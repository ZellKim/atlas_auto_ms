"""
Collect Achilles measurement drilldown (per-concept value distribution + unit
metadata) for one or more sites. Designed for batched API-friendly execution.

Per site:
  - Reads the fresh concept inventory from
    data/concept_frequency/by_site/{CODE}_measurement.csv
  - Calls /cdmresults/{sk}/measurement/{conceptId} for each concept
  - Retries up to 3× with exponential backoff on transient ERROR
  - Saves incrementally (CSV + raw JSON) every 50 concepts
  - Writes meta sidecar with source/timestamp/coverage

Output (per site):
  data/measurement/drilldown_2026-05-12/{CODE}_measurement_distribution.csv
  data/measurement/drilldown_2026-05-12/raw/{CODE}_measurement.json
  data/measurement/drilldown_2026-05-12/{CODE}_measurement_distribution.meta.json

API politeness:
  --sleep N (default 1.0s between concept calls)
  --inter-site-sleep N (default 10s between sites)
  --max-retries 3 + exponential backoff (2s, 4s, 8s)

Usage examples:
  # Batch 1: 5 sites
  python collect_measurement_drilldown.py --sites KHNMC,AUMC,DCMC,SCHGM,SCHCA

  # Single site (test)
  python collect_measurement_drilldown.py --sites KHNMC --limit 50

  # Resume — skip sites that already have output
  python collect_measurement_drilldown.py --sites KHNMC,AUMC --skip-existing
"""
import argparse
import csv
import datetime as dt
import functools
import json
import os
import subprocess
import sys
import time

print = functools.partial(print, flush=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'automation'))

from atlas_auto.client import FedernetClient  # noqa: E402
from credentials import get_feedernet_credentials  # noqa: E402

SITE_MAP_CSV = os.path.join(REPO_ROOT, 'data', 'site_mapping', 'source_key_mapping.csv')
FREQ_DIR = os.path.join(REPO_ROOT, 'data', 'concept_frequency', 'by_site')

TODAY = os.environ.get('DRILLDOWN_DATE') or dt.date.today().isoformat()
OUT_DIR = os.path.join(REPO_ROOT, 'data', 'measurement', f'drilldown_{TODAY}')
RAW_DIR = os.path.join(OUT_DIR, 'raw')

CSV_FIELDS = ['site', 'concept_id', 'concept_name', 'numPersons_achilles',
              'unit_concept_id', 'unit_name', 'count',
              'min', 'p10', 'p25', 'median', 'p75', 'p90', 'max']

SCRIPT_VERSION = "1.0.0"


def load_sites():
    sites = []
    with open(SITE_MAP_CSV, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            code = (r.get('﻿code') or r.get('code') or '').strip()
            if not code: continue
            sites.append({
                'code': code,
                'cdm_name': r.get('cdmName', ''),
                'source_key': r.get('sourceKey', ''),
                'group_id': int(r.get('group_id', 0) or 0),
                'site_id': int(r.get('site_id', 0) or 0),
            })
    return sites


def load_concept_inventory_for_site(code, override_source_key=None):
    """Read the fresh measurement frequency CSV + its meta. Return (concepts, meta)."""
    csv_path = os.path.join(FREQ_DIR, f'{code}_measurement.csv')
    meta_path = os.path.join(FREQ_DIR, f'{code}_measurement.meta.json')
    if not os.path.exists(csv_path):
        return None, None
    concepts = []
    with open(csv_path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            cid = (r.get('conceptId') or '').strip()
            if not cid: continue
            try:
                np_ = int(r.get('numPersons', 0) or 0)
            except (TypeError, ValueError):
                np_ = 0
            name = (r.get('conceptPath') or '').split('||')[-1].strip().strip('"')
            concepts.append({'concept_id': int(cid), 'name': name, 'numPersons': np_})
    concepts.sort(key=lambda x: -x['numPersons'])  # frequent first
    meta = None
    if os.path.exists(meta_path):
        # Google Drive can throw transient OSError: Invalid argument; retry once.
        for attempt in (1, 2):
            try:
                with open(meta_path, encoding='utf-8') as f:
                    meta = json.load(f)
                break
            except (OSError, json.JSONDecodeError) as e:
                if attempt == 1:
                    time.sleep(0.5)
                else:
                    print(f"  WARN: failed to read {os.path.basename(meta_path)}: {type(e).__name__}: {e}")
                    meta = None
    return concepts, meta


def filter_to_loinc(client, concepts):
    """Look up vocabulary for each concept; return only those with VOCABULARY_ID == 'LOINC'.
    Cache lookups in process memory."""
    cache = {}
    base = client.webapi_url
    loinc = []
    skipped = {}
    for c in concepts:
        cid = c['concept_id']
        if cid in cache:
            voc = cache[cid]
        else:
            try:
                r = client.session.get(f"{base}/vocabulary/concept/{cid}", timeout=15)
                voc = r.json().get('VOCABULARY_ID', '?') if r.ok else '?'
            except Exception:
                voc = '?'
            cache[cid] = voc
        if voc == 'LOINC':
            loinc.append(c)
        else:
            skipped[voc] = skipped.get(voc, 0) + 1
    return loinc, skipped


def extract_values(raw):
    """recordsByUnit (count per unit) + measurementValueDistribution (stats per unit)."""
    out = []
    if not isinstance(raw, dict):
        return out
    unit_counts = {}
    for u in raw.get('recordsByUnit', []) or []:
        unit_counts[u.get('conceptName', '?')] = {
            'unit_concept_id': u.get('conceptId', 0),
            'count': u.get('countValue', 0),
        }
    mvd_units = set()
    for d in raw.get('measurementValueDistribution', []) or []:
        unit = d.get('category', '?')
        mvd_units.add(unit)
        meta = unit_counts.get(unit, {'unit_concept_id': 0, 'count': 0})
        out.append({
            'unit_concept_id': meta['unit_concept_id'],
            'unit_name': unit,
            'count': meta['count'],
            'min': d.get('minValue'),
            'p10': d.get('p10Value'),
            'p25': d.get('p25Value'),
            'median': d.get('medianValue'),
            'p75': d.get('p75Value'),
            'p90': d.get('p90Value'),
            'max': d.get('maxValue'),
        })
    for unit, meta in unit_counts.items():
        if unit not in mvd_units:
            out.append({
                'unit_concept_id': meta['unit_concept_id'], 'unit_name': unit,
                'count': meta['count'],
                'min': None, 'p10': None, 'p25': None, 'median': None,
                'p75': None, 'p90': None, 'max': None,
            })
    return out


def drilldown_with_retry(client, site, source_key, concept_id, max_retries=3):
    """Returns (raw_or_none, message). Auto re-authenticates on HTTP 401 session expiry."""
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = client.get_achilles_drilldown(source_key, 'measurement', int(concept_id))
            if raw is None or (isinstance(raw, dict) and not raw):
                last = f"attempt {attempt}: empty"
            else:
                return raw, 'OK'
        except Exception as e:
            err_str = str(e)
            last = f"attempt {attempt}: {type(e).__name__}: {err_str[:120]}"
            # Detect HTTP 401 (session cookie expired) → re-authenticate + re-bind site
            if '401' in err_str:
                try:
                    client.login_portal(*get_feedernet_credentials())
                    client.connect_site(group_id=site['group_id'], site_id=site['site_id'])
                    last += " | re-auth OK"
                except Exception as re_e:
                    last += f" | re-auth FAILED: {str(re_e)[:60]}"
        if attempt < max_retries:
            time.sleep(2 ** attempt)
    return None, last


def git_commit():
    try:
        out = subprocess.run(['git', '-C', REPO_ROOT, 'rev-parse', 'HEAD'],
                             capture_output=True, text=True, check=True, timeout=5)
        return out.stdout.strip()[:12]
    except Exception:
        return 'unknown'


def save_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in CSV_FIELDS})


def run_for_site(client, site, args):
    code = site['code']
    sk_override = args.override_map.get(code)
    sk = sk_override or site['source_key']

    csv_out = os.path.join(OUT_DIR, f'{code}_measurement_distribution.csv')
    raw_out = os.path.join(RAW_DIR, f'{code}_measurement.json')
    meta_out = os.path.join(OUT_DIR, f'{code}_measurement_distribution.meta.json')

    if args.skip_existing and os.path.exists(csv_out) and os.path.exists(meta_out):
        print(f"[{code}] skipping (output exists)")
        return {'code': code, 'status': 'SKIPPED'}

    concepts, freq_meta = load_concept_inventory_for_site(code)
    if not concepts:
        print(f"[{code}] no concept inventory at {FREQ_DIR}/{code}_measurement.csv — skip")
        return {'code': code, 'status': 'NO_INVENTORY'}

    # Filter via vocabulary cache. Default: LOINC only.
    # --vocabulary-include "SNOMED,EDI,..." overrides to keep specified vocabs.
    filtered_out = 0
    if args.loinc_cache:
        before = len(concepts)
        if args.vocabulary_include:
            wanted = {v.strip() for v in args.vocabulary_include.split(',') if v.strip()}
            filtered = [c for c in concepts if args.loinc_cache.get(str(c['concept_id'])) in wanted]
            filter_desc = f"vocab filter ({'/'.join(sorted(wanted))})"
        else:
            filtered = [c for c in concepts if args.loinc_cache.get(str(c['concept_id'])) == 'LOINC']
            filter_desc = "LOINC filter"
        concepts = filtered
        filtered_out = before - len(concepts)
        print(f"[{code}] {filter_desc}: {before} → {len(concepts)} concepts ({filtered_out} excluded)")

    if args.limit:
        concepts = concepts[:args.limit]
    n_concepts = len(concepts)
    print(f"\n=== [{code}] {n_concepts} concepts | sourceKey={sk}{' (override)' if sk_override else ''} ===")

    try:
        client.connect_site(group_id=site['group_id'], site_id=site['site_id'])
    except Exception as e:
        print(f"  connect_site failed: {e}")
        return {'code': code, 'status': 'CONNECT_FAILED'}

    rows = []
    raw_results = {}
    errors = []
    t0 = time.time()
    for i, c in enumerate(concepts, 1):
        cid = c['concept_id']; name = c['name']; np_ = c['numPersons']
        raw, msg = drilldown_with_retry(client, site, sk, cid, max_retries=args.max_retries)
        if raw is not None:
            raw_results[str(cid)] = raw
            entries = extract_values(raw)
            if not entries:
                rows.append({'site': code, 'concept_id': cid, 'concept_name': name,
                             'numPersons_achilles': np_,
                             'unit_concept_id': 0, 'unit_name': 'NO_DATA',
                             'count': 0})
            else:
                for e in entries:
                    rows.append({'site': code, 'concept_id': cid, 'concept_name': name,
                                 'numPersons_achilles': np_, **e})
        else:
            errors.append((cid, name, msg))
            rows.append({'site': code, 'concept_id': cid, 'concept_name': name,
                         'numPersons_achilles': np_,
                         'unit_concept_id': 0, 'unit_name': 'ERROR',
                         'count': 0, 'max': (msg or '')[:80]})

        if i % 25 == 0 or i == n_concepts:
            elapsed = time.time() - t0
            rate = i / max(elapsed, 1e-9)
            eta = (n_concepts - i) / max(rate, 1e-9) / 60
            print(f"  [{i:>4}/{n_concepts}] {elapsed:>4.0f}s elapsed, ~{eta:.1f}min ETA, "
                  f"{len(rows)} rows, {len(errors)} errors")

        if i % args.save_every == 0:
            save_csv(rows, csv_out)

        time.sleep(args.sleep)

    save_csv(rows, csv_out)
    if not args.no_raw:
        os.makedirs(os.path.dirname(raw_out), exist_ok=True)
        with open(raw_out, 'w', encoding='utf-8') as f:
            json.dump(raw_results, f, ensure_ascii=False)
    elapsed = time.time() - t0

    meta = {
        'site_code': code,
        'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'cdm_name': site['cdm_name'],
        'group_id': site['group_id'], 'site_id': site['site_id'],
        'source_key': sk,
        'source_key_override': sk_override is not None,
        'concept_inventory_source': os.path.relpath(
            os.path.join(FREQ_DIR, f'{code}_measurement.csv'), REPO_ROOT),
        'concept_inventory_collected_at': (freq_meta or {}).get('collected_at'),
        'concepts_attempted': n_concepts,
        'concepts_with_data': sum(1 for r in rows if r['unit_name'] not in ('NO_DATA', 'ERROR')),
        'concepts_no_data': sum(1 for r in rows if r['unit_name'] == 'NO_DATA'),
        'concepts_error': sum(1 for r in rows if r['unit_name'] == 'ERROR'),
        'rows_total': len(rows),
        'elapsed_seconds': round(elapsed, 1),
        'collector_script': os.path.basename(__file__),
        'collector_version': SCRIPT_VERSION,
        'collector_commit': git_commit(),
        'sleep_seconds': args.sleep,
        'max_retries': args.max_retries,
    }
    with open(meta_out, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  → {os.path.relpath(csv_out, REPO_ROOT)} ({len(rows)} rows)")
    print(f"  → {os.path.relpath(meta_out, REPO_ROOT)}")
    return {'code': code, 'status': 'OK', 'rows': len(rows), 'errors': len(errors)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sites', required=True, help='comma-separated site codes')
    parser.add_argument('--limit', type=int, help='cap concept count (testing)')
    parser.add_argument('--sleep', type=float, default=1.0)
    parser.add_argument('--inter-site-sleep', type=float, default=10.0)
    parser.add_argument('--save-every', type=int, default=50)
    parser.add_argument('--max-retries', type=int, default=3)
    parser.add_argument('--no-raw', action='store_true')
    parser.add_argument('--skip-existing', action='store_true')
    parser.add_argument('--override-source-key', default='',
                        help='comma-separated CODE:SOURCEKEY overrides (e.g., UUH:cdm_0022)')
    parser.add_argument('--vocabulary-cache', default='',
                        help='path to JSON {concept_id: VOCABULARY_ID} cache. '
                             'If provided, only LOINC concepts are drilled down (default).')
    parser.add_argument('--vocabulary-include', default='',
                        help='comma-separated VOCABULARY_IDs to keep instead of LOINC '
                             '(e.g., "SNOMED,EDI,CPT4,OMOP Genomic,Cancer Modifier"). '
                             'Requires --vocabulary-cache.')
    args = parser.parse_args()

    args.loinc_cache = None
    if args.vocabulary_cache:
        with open(args.vocabulary_cache, encoding='utf-8') as f:
            args.loinc_cache = json.load(f)
        print(f"Loaded vocabulary cache: {len(args.loinc_cache):,} entries from {args.vocabulary_cache}")

    args.override_map = {}
    if args.override_source_key:
        for pair in args.override_source_key.split(','):
            if ':' in pair:
                c, sk = pair.split(':', 1)
                args.override_map[c.strip()] = sk.strip()

    all_sites = {s['code']: s for s in load_sites()}
    wanted = [s.strip() for s in args.sites.split(',') if s.strip()]
    sites = [all_sites[c] for c in wanted if c in all_sites]
    missing = [c for c in wanted if c not in all_sites]
    if missing:
        print(f"WARN: unknown sites: {missing}")
    if not sites:
        print("No valid sites — abort")
        return

    print(f"=== Drilldown master ===")
    print(f"Sites: {[s['code'] for s in sites]}")
    print(f"Output dir: {OUT_DIR}")
    print(f"sleep={args.sleep}s | inter-site-sleep={args.inter_site_sleep}s | max-retries={args.max_retries}")

    client = FedernetClient()
    client.login_portal(*get_feedernet_credentials())

    results = []
    for i, site in enumerate(sites, 1):
        res = run_for_site(client, site, args)
        results.append(res)
        if i < len(sites):
            print(f"  ... inter-site sleep {args.inter_site_sleep}s ...")
            time.sleep(args.inter_site_sleep)

    print("\n=== Final summary ===")
    for r in results:
        print(f"  {r['code']:8s} {r['status']:15s} rows={r.get('rows','-')} errors={r.get('errors','-')}")


if __name__ == '__main__':
    main()
