"""
KHNMC 전체 measurement concept (1,494개) value distribution + unit 전수조사.

기반: data/scripts/collect_v4_value_survey.py 의 extract_values() 로직 그대로 재사용.
변경점:
  - CONCEPTS: data/concept_frequency/by_site/KHNMC_measurement.csv 에서 동적 로드
  - SITES: KHNMC 1개만
  - credentials: automation/credentials.py
  - 50 concept마다 incremental save (중간 실패 대비)

Usage:
  python collect_khnmc_measurement_dist.py            # 전체 1,494 concept
  python collect_khnmc_measurement_dist.py --min-persons 10000  # 빈도 threshold
  python collect_khnmc_measurement_dist.py --limit 50           # 테스트 (50개만)
  python collect_khnmc_measurement_dist.py --bearer "eyJ..."    # 토큰 직접
"""
import csv
import json
import os
import sys
import time
import argparse
import functools
print = functools.partial(print, flush=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'automation'))

from atlas_auto.client import FedernetClient
from credentials import get_feedernet_credentials

CONCEPT_FREQ_CSV = os.path.join(REPO_ROOT, 'data', 'concept_frequency', 'by_site', 'KHNMC_measurement.csv')
OUTPUT_PATH = os.path.join(REPO_ROOT, 'data', 'measurement', 'khnmc_full_value_survey.csv')
RAW_PATH = os.path.join(REPO_ROOT, 'data', 'measurement', 'raw_drilldown', 'khnmc_full_measurement.json')

SITE = {'code': 'KHNMC', 'group_id': 7, 'site_id': 203, 'sourceKey': 'cdmpv53_251128'}


def load_concepts(min_persons: int = 0, limit: int = None):
    """KHNMC measurement concept frequency CSV → [(concept_id, concept_name, num_persons), ...]"""
    rows = []
    with open(CONCEPT_FREQ_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            cid = r.get('conceptId', '').strip()
            if not cid:
                continue
            try:
                np_ = int(r.get('numPersons', 0))
            except ValueError:
                np_ = 0
            if np_ < min_persons:
                continue
            # conceptPath 마지막 segment = concept name
            path = r.get('conceptPath', '')
            name = path.split('||')[-1].strip().strip('"')
            rows.append((cid, name, np_))
    # numPersons desc로 정렬 — 자주 쓰이는 것부터 먼저 수집 (중간 실패 시 손실 최소화)
    rows.sort(key=lambda x: -x[2])
    if limit:
        rows = rows[:limit]
    return rows


def extract_values(raw):
    """recordsByUnit (count per unit) + measurementValueDistribution (stats per unit)"""
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
    # units with count but no distribution
    for unit, meta in unit_counts.items():
        if unit not in mvd_units:
            out.append({
                'unit_concept_id': meta['unit_concept_id'],
                'unit_name': unit,
                'count': meta['count'],
                'min': None, 'p10': None, 'p25': None, 'median': None,
                'p75': None, 'p90': None, 'max': None,
            })
    return out


FIELDS = ['site', 'concept_id', 'concept_name', 'numPersons_achilles',
          'unit_concept_id', 'unit_name', 'count',
          'min', 'p10', 'p25', 'median', 'p75', 'p90', 'max']


def save_csv(rows, path):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bearer', help='Bearer token (otherwise uses credentials.py)')
    parser.add_argument('--min-persons', type=int, default=0,
                        help='Skip concepts below this numPersons threshold')
    parser.add_argument('--limit', type=int, help='Limit concept count (testing)')
    parser.add_argument('--no-raw', action='store_true', help='Skip raw JSON dump')
    parser.add_argument('--save-every', type=int, default=50,
                        help='Incremental CSV save frequency')
    parser.add_argument('--sleep', type=float, default=0.2,
                        help='Delay between API calls (seconds)')
    args = parser.parse_args()

    concepts = load_concepts(min_persons=args.min_persons, limit=args.limit)
    print(f"Loaded {len(concepts)} concepts from {CONCEPT_FREQ_CSV}")
    if args.min_persons:
        print(f"  (filtered: numPersons >= {args.min_persons})")
    est_min = len(concepts) * (args.sleep + 0.3) / 60
    print(f"Estimated time: ~{est_min:.1f} min")
    print(f"Output: {OUTPUT_PATH}")

    client = FedernetClient()
    if args.bearer:
        if not client.login_with_bearer_token(args.bearer):
            print("Bearer login failed")
            return
    else:
        email, pw = get_feedernet_credentials()
        if not client.login_portal(email, pw):
            print("Portal login failed")
            return

    print(f"Connecting to {SITE['code']} (group={SITE['group_id']}, site={SITE['site_id']})...")
    if not client.connect_site(group_id=SITE['group_id'], site_id=SITE['site_id']):
        print("connect_site failed")
        return

    results = []
    raw_results = {}
    errors = []
    t0 = time.time()

    for i, (cid, name, np_) in enumerate(concepts, 1):
        try:
            raw = client.get_achilles_drilldown(SITE['sourceKey'], 'measurement', int(cid))
            if not args.no_raw:
                raw_results[cid] = raw
            entries = extract_values(raw)
            if not entries:
                results.append({
                    'site': SITE['code'], 'concept_id': cid, 'concept_name': name,
                    'numPersons_achilles': np_,
                    'unit_concept_id': 0, 'unit_name': 'NO_DATA',
                    'count': 0, 'min': '', 'p10': '', 'p25': '',
                    'median': '', 'p75': '', 'p90': '', 'max': '',
                })
            else:
                for e in entries:
                    row = {'site': SITE['code'], 'concept_id': cid, 'concept_name': name,
                           'numPersons_achilles': np_}
                    row.update(e)
                    results.append(row)
        except Exception as e:
            errors.append((cid, name, str(e)[:120]))
            results.append({
                'site': SITE['code'], 'concept_id': cid, 'concept_name': name,
                'numPersons_achilles': np_,
                'unit_concept_id': 0, 'unit_name': 'ERROR',
                'count': 0, 'min': '', 'p10': '', 'p25': '',
                'median': '', 'p75': '', 'p90': '', 'max': str(e)[:80],
            })

        if i % 25 == 0 or i == len(concepts):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed else 0
            eta = (len(concepts) - i) / rate / 60 if rate else 0
            print(f"  [{i}/{len(concepts)}] {cid} ({name[:40]}) "
                  f"persons={np_} | {elapsed:.0f}s elapsed, ~{eta:.1f}min ETA, "
                  f"{len(results)} rows, {len(errors)} errors")

        if i % args.save_every == 0:
            save_csv(results, OUTPUT_PATH)

        time.sleep(args.sleep)

    save_csv(results, OUTPUT_PATH)
    print(f"\nDone. {len(results)} rows → {OUTPUT_PATH}")
    print(f"Errors: {len(errors)}")
    if errors[:5]:
        for cid, name, msg in errors[:5]:
            print(f"  {cid} ({name[:40]}): {msg}")

    if not args.no_raw:
        with open(RAW_PATH, 'w', encoding='utf-8') as f:
            json.dump(raw_results, f, ensure_ascii=False)
        size_mb = os.path.getsize(RAW_PATH) / 1024 / 1024
        print(f"Raw JSON ({size_mb:.1f} MB) → {RAW_PATH}")


if __name__ == '__main__':
    main()
