"""
v4 확장 11 concept Achilles value survey (Tier 1 6 + Tier 2 4 + BUN 1)

Pipeline:
- Step 1: Vocabulary verification (concept name)
- Step 3: recordsByUnit (unit distribution)
- Step 4: measurementValueDistribution (value stats per unit)

Step 2 (multi-concept)는 별도 search 스크립트로.
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

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUTPUT_PATH = os.path.join(DATA_DIR, 'measurement', 'v4_surveys', 'extension11_value_survey.csv')
RAW_PATH = os.path.join(DATA_DIR, 'measurement', 'raw_drilldown', 'v4_extension11.json')
VOCAB_PATH = os.path.join(DATA_DIR, 'v4_extension11_vocab_check.csv')

# 확장 11 concept (ID는 추정 — Step 1 vocab check으로 검증)
CONCEPTS = [
    (3007461,  'Platelet',     'thou/uL',       'Tier1'),
    (3015242,  'Ferritin',     'ng/mL',         'Tier1'),
    (3024128,  'TotBili',      'mg/dL',         'Tier1'),
    (3002385,  'RDW',          '%|fL',          'Tier1'),  # 기존에 Mono#로 잘못 매핑돼 있던 것
    (3019577,  'TSH',          'mIU/L',         'Tier1'),
    (3010137,  'VitD_a',       'ng/mL',         'Tier1'),
    (3029187,  'VitD_b',       'ng/mL',         'Tier1'),  # alt
    (3023314,  'Hct',          '%',             'Tier2'),
    (3024731,  'MCV',          'fL',            'Tier2'),
    (3016723,  'Creatinine',   'mg/dL',         'Tier2'),
    (3020630,  'TotProtein',   'g/dL',          'Tier2'),
    (3013682,  'BUN',          'mg/dL',         'Kidney'),
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
    {'code': 'WKUH', 'group_id': 13,  'site_id': 188, 'sourceKey': 'cdmpv53_251126'},
]


def extract_values(raw):
    out = []
    if not isinstance(raw, dict): return out
    unit_counts = {}
    for u in raw.get('recordsByUnit', []) or []:
        unit_counts[u.get('conceptName', '?')] = {
            'unit_concept_id': u.get('conceptId', 0),
            'count': u.get('countValue', 0),
        }
    for d in raw.get('measurementValueDistribution', []) or []:
        unit = d.get('category', '?')
        meta = unit_counts.get(unit, {'unit_concept_id': 0, 'count': 0})
        out.append({
            'unit_concept_id': meta['unit_concept_id'], 'unit_name': unit,
            'count': meta['count'],
            'min': d.get('minValue'), 'p10': d.get('p10Value'),
            'p25': d.get('p25Value'), 'median': d.get('medianValue'),
            'p75': d.get('p75Value'), 'p90': d.get('p90Value'),
            'max': d.get('maxValue'),
        })
    mvd_units = {d.get('category') for d in raw.get('measurementValueDistribution', []) or []}
    for unit, meta in unit_counts.items():
        if unit not in mvd_units:
            out.append({
                'unit_concept_id': meta['unit_concept_id'], 'unit_name': unit,
                'count': meta['count'],
                'min': None, 'p10': None, 'p25': None, 'median': None,
                'p75': None, 'p90': None, 'max': None,
            })
    return out


def step1_vocab(client):
    """Step 1: vocabulary verification via /vocabulary/concept/{id}"""
    print("\n=== Step 1: Vocabulary verification ===")
    client.connect_site(group_id=7, site_id=203)  # KHNMC for vocab query
    results = []
    for cid, bm, unit, tier in CONCEPTS:
        try:
            r = client.session.get(
                f'https://www.feedernet.com/api/v1/atlas/7/203/vocabulary/concept/{cid}', timeout=30)
            if r.status_code == 200:
                d = r.json()
                name = d.get('CONCEPT_NAME', '?')
                domain = d.get('DOMAIN_ID', '?')
                vocab = d.get('VOCABULARY_ID', '?')
                std = d.get('STANDARD_CONCEPT', '?')
                bm_core = bm.split('_')[0].lower()
                # crude match check
                match = bm_core in name.lower()
                # special cases
                if bm == 'VitD_a' or bm == 'VitD_b':
                    match = 'vitamin d' in name.lower() or 'hydroxyvitamin' in name.lower() or '25-oh' in name.lower()
                if bm == 'Platelet':
                    match = 'platelet' in name.lower()
                if bm == 'TotBili':
                    match = 'bilirubin' in name.lower()
                if bm == 'Hct':
                    match = 'hematocrit' in name.lower()
                if bm == 'MCV':
                    match = 'mcv' in name.lower() or ('erythrocyte' in name.lower() and 'volume' in name.lower())
                if bm == 'TotProtein':
                    match = 'total protein' in name.lower() or 'protein' in name.lower()
                if bm == 'BUN':
                    match = 'urea' in name.lower()
                if bm == 'RDW':
                    match = 'distribution width' in name.lower()
                status = 'OK' if match else 'MISMATCH'
                results.append({'concept_id': cid, 'claimed': bm, 'actual_name': name,
                               'domain': domain, 'vocab': vocab, 'standard': std, 'tier': tier,
                               'match_status': status})
                print(f'  {status:10} {bm:12} {cid:10} [{domain}/{vocab}/{std}]  {name[:75]}')
        except Exception as e:
            results.append({'concept_id': cid, 'claimed': bm, 'actual_name': f'ERR:{e}',
                           'domain': '?', 'vocab': '?', 'standard': '?', 'tier': tier,
                           'match_status': 'ERROR'})
    with open(VOCAB_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['concept_id', 'claimed', 'actual_name',
                                                'domain', 'vocab', 'standard', 'tier', 'match_status'])
        writer.writeheader()
        writer.writerows(results)
    print(f"  Saved vocab check -> {VOCAB_PATH}")
    return results


def step3_4_drilldown(client):
    """Step 3+4: drilldown for unit and value distribution across all sites"""
    print("\n=== Step 3+4: Drilldown (unit + value distribution) ===")
    results = []
    raw_results = {}
    for si, site in enumerate(SITES):
        print(f"[{si+1}/{len(SITES)}] {site['code']}")
        if not client.connect_site(group_id=site['group_id'], site_id=site['site_id']):
            print(f"  SKIP: connect failed")
            continue
        for cid, bm_name, expected_unit, tier in CONCEPTS:
            try:
                raw = client.get_achilles_drilldown(site['sourceKey'], 'measurement', int(cid))
                raw_results[f"{site['code']}_{cid}"] = raw
                entries = extract_values(raw)
                if not entries:
                    results.append({
                        'site': site['code'], 'concept_id': cid, 'biomarker': bm_name,
                        'expected_unit': expected_unit, 'tier': tier,
                        'unit_concept_id': 0, 'unit_name': 'NO_DATA',
                        'count': 0, 'min': '', 'p10': '', 'p25': '',
                        'median': '', 'p75': '', 'p90': '', 'max': '',
                    })
                else:
                    for e in entries:
                        row = {'site': site['code'], 'concept_id': cid, 'biomarker': bm_name,
                               'expected_unit': expected_unit, 'tier': tier}
                        row.update(e)
                        results.append(row)
            except Exception:
                pass
            time.sleep(0.2)
        print(f"  done {len(CONCEPTS)} concepts")
    fields = ['site', 'concept_id', 'biomarker', 'expected_unit', 'tier',
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--password', required=True)
    args = parser.parse_args()

    c = FedernetClient()
    c.login_portal(args.email, args.password)

    step1_vocab(c)
    step3_4_drilldown(c)

    print("\n=== Done. Next: run biomarker_stability_summary.py ===")


if __name__ == '__main__':
    main()
