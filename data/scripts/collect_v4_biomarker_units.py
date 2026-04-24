"""
v4 biomarker 후보 10 concept × 24 site 단위 전수조사

Target concepts (추가 7 biomarker = 10 concept, multi-concept 포함):
- HbA1c     3004410
- LDL       3028437
- HDL       3007070
- UA_a      3037556
- UA_b      3000285        (multi-concept 후보)
- eGFR_a    40771922
- eGFR_b    3036277         (multi-concept 후보)
- GGT_a     3026910
- GGT_b     3013721         (multi-concept 후보)
- ALP       3035995

Usage:
    python collect_v4_biomarker_units.py --email YOUR_EMAIL --password YOUR_PW
    python collect_v4_biomarker_units.py --bearer "eyJhbG..."
"""
import csv
import json
import os
import sys
import time
import argparse
import functools
# Force stdout unbuffered
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..')
OUTPUT_PATH = os.path.join(DATA_DIR, 'measurement', 'v4_surveys', 'biomarker_unit_survey.csv')
RAW_PATH = os.path.join(DATA_DIR, 'measurement', 'raw_drilldown', 'v4_biomarker.json')

TARGET_CONCEPTS = [
    ('3004410',  'HbA1c',  '%'),
    ('3028437',  'LDL',    'mg/dL'),
    ('3007070',  'HDL',    'mg/dL'),
    ('3037556',  'UA_a',   'mg/dL'),
    ('3000285',  'UA_b',   'mg/dL'),
    ('40771922', 'eGFR_a', 'mL/min/1.73m2'),
    ('3036277',  'eGFR_b', 'mL/min/1.73m2'),
    ('3026910',  'GGT_a',  'U/L'),
    ('3013721',  'GGT_b',  'U/L'),
    ('3035995',  'ALP',    'U/L'),
]

# source_key_mapping.csv 기준 24 기관 (sourceKey != cdmName 주의!)
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


def collect_drilldown(client, concept_id, source_key):
    """Achilles drilldown의 recordsByUnit에서 unit 분포 추출"""
    try:
        data = client.get_achilles_drilldown(source_key, 'measurement', int(concept_id))
        units = []
        num_persons = 0
        if isinstance(data, dict):
            # recordsByUnit: unit_concept_id + unit_name + count (정확한 unit 데이터)
            if 'recordsByUnit' in data and data['recordsByUnit']:
                for item in data['recordsByUnit']:
                    units.append({
                        'unit_concept_id': item.get('conceptId', 0),
                        'unit': item.get('conceptName', 'unknown'),
                        'count': item.get('countValue', 0),
                    })
            if 'ageAtFirstOccurrence' in data and data['ageAtFirstOccurrence']:
                num_persons = sum(item.get('countValue', 0) for item in data['ageAtFirstOccurrence'])
        return {'raw': data, 'units': units, 'num_persons': num_persons, 'error': None}
    except Exception as e:
        return {'error': str(e), 'units': [], 'num_persons': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email')
    parser.add_argument('--password')
    parser.add_argument('--bearer')
    parser.add_argument('--sites', nargs='*', help='Specific site codes')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    target_sites = SITES
    if args.sites:
        target_sites = [s for s in SITES if s['code'] in args.sites]

    n_calls = len(TARGET_CONCEPTS) * len(target_sites)
    print(f"Concepts: {len(TARGET_CONCEPTS)}, Sites: {len(target_sites)}, Calls: {n_calls} (~{n_calls*0.5/60:.1f} min)")
    if args.dry_run:
        return

    client = FedernetClient()
    if args.bearer:
        client.login_with_bearer_token(args.bearer)
    elif args.email and args.password:
        if not client.login_portal(args.email, args.password):
            print("Login failed!")
            return
    else:
        print("Provide --email/--password or --bearer")
        return

    results = []
    raw_results = {}

    for si, site in enumerate(target_sites):
        print(f"[{si+1}/{len(target_sites)}] {site['code']} connecting...")
        if not client.connect_site(group_id=site['group_id'], site_id=site['site_id']):
            print(f"  SKIP: connect failed")
            continue
        print(f"  connected, querying {len(TARGET_CONCEPTS)} concepts...")
        for cid, bm_name, expected_unit in TARGET_CONCEPTS:
            result = collect_drilldown(client, cid, site['sourceKey'])
            if result.get('error'):
                print(f"    {bm_name} ({cid}): ERR {result['error'][:80]}")
                continue
            n_units = len(result['units'])
            print(f"    {bm_name} ({cid}): {n_units} unit entries, {result['num_persons']} persons")
            raw_results[f"{site['code']}_{cid}"] = result['raw']
            if result['units']:
                for u in result['units']:
                    results.append({
                        'site': site['code'], 'concept_id': cid, 'biomarker': bm_name,
                        'expected_unit': expected_unit,
                        'unit_concept_id': u.get('unit_concept_id', 0),
                        'actual_unit': u['unit'],
                        'count': u['count'], 'num_persons': result['num_persons'],
                    })
            else:
                results.append({
                    'site': site['code'], 'concept_id': cid, 'biomarker': bm_name,
                    'expected_unit': expected_unit, 'unit_concept_id': 0,
                    'actual_unit': 'NO_DATA',
                    'count': 0, 'num_persons': result['num_persons'],
                })
            time.sleep(0.3)

    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'site', 'concept_id', 'biomarker', 'expected_unit',
            'unit_concept_id', 'actual_unit', 'count', 'num_persons'
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nSaved {len(results)} rows -> {OUTPUT_PATH}")

    with open(RAW_PATH, 'w', encoding='utf-8') as f:
        json.dump(raw_results, f, indent=2, ensure_ascii=False)
    print(f"Raw -> {RAW_PATH}")


if __name__ == '__main__':
    main()
