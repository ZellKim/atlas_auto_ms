"""
v4 22 biomarker outcome × 23 site — 전수 value distribution 조사
(median/p25/p75/min/max per site per unit → mislabeling 검증)
"""
import csv
import json
import os
import sys
import time
import argparse
import functools
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..')
OUTPUT_PATH = os.path.join(DATA_DIR, 'measurement', 'v4_surveys', 'all_outcomes_value_survey.csv')
RAW_PATH = os.path.join(DATA_DIR, 'measurement', 'raw_drilldown', 'v4_all_outcomes.json')

# 22 outcome의 underlying measurement concept IDs (중복 제거)
# 확장해서 그룹별로 표기
CONCEPTS = [
    # v3 refined
    (3000905, 'WBC_a',   'thou/uL'),
    (3010813, 'WBC_b',   'thou/uL'),
    (3017732, 'Neutro_abs', 'thou/uL'),
    (3017354, 'Neutro_pct_a', '%'),
    (3018010, 'Neutro_pct_b', '%'),
    (3002385, 'Mono_a',  'thou/uL'),
    (3019069, 'Mono_b',  '%'),
    (3020460, 'CRP',     'mg/dL|mg/L'),
    (3004501, 'Glucose', 'mg/dL'),
    (3037110, 'GlucFast','mg/dL'),
    (3000963, 'Hgb',     'g/dL'),
    # v1 single
    (3004327, 'Lympho_a','thou/uL'),
    (3002030, 'Lympho_b','%'),
    (3013115, 'Eosino_a','thou/uL'),
    (3006504, 'Eosino_b','%'),
    (3037575, 'Baso_a',  'thou/uL'),
    (3022096, 'Baso_b',  '%'),
    (3013707, 'ESR_a',   'mm/hr'),
    (3015183, 'ESR_b',   'mm/hr'),
    (3022192, 'TG',      'mg/dL'),
    (3006923, 'ALT',     'U/L'),
    (3024561, 'Albumin', 'g/dL'),
    # v4 new
    (3004410, 'HbA1c',   '%'),
    (3028437, 'LDL',     'mg/dL'),
    (3007070, 'HDL',     'mg/dL'),
    (3037556, 'UA',      'mg/dL'),
    (3026910, 'GGT',     'U/L'),
    (3035995, 'ALP',     'U/L'),
    (3013721, 'AST',     'U/L'),
    (3027114, 'TC',      'mg/dL'),
]

SITES = [
    {'code': 'AUMC',  'group_id': 9,   'site_id': 191, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'CHNUH', 'group_id': 95,  'site_id': 227, 'sourceKey': 'cdm'},
    {'code': 'DCMC',  'group_id': 16,  'site_id': 196, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'DSMC',  'group_id': 103, 'site_id': 235, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'EUMC',  'group_id': 5,   'site_id': 197, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'GNUCH', 'group_id': 86,  'site_id': 224, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'GNUH',  'group_id': 88,  'site_id': 198, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'HUMC',  'group_id': 117, 'site_id': 256, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'ISH',   'group_id': 81,  'site_id': 222, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'JCMJ',  'group_id': 93,  'site_id': 226, 'sourceKey': 'cdmpv53_250317'},
    {'code': 'KCCH',  'group_id': 91,  'site_id': 225, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'KDH',   'group_id': 4,   'site_id': 201, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'KHMC',  'group_id': 11,  'site_id': 202, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'KHNMC', 'group_id': 7,   'site_id': 203, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'KWMC',  'group_id': 10,  'site_id': 213, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'MJH',   'group_id': 67,  'site_id': 204, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'PNUH',  'group_id': 3,   'site_id': 190, 'sourceKey': 'cdmpv53_251128'},
    {'code': 'SCHBC', 'group_id': 29,  'site_id': 206, 'sourceKey': 'cdmpv533'},
    {'code': 'SCHCA', 'group_id': 28,  'site_id': 207, 'sourceKey': 'cdmpv533'},
    {'code': 'SCHGM', 'group_id': 30,  'site_id': 208, 'sourceKey': 'cdmpv533'},
    {'code': 'SCHSU', 'group_id': 27,  'site_id': 209, 'sourceKey': 'cdmpv533'},
    {'code': 'UUH',   'group_id': 99,  'site_id': 243, 'sourceKey': 'cdm_0023'},
    {'code': 'WKUH',  'group_id': 13,  'site_id': 188, 'sourceKey': 'cdmpv53_251126'},
]


def extract_values(raw):
    """recordsByUnit (count per unit) + measurementValueDistribution (stats per unit)"""
    out = []
    if not isinstance(raw, dict): return out
    # Build {unit_name: count} from recordsByUnit
    unit_counts = {}
    for u in raw.get('recordsByUnit', []) or []:
        unit_counts[u.get('conceptName', '?')] = {
            'unit_concept_id': u.get('conceptId', 0),
            'count': u.get('countValue', 0),
        }
    # value dist per unit (mvd category = unit_name)
    for d in raw.get('measurementValueDistribution', []) or []:
        unit = d.get('category', '?')
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
    # units without mvd (count only)
    mvd_units = {d.get('category') for d in raw.get('measurementValueDistribution', []) or []}
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--sites', nargs='*')
    args = parser.parse_args()

    target_sites = SITES
    if args.sites:
        target_sites = [s for s in SITES if s['code'] in args.sites]
    n_calls = len(CONCEPTS) * len(target_sites)
    print(f"Concepts: {len(CONCEPTS)}, Sites: {len(target_sites)}, Calls: {n_calls} (~{n_calls*0.5/60:.1f} min)")

    c = FedernetClient()
    c.login_portal(args.email, args.password)

    results = []
    raw_results = {}

    for si, site in enumerate(target_sites):
        print(f"[{si+1}/{len(target_sites)}] {site['code']}")
        if not c.connect_site(group_id=site['group_id'], site_id=site['site_id']):
            print(f"  SKIP: connect failed")
            continue
        for cid, bm_name, expected_unit in CONCEPTS:
            try:
                raw = c.get_achilles_drilldown(site['sourceKey'], 'measurement', int(cid))
                raw_results[f"{site['code']}_{cid}"] = raw
                entries = extract_values(raw)
                if not entries:
                    results.append({
                        'site': site['code'], 'concept_id': cid, 'biomarker': bm_name,
                        'expected_unit': expected_unit,
                        'unit_concept_id': 0, 'unit_name': 'NO_DATA',
                        'count': 0, 'min': '', 'p10': '', 'p25': '',
                        'median': '', 'p75': '', 'p90': '', 'max': '',
                    })
                else:
                    for e in entries:
                        row = {
                            'site': site['code'], 'concept_id': cid, 'biomarker': bm_name,
                            'expected_unit': expected_unit,
                        }
                        row.update(e)
                        results.append(row)
            except Exception as e:
                pass
            time.sleep(0.2)
        print(f"  done {len(CONCEPTS)} concepts")

    fields = ['site', 'concept_id', 'biomarker', 'expected_unit',
              'unit_concept_id', 'unit_name', 'count',
              'min', 'p10', 'p25', 'median', 'p75', 'p90', 'max']
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved {len(results)} rows -> {OUTPUT_PATH}")

    with open(RAW_PATH, 'w', encoding='utf-8') as f:
        json.dump(raw_results, f, indent=2, ensure_ascii=False)
    print(f"Raw -> {RAW_PATH}")


if __name__ == '__main__':
    main()
