"""
Audit every site's available ATLAS source instances. For each site, list all
related sources from /source/sources, then probe each instance for:
  - measurement endpoint health (HTTP 200 vs 500 BadSqlGrammar)
  - total_persons (dashboard summary)
  - vocabulary release (oldest vocabulary v5.0 entry)
  - data_cutoff_month (last observed month with non-trivial data)

Output: data/site_mapping/site_instance_audit_<DATE>.csv
        + recommends a "best" instance per site (latest sourceName + healthy)

Why this exists: 2026-05-12 UUH refresh discovered the default sourceKey
cdm_0023 (UUH_5.3.0_04, latest sourceName) returned HTTP 500 BadSqlGrammar
while older cdm_0022 (UUH_5.3.0_03) was healthy. Other sites may have similar
issues hidden behind the default sourceKey.

Usage:
  python audit_site_instances.py            # all 23 sites
  python audit_site_instances.py --sites KHNMC,UUH
"""
import csv
import os
import sys
import re
import argparse
import datetime as dt
import functools

print = functools.partial(print, flush=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'automation'))

from atlas_auto.client import FedernetClient  # noqa: E402
from credentials import get_feedernet_credentials  # noqa: E402

SITE_MAP_CSV = os.path.join(REPO_ROOT, 'data', 'site_mapping', 'source_key_mapping.csv')
OUT_PATH = os.path.join(REPO_ROOT, 'data', 'site_mapping',
                        f"site_instance_audit_{dt.date.today().isoformat()}.csv")


def load_sites():
    sites = []
    with open(SITE_MAP_CSV, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            code = (r.get('﻿code') or r.get('code') or '').strip()
            if not code: continue
            sites.append({
                'code': code,
                'cdm_name': r.get('cdmName', ''),
                'source_key_default': r.get('sourceKey', ''),
                'group_id': int(r.get('group_id', 0) or 0),
                'site_id': int(r.get('site_id', 0) or 0),
            })
    return sites


def probe_instance(client, sk):
    """Return dict with health + metadata for one sourceKey."""
    base = client.webapi_url
    result = {'source_key': sk}

    # 1. measurement endpoint health
    try:
        r = client.session.get(f"{base}/cdmresults/{sk}/measurement", timeout=15)
        result['measurement_status'] = r.status_code
        if r.ok:
            data = r.json()
            result['measurement_concepts'] = len(data) if isinstance(data, list) else 0
        else:
            short = r.text[:120] if r.text else ''
            result['measurement_error'] = re.sub(r'\s+', ' ', short)[:120]
    except Exception as e:
        result['measurement_status'] = 'EXC'
        result['measurement_error'] = f"{type(e).__name__}: {str(e)[:100]}"

    # 2. dashboard: total_persons + data_cutoff_month
    try:
        r = client.session.get(f"{base}/cdmresults/{sk}/dashboard", timeout=15)
        if r.ok:
            d = r.json()
            for item in d.get('summary', []) or []:
                if item.get('attributeName') == 'Number of persons':
                    result['total_persons'] = int(item.get('attributeValue', 0))
            obs = d.get('observedByMonth', []) or []
            non_zero = [o for o in obs if (o.get('countValue', 0) or 0) > 100]
            if non_zero:
                last = max(non_zero, key=lambda x: x.get('monthYear', 0))
                result['data_cutoff_month'] = last.get('monthYear')
    except Exception as e:
        result['dashboard_error'] = str(e)[:100]

    # 3. Vocabulary release (the "None" or "Vocabulary" entry holds OMOP release date)
    try:
        r = client.session.get(f"{base}/vocabulary/{sk}/vocabularies", timeout=15)
        if r.ok:
            for v in r.json():
                if isinstance(v, dict) and v.get('VOCABULARY_ID') == 'None':
                    result['vocabulary_release'] = v.get('VOCABULARY_VERSION')
                    break
            if 'vocabulary_release' not in result:
                for v in r.json():
                    if isinstance(v, dict) and 'Vocabulary' in str(v.get('VOCABULARY_NAME', '')):
                        result['vocabulary_release'] = v.get('VOCABULARY_VERSION')
                        break
    except Exception as e:
        result['vocab_error'] = str(e)[:100]
    return result


def find_instances_for_site(client, site_code):
    """Search /source/sources for entries whose sourceName starts with site_code (case-insensitive)."""
    base = client.webapi_url
    r = client.session.get(f"{base}/source/sources", timeout=30)
    if not r.ok:
        return []
    out = []
    for s in r.json():
        nm = str(s.get('sourceName', ''))
        if nm.upper().startswith(site_code.upper() + '_') or nm.upper() == site_code.upper():
            out.append({
                'source_id': s.get('sourceId'),
                'source_name': nm,
                'source_key': s.get('sourceKey'),
                'source_dialect': s.get('sourceDialect'),
            })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sites', default='')
    args = parser.parse_args()

    sites = load_sites()
    if args.sites:
        wanted = set(s.strip() for s in args.sites.split(','))
        sites = [s for s in sites if s['code'] in wanted]

    client = FedernetClient()
    client.login_portal(*get_feedernet_credentials())

    rows = []
    for site in sites:
        print(f"\n--- {site['code']} (default sourceKey: {site['source_key_default']}) ---")
        # Connect to site once
        try:
            client.connect_site(group_id=site['group_id'], site_id=site['site_id'])
        except Exception as e:
            print(f"  connect_site failed: {e}")
            continue

        # Find all instances for this site
        instances = find_instances_for_site(client, site['code'])
        print(f"  {len(instances)} instances found")

        # Probe each
        for inst in instances:
            sk = inst['source_key']
            probe = probe_instance(client, sk)
            is_default = sk == site['source_key_default']
            healthy = probe.get('measurement_status') == 200
            row = {
                'site_code': site['code'],
                'source_name': inst['source_name'],
                'source_key': sk,
                'is_site_mapping_default': is_default,
                'healthy': healthy,
                'measurement_status': probe.get('measurement_status'),
                'measurement_error': probe.get('measurement_error', ''),
                'measurement_concepts': probe.get('measurement_concepts', ''),
                'total_persons': probe.get('total_persons', ''),
                'data_cutoff_month': probe.get('data_cutoff_month', ''),
                'vocabulary_release': probe.get('vocabulary_release', ''),
            }
            rows.append(row)
            mark = '★' if is_default else ' '
            health = '✓' if healthy else '✗'
            print(f"   {mark} {health} {inst['source_name']:<30s} [{sk:<22s}] persons={probe.get('total_persons','?')} cutoff={probe.get('data_cutoff_month','?')} vocab={probe.get('vocabulary_release','?')}")

    # Mark "best" per site: healthy + latest sourceName suffix number
    by_site = {}
    for r in rows:
        by_site.setdefault(r['site_code'], []).append(r)
    for code, group in by_site.items():
        healthy = [r for r in group if r['healthy']]
        if not healthy:
            continue
        # Best = healthy + max total_persons (proxy for "most data")
        best = max(healthy, key=lambda x: int(x.get('total_persons') or 0))
        for r in group:
            r['best_for_site'] = (r is best)
        # Default health check
        default_row = next((r for r in group if r['is_site_mapping_default']), None)
        if default_row and not default_row['healthy']:
            for r in group:
                if r is best and best is not default_row:
                    r['default_broken_use_this_instead'] = True

    # Write CSV — sanitize all string fields to be CSV-safe on Windows
    fieldnames = ['site_code', 'source_name', 'source_key', 'is_site_mapping_default',
                  'best_for_site', 'default_broken_use_this_instead',
                  'healthy', 'measurement_status', 'measurement_concepts',
                  'total_persons', 'data_cutoff_month', 'vocabulary_release',
                  'measurement_error']

    def sanitize(v):
        if v is None: return ''
        if isinstance(v, bool): return v
        if isinstance(v, (int, float)): return v
        s = str(v)
        # Strip all control chars + non-printable + Unicode that might break Windows CSV
        return ''.join(ch for ch in s if ch.isprintable() and ord(ch) < 0x10000)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore',
                           quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            clean = {k: sanitize(r.get(k)) for k in fieldnames}
            w.writerow(clean)
    print(f"\n→ {OUT_PATH} ({len(rows)} rows)")

    # Summary: default-broken sites
    broken = [c for c, g in by_site.items()
              if any(r['is_site_mapping_default'] and not r['healthy'] for r in g)]
    print(f"\nSites where site_mapping default is BROKEN: {len(broken)}")
    for c in broken:
        for r in by_site[c]:
            if r.get('default_broken_use_this_instead'):
                print(f"  {c}: default={r['source_name']} broken; recommend {r['source_name']} [{r['source_key']}]")
                break


if __name__ == '__main__':
    main()
