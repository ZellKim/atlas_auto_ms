"""
전 기관 measurement unit 전수조사 스크립트
ETRI 주요 lab test 143개 × 24개 기관 Achilles drilldown 수집

Usage:
    python collect_measurement_units.py --email YOUR_EMAIL --password YOUR_PW
    python collect_measurement_units.py --bearer "eyJhbG..."
"""
import csv
import json
import os
import sys
import time
import argparse

# atlas_auto 패키지 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..')
OUTPUT_PATH = os.path.join(DATA_DIR, 'measurement', 'unit_survey_full.csv')

# 기관 매핑 (site_id_mapping_full.csv 기반)
SITES = [
    {'code': 'AUMC',  'group_id': 9,   'site_id': 191, 'cdmName': 'AUMC_5.3.1_11'},
    {'code': 'CHNUH', 'group_id': 95,  'site_id': 227, 'cdmName': 'CHNUH_5.3.1_01'},
    {'code': 'DCMC',  'group_id': 16,  'site_id': 196, 'cdmName': 'DCMC_5.3.1_06'},
    {'code': 'DSMC',  'group_id': 103, 'site_id': 235, 'cdmName': 'DSMC_5.3.1_06'},
    {'code': 'EUMC',  'group_id': 5,   'site_id': 197, 'cdmName': 'EUMC_5.3.1_07'},
    {'code': 'GNUCH', 'group_id': 86,  'site_id': 224, 'cdmName': 'GNUCH_5.3.1_06'},
    {'code': 'GNUH',  'group_id': 88,  'site_id': 198, 'cdmName': 'GNUH_5.3.1_07'},
    {'code': 'HUMC',  'group_id': 117, 'site_id': 256, 'cdmName': 'HUMC_DONGTAN_5.3.1_04'},
    {'code': 'ISH',   'group_id': 81,  'site_id': 222, 'cdmName': 'ISH_5.3.1_05'},
    {'code': 'JCMJ',  'group_id': 93,  'site_id': 226, 'cdmName': 'JCMJ_5.3.1_04'},
    {'code': 'KCCH',  'group_id': 91,  'site_id': 225, 'cdmName': 'KCCH_5.3.1_05'},
    {'code': 'KDH',   'group_id': 4,   'site_id': 201, 'cdmName': 'KDH_5.3.1_08'},
    {'code': 'KHMC',  'group_id': 11,  'site_id': 202, 'cdmName': 'KHMC_5.3.1_07'},
    {'code': 'KHNMC', 'group_id': 7,   'site_id': 203, 'cdmName': 'KHNMC_5.3.1_08'},
    {'code': 'KWMC',  'group_id': 10,  'site_id': 213, 'cdmName': 'KWMC_5.3.1_09'},
    {'code': 'MJH',   'group_id': 67,  'site_id': 204, 'cdmName': 'MJH_5.3.1_06'},
    {'code': 'PNUH',  'group_id': 3,   'site_id': 190, 'cdmName': 'PNUH_5.3.0_04'},
    {'code': 'SCHBC', 'group_id': 29,  'site_id': 206, 'cdmName': 'SCHBC_5.3.1_03'},
    {'code': 'SCHCA', 'group_id': 28,  'site_id': 207, 'cdmName': 'SCHCA_5.3.3_03'},
    {'code': 'SCHGM', 'group_id': 30,  'site_id': 208, 'cdmName': 'SCHGM_5.3.3_03'},
    {'code': 'SCHSU', 'group_id': 27,  'site_id': 209, 'cdmName': 'SCHSU_5.3.3_03'},
    {'code': 'SEJONG','group_id': 119, 'site_id': 260, 'cdmName': 'SEJONG_5.3.1_01'},
    {'code': 'UUH',   'group_id': 99,  'site_id': 243, 'cdmName': 'UUH_5.3.0_04'},
    {'code': 'WKUH',  'group_id': 13,  'site_id': 188, 'cdmName': 'WKUH_5.3.1_07'},
]


def load_etri_concepts():
    """ETRI measurement list에서 numeric concept 추출"""
    etri_path = os.path.join(DATA_DIR, 'atlas_reference', 'etri_measurement_list.csv')
    concepts = {}
    with open(etri_path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            cid = r.get('target_concept_id_1', '').strip()
            var = r.get('var_nm', '').strip()
            unit = r.get('local_cd3', '').strip() if r.get('local_cd3') else ''
            name = r.get('concept_name', '').strip()
            if cid and cid not in concepts:
                concepts[cid] = {'var': var, 'expected_unit': unit, 'concept_name': name}
    return concepts


def collect_drilldown(client, site, concept_id, source_key):
    """단일 concept의 drilldown에서 unit 정보 추출"""
    try:
        data = client.get_achilles_drilldown(source_key, 'measurement', int(concept_id))
        # drilldown 응답에서 unit 분포 추출
        units = []
        if isinstance(data, dict):
            # valuesRelativeToNorm 또는 measurementValueDistribution에서 unit 추출
            for key in ['valuesRelativeToNorm', 'measurementValueDistribution']:
                if key in data and data[key]:
                    for item in data[key]:
                        unit_name = item.get('category', item.get('conceptName', 'unknown'))
                        count = item.get('countValue', item.get('count', 0))
                        units.append({'unit': unit_name, 'count': count})

            # ageAtFirstOccurrence 등에서 numPersons 추출
            num_persons = 0
            if 'ageAtFirstOccurrence' in data and data['ageAtFirstOccurrence']:
                num_persons = sum(item.get('countValue', 0) for item in data['ageAtFirstOccurrence'])

            # prevalenceByGenderAgeYear에서도 확인
            if not units and 'prevalenceByGenderAgeYear' in data:
                pass  # unit 없는 경우

            return {
                'raw': data,
                'units': units,
                'num_persons': num_persons,
            }
        return {'raw': data, 'units': [], 'num_persons': 0}
    except Exception as e:
        return {'error': str(e), 'units': [], 'num_persons': 0}


def main():
    parser = argparse.ArgumentParser(description='Measurement unit survey')
    parser.add_argument('--email', help='feedernet email')
    parser.add_argument('--password', help='feedernet password')
    parser.add_argument('--bearer', help='Bearer token')
    parser.add_argument('--sites', nargs='*', help='Specific site codes (default: all)')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without executing')
    args = parser.parse_args()

    concepts = load_etri_concepts()
    print(f"ETRI concepts loaded: {len(concepts)}")

    target_sites = SITES
    if args.sites:
        target_sites = [s for s in SITES if s['code'] in args.sites]
    print(f"Target sites: {len(target_sites)}")

    total_calls = len(concepts) * len(target_sites)
    print(f"Total API calls: {total_calls} (est. {total_calls * 0.5 / 60:.0f} min)")

    if args.dry_run:
        print("\n[DRY RUN] Exiting.")
        return

    # Login
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

    # Collect
    results = []
    raw_results = {}

    for si, site in enumerate(target_sites):
        print(f"\n[{si+1}/{len(target_sites)}] {site['code']} (group={site['group_id']}, site={site['site_id']})")

        if not client.connect_site(group_id=site['group_id'], site_id=site['site_id']):
            print(f"  SKIP: connect failed")
            continue

        source_key = site['cdmName']

        for ci, (cid, info) in enumerate(concepts.items()):
            if ci % 20 == 0:
                print(f"  concept {ci+1}/{len(concepts)} ({info['var']})")

            result = collect_drilldown(client, site, cid, source_key)

            if result.get('error'):
                # concept이 이 기관에 없을 수 있음
                continue

            # Save raw for later analysis
            raw_key = f"{site['code']}_{cid}"
            raw_results[raw_key] = result['raw']

            if result['units']:
                for u in result['units']:
                    results.append({
                        'site': site['code'],
                        'concept_id': cid,
                        'var_nm': info['var'],
                        'expected_unit': info['expected_unit'],
                        'actual_unit': u['unit'],
                        'count': u['count'],
                        'num_persons': result['num_persons'],
                    })
            else:
                results.append({
                    'site': site['code'],
                    'concept_id': cid,
                    'var_nm': info['var'],
                    'expected_unit': info['expected_unit'],
                    'actual_unit': 'NO_DATA',
                    'count': 0,
                    'num_persons': result['num_persons'],
                })

            time.sleep(0.3)  # rate limit

    # Save CSV
    print(f"\nSaving {len(results)} rows to {OUTPUT_PATH}")
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'site', 'concept_id', 'var_nm', 'expected_unit',
            'actual_unit', 'count', 'num_persons'
        ])
        writer.writeheader()
        writer.writerows(results)

    # Save raw JSON for detailed analysis
    raw_path = os.path.join(DATA_DIR, 'measurement_drilldown_raw.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(raw_results, f, indent=2, ensure_ascii=False)
    print(f"Raw data saved to {raw_path}")

    # Summary
    print("\n=== SUMMARY ===")
    from collections import Counter
    site_issues = Counter()
    for r in results:
        if r['actual_unit'] in ('NO_DATA', 'No matching concept', ''):
            site_issues[r['site']] += 1
    for site, count in site_issues.most_common():
        print(f"  {site}: {count} concepts with no unit")


if __name__ == '__main__':
    main()
