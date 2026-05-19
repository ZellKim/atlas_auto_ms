"""
Refresh Achilles concept frequency for one (site, domain) pair, with mandatory
metadata header (sidecar .meta.json) for traceability.

Why mandatory metadata: the 2026-04-16 untraceable CSV episode showed that
without source_key, source_name, vocabulary release, total_persons, and
collected_at recorded alongside the data, future readers cannot diagnose
which ATLAS instance the data came from. See
`data/concept_frequency/archive/2026-04-16_untraceable_source/README.md`.

Output (per call):
  data/concept_frequency/by_site/{CODE}_{domain}.csv      — pure CSV
  data/concept_frequency/by_site/{CODE}_{domain}.meta.json — sidecar metadata

Test usage:
  python refresh_achilles_frequency.py --sites KHNMC --domains measurement
Full usage:
  python refresh_achilles_frequency.py            # all 23 sites × 5 domains
  python refresh_achilles_frequency.py --sites KHNMC,AUMC --domains measurement,condition
  python refresh_achilles_frequency.py --dry-run  # call API but do not write
"""
import csv
import json
import os
import sys
import time
import argparse
import datetime as dt
import subprocess
import functools

print = functools.partial(print, flush=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'automation'))

from atlas_auto.client import FedernetClient  # noqa: E402
from credentials import get_feedernet_credentials  # noqa: E402

SITE_MAP_CSV = os.path.join(REPO_ROOT, 'data', 'site_mapping', 'source_key_mapping.csv')
OUT_DIR = os.path.join(REPO_ROOT, 'data', 'concept_frequency', 'by_site')

DOMAINS_ALL = ['condition', 'drug', 'measurement', 'observation', 'procedure']

CSV_FIELDS = ['conceptId', 'conceptPath', 'numPersons', 'percentPersons', 'recordsPerPerson']

SCRIPT_VERSION = "1.0.0"


def load_sites():
    """Return ordered list of {code, sourceName, sourceKey, group_id, site_id}."""
    sites = []
    with open(SITE_MAP_CSV, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            code = (r.get('﻿code') or r.get('code') or '').strip()
            if not code:
                continue
            sites.append({
                'code': code,
                'cdm_name': r.get('cdmName', '').strip(),
                'source_key': r.get('sourceKey', '').strip(),
                'group_id': int(r.get('group_id', 0) or 0),
                'site_id': int(r.get('site_id', 0) or 0),
            })
    return sites


def git_commit():
    try:
        out = subprocess.run(['git', '-C', REPO_ROOT, 'rev-parse', 'HEAD'],
                             capture_output=True, text=True, check=True, timeout=5)
        return out.stdout.strip()[:12]
    except Exception:
        return 'unknown'


def fetch_source_metadata(client, source_key):
    """Return dict with sourceName/dialect/daimons + vocabulary release + dashboard summary."""
    meta = {}
    base = client.webapi_url

    # 1. /source/sources — sourceName + daimons
    try:
        r = client.session.get(f"{base}/source/sources", timeout=30)
        if r.ok:
            sources = r.json()
            entry = next((s for s in sources if s.get('sourceKey') == source_key), None)
            if entry:
                meta['source_id'] = entry.get('sourceId')
                meta['source_name'] = entry.get('sourceName')
                meta['source_dialect'] = entry.get('sourceDialect')
                meta['daimons'] = {
                    d.get('daimonType'): d.get('tableQualifier')
                    for d in entry.get('daimons', []) or []
                }
    except Exception as e:
        meta['source_meta_error'] = str(e)[:100]

    # 2. /vocabulary/{sk}/vocabularies — OMOP Vocabulary release
    try:
        r = client.session.get(f"{base}/vocabulary/{source_key}/vocabularies", timeout=30)
        if r.ok:
            vocabs = r.json()
            for v in vocabs:
                if isinstance(v, dict) and v.get('VOCABULARY_ID') == 'None':
                    meta['omop_vocabulary_release'] = v.get('VOCABULARY_VERSION')
                    break
            if 'omop_vocabulary_release' not in meta:
                for v in vocabs:
                    if isinstance(v, dict) and 'Vocabulary' in str(v.get('VOCABULARY_NAME', '')):
                        meta['omop_vocabulary_release'] = v.get('VOCABULARY_VERSION')
                        break
    except Exception as e:
        meta['vocab_meta_error'] = str(e)[:100]

    # 3. /cdmresults/{sk}/dashboard — total_persons + data_cutoff_month
    try:
        r = client.session.get(f"{base}/cdmresults/{source_key}/dashboard", timeout=30)
        if r.ok:
            d = r.json()
            for item in d.get('summary', []) or []:
                if item.get('attributeName') == 'Number of persons':
                    meta['total_persons'] = int(item.get('attributeValue', 0))
            obs = d.get('observedByMonth', []) or []
            non_zero = [o for o in obs if (o.get('countValue', 0) or 0) > 100]
            if non_zero:
                last = max(non_zero, key=lambda x: x.get('monthYear', 0))
                meta['data_cutoff_month'] = last.get('monthYear')
    except Exception as e:
        meta['dashboard_meta_error'] = str(e)[:100]

    return meta


def write_meta_sidecar(meta_path, meta_dict):
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_dict, f, ensure_ascii=False, indent=2)


def write_csv(rows, csv_path):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            out = {}
            for k in CSV_FIELDS:
                v = r.get(k)
                out[k] = '' if v is None else v
            w.writerow(out)


def refresh_one(client, site, domain, dry_run=False):
    code = site['code']
    sk = site['source_key']
    print(f"\n--- {code} / {domain} (sourceKey={sk}) ---")

    # Connect site (skip if same group/site as previous)
    try:
        client.connect_site(group_id=site['group_id'], site_id=site['site_id'])
    except Exception as e:
        return {'status': 'CONNECT_FAILED', 'error': str(e)[:120], 'rows': 0}

    # Fetch source metadata
    t0 = time.time()
    src_meta = fetch_source_metadata(client, sk)
    print(f"  metadata: source={src_meta.get('source_name')}, "
          f"vocab={src_meta.get('omop_vocabulary_release')}, "
          f"total_persons={src_meta.get('total_persons')}, "
          f"cutoff_month={src_meta.get('data_cutoff_month')}")

    # Fetch concept frequency
    try:
        freq = client.get_achilles_frequency(sk, domain)
        rows = freq if isinstance(freq, list) else []
        elapsed = time.time() - t0
        print(f"  fetched {len(rows)} concepts in {elapsed:.1f}s")
    except Exception as e:
        return {'status': 'FETCH_FAILED', 'error': str(e)[:120], 'rows': 0,
                'source_metadata': src_meta}

    # Build meta sidecar
    meta = {
        'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'site_code': code,
        'cdm_name': site['cdm_name'],
        'group_id': site['group_id'],
        'site_id': site['site_id'],
        'source_key': sk,
        'domain': domain,
        'api_endpoint': f"/cdmresults/{sk}/{domain}",
        'rows_returned': len(rows),
        'collector_script': os.path.basename(__file__),
        'collector_version': SCRIPT_VERSION,
        'collector_commit': git_commit(),
        'fetch_seconds': round(elapsed, 2),
        **src_meta,
    }
    # Override info — when site_mapping default sourceKey was broken
    if site.get('_override_applied'):
        meta['source_key_override'] = True
        meta['site_mapping_default_source_key'] = site.get('_original_source_key')
        meta['override_reason'] = 'site_mapping default sourceKey returned HTTP 500 (BadSqlGrammarException) at refresh time'

    if dry_run:
        print(f"  [dry-run] would write {len(rows)} rows + meta")
        return {'status': 'DRY_RUN', 'rows': len(rows), 'meta': meta}

    # Write
    csv_path = os.path.join(OUT_DIR, f"{code}_{domain}.csv")
    meta_path = os.path.join(OUT_DIR, f"{code}_{domain}.meta.json")
    write_csv(rows, csv_path)
    write_meta_sidecar(meta_path, meta)
    print(f"  → {os.path.relpath(csv_path, REPO_ROOT)} ({len(rows)} rows)")
    print(f"  → {os.path.relpath(meta_path, REPO_ROOT)}")
    return {'status': 'OK', 'rows': len(rows), 'meta': meta, 'csv_path': csv_path}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sites', default='', help='comma-separated site codes (default: all)')
    parser.add_argument('--domains', default='', help='comma-separated domains (default: all 5)')
    parser.add_argument('--override-source-key', default='',
                        help='comma-separated CODE:SOURCEKEY overrides (e.g., UUH:cdm_0022). '
                             'Use when site_mapping default sourceKey is broken — refresh proceeds '
                             'against the override sourceKey, and the meta sidecar records the override.')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--sleep', type=float, default=0.5)
    args = parser.parse_args()

    overrides = {}
    if args.override_source_key:
        for pair in args.override_source_key.split(','):
            if ':' in pair:
                code, sk = pair.split(':', 1)
                overrides[code.strip()] = sk.strip()

    sites = load_sites()
    if args.sites:
        wanted = set(s.strip() for s in args.sites.split(','))
        sites = [s for s in sites if s['code'] in wanted]
    domains = args.domains.split(',') if args.domains else DOMAINS_ALL
    domains = [d.strip() for d in domains if d.strip() in DOMAINS_ALL]

    print(f"Refresh plan: {len(sites)} site × {len(domains)} domain = {len(sites)*len(domains)} pairs")
    for s in sites:
        print(f"  - {s['code']} ({s['source_key']})")
    print(f"Domains: {domains}")
    print(f"Dry-run: {args.dry_run}")
    print()

    client = FedernetClient()
    email, pw = get_feedernet_credentials()
    if not client.login_portal(email, pw):
        print("Portal login failed")
        return

    results = []
    for site in sites:
        # Apply sourceKey override if provided
        site_to_use = dict(site)
        if site['code'] in overrides:
            new_sk = overrides[site['code']]
            print(f"[override] {site['code']}: sourceKey {site['source_key']} → {new_sk}")
            site_to_use['source_key'] = new_sk
            site_to_use['_override_applied'] = True
            site_to_use['_original_source_key'] = site['source_key']
        for domain in domains:
            res = refresh_one(client, site_to_use, domain, dry_run=args.dry_run)
            results.append({'code': site['code'], 'domain': domain, **{k: v for k, v in res.items() if k != 'meta'}})
            time.sleep(args.sleep)

    # Summary
    print("\n=== Summary ===")
    for r in results:
        print(f"  {r['code']:8s} {r['domain']:13s}  {r['status']:15s}  rows={r['rows']}")

    ok = sum(1 for r in results if r['status'] == 'OK')
    print(f"\n  OK: {ok}/{len(results)}")


if __name__ == '__main__':
    main()
