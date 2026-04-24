"""
v4 biomarker stability summary (biomarker × site matrix)

각 biomarker별로 사이트가 어느 concept을 쓰는지 매핑 → v4 cohort 정의 시 multi-concept OR로 포괄.

Output:
- biomarker_site_concept_matrix.csv — 각 (biomarker, site) 쌍에 쓰인 concept + 값 범위 평가
- biomarker_stability_summary.csv — biomarker별 usable site 수 + INCLUDE 판정

판정 규칙:
- 사이트 usable = (alt concept 중 하나라도 count > 0) AND (주요 concept의 median이 관대한 임상 범위 내)
- INCLUDE (≥18 usable), CONDITIONAL (15-17), EXCLUDE (<15)
"""
import csv
import os
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT_MATRIX = os.path.join(DATA_DIR, 'biomarker_site_concept_matrix.csv')
OUT_SUMMARY = os.path.join(DATA_DIR, 'biomarker_stability_summary.csv')

# biomarker → [(concept_id, name)]: 각 biomarker의 모든 alt concept
BIOMARKER_CONCEPTS = {
    # CBC
    'WBC': [(3000905, 'WBC_auto'), (3010813, 'WBC_alt')],
    'Neutro': [(3017732, 'Neutro_abs'), (3017354, 'Neutro_pct_a'), (3018010, 'Neutro_pct_b')],
    'Lympho': [(3004327, 'Lympho_a'), (3002030, 'Lympho_b')],
    'Eosino': [(3013115, 'Eosino_a'), (3006504, 'Eosino_b')],
    'Mono': [(3002385, 'Mono_a'), (3019069, 'Mono_b')],
    'Baso': [(3037575, 'Baso_a'), (3022096, 'Baso_b')],
    'Hgb': [(3000963, 'Hgb'), (3027484, 'Hgb_alt')],
    'Hct': [(3023314, 'Hct_auto'), (3009542, 'Hct_generic')],
    'MCV': [(3024731, 'MCV')],
    'RDW': [(3002385, 'RDW')],  # NOTE: same ID as Mono_a (it's actually RDW)
    'Platelet': [(3007461, 'Platelet')],
    # 염증
    'CRP': [(3020460, 'CRP')],
    'ESR': [(3013707, 'ESR_a'), (3015183, 'ESR_b')],
    'Ferritin': [(3015242, 'Ferritin')],
    # 간
    'ALT': [(3006923, 'ALT')],
    'AST': [(3013721, 'AST')],
    'GGT': [(3026910, 'GGT')],
    'ALP': [(3035995, 'ALP')],
    'TotBili': [(3024128, 'TotBili')],
    'Albumin': [(3024561, 'Albumin')],
    'TotProtein': [(3020630, 'TotProtein')],
    # 대사
    'Glucose': [(3004501, 'Glucose'), (3037110, 'GlucFast')],
    'HbA1c': [(3004410, 'HbA1c')],
    'TG': [(3022192, 'TG')],
    'TC': [(3027114, 'TC')],
    'HDL': [(3007070, 'HDL')],
    'LDL': [(3028437, 'LDL')],
    # 신장
    'Creatinine': [(3016723, 'Creatinine')],
    'BUN': [(3013682, 'BUN')],
    'UA': [(3037556, 'UA')],
    # 내분비/면역
    'TSH': [(3009201, 'TSH')],
    'VitD': [(3020149, 'VitD_D3'), (40765040, 'VitD_total'), (42529187, 'VitD_totIA')],
}

# Concept ID → expected biomarker (reverse lookup)
# NOTE: 3002385 is ambiguous — appears as both Mono_a (wrong old mapping) and RDW (correct)
# For RDW biomarker, use it. For Mono biomarker, skip (it was wrong).
CONCEPT_TO_BIOMARKERS = defaultdict(list)
for bm, concepts in BIOMARKER_CONCEPTS.items():
    for cid, _ in concepts:
        CONCEPT_TO_BIOMARKERS[str(cid)].append(bm)

# 임상 reference median 범위 (관대하게 — unit 혼동 커버)
CLINICAL_RANGE = {
    'WBC':        (0.5, 50),      # thou/uL or /uL - mixed scales OK
    'Neutro':     (0, 100),       # # or %
    'Lympho':     (0, 100),
    'Eosino':     (0, 50),
    'Mono':       (0, 50),
    'Baso':       (0, 10),
    'Hgb':        (5, 25),
    'Hct':        (10, 70),
    'MCV':        (60, 130),
    'RDW':        (5, 30),
    'Platelet':   (10, 1000),
    'CRP':        (0, 500),       # mg/dL or mg/L — wide
    'ESR':        (0, 150),
    'Ferritin':   (1, 5000),
    'ALT':        (1, 500),
    'AST':        (1, 500),
    'GGT':        (1, 500),
    'ALP':        (10, 1000),
    'TotBili':    (0, 10),
    'Albumin':    (1, 8),
    'TotProtein': (2, 12),
    'Glucose':    (30, 500),
    'HbA1c':      (3, 20),
    'TG':         (10, 2000),
    'TC':         (50, 500),
    'HDL':        (5, 200),
    'LDL':        (10, 500),
    'Creatinine': (0.1, 15),
    'BUN':        (1, 150),
    'UA':         (0.5, 30),
    'TSH':        (0.01, 30),
    'VitD':       (1, 200),
}


def load_rows(path):
    if not os.path.exists(path):
        print(f'WARN: {path} not found')
        return []
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def load_achilles_frequency():
    """
    Achilles `data/concept_frequency/*_measurement.csv` 로드.
    한글 institution → English site code 매핑 (site_id_mapping_full.csv 기반).
    """
    import glob
    KOREAN_TO_CODE = {
        '아주대학교병원': 'AUMC', '충남대학교병원': 'CHNUH',
        '대구가톨릭대학교병원': 'DCMC', '대구카톨릭_kcd': 'DCMC',
        '동산병원': 'DSMC', '대구동산병원': 'DSMC',
        '이화의료원': 'EUMC', '이대목동': 'EUMC',
        '창원경상국립대학교병원': 'GNUCH',
        '경상국립대학교병원(진주,창원)': 'GNUH', '경상국립대학교병원': 'GNUH',
        '경상국립대_kcd': 'GNUH',
        '동탄성심병원': 'HUMC',
        '국제성모병원': 'ISH', '인천_국제성모': 'ISH', '인천': 'ISH',
        '제천명지병원': 'JCMJ',
        '원자력병원': 'KCCH',
        '강동성심병원': 'KDH',
        '경희의료원': 'KHMC', '경희의료원_kcd': 'KHMC',
        '강동경희대학교병원': 'KHNMC',
        '강원대학교병원': 'KWMC',
        '명지병원': 'MJH',
        '부산대학교병원': 'PNUH', '부산대_kcd': 'PNUH', '부산대': 'PNUH',
        '순천향대학교_부천병원': 'SCHBC',
        '순천향대학교_천안병원': 'SCHCA', '순천향천안': 'SCHCA',
        '순천향대학교_구미병원': 'SCHGM',
        '순천향대학교_서울병원': 'SCHSU',
        '울산대학교_병원': 'UUH', '울산대학교병원': 'UUH',
        '원광대학교병원': 'WKUH', '원광대_kcd': 'WKUH',
        '원주세브란스_kcd': 'WKUH',  # might be wrong, but add as alt
        '아주대_kcd': 'AUMC',
        '경희의료원1_kcd': 'KHMC', '경희의료원2_kcd': 'KHMC',
    }
    base = os.path.join(DATA_DIR, 'concept_frequency')
    site_counts = defaultdict(dict)
    for f in glob.glob(os.path.join(base, '*_measurement.csv')):
        site_raw = os.path.basename(f).replace('_measurement.csv', '')
        # English code first
        if site_raw.isascii() and site_raw.replace('_', '').isalnum():
            site = site_raw
        else:
            site = KOREAN_TO_CODE.get(site_raw)
            if not site:
                continue  # unknown Korean name
        with open(f, encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                cid = row.get('conceptId', '')
                try:
                    n = int(row.get('numPersons', 0) or 0)
                except ValueError:
                    n = 0
                if n > 0:
                    # accumulate (different Korean files for same site may coexist)
                    prev = site_counts[site].get(cid, 0)
                    site_counts[site][cid] = max(prev, n)
    return site_counts


def main():
    rows30 = load_rows(os.path.join(DATA_DIR, 'v4_all_outcomes_value_survey.csv'))
    rows11 = load_rows(os.path.join(DATA_DIR, 'v4_extension11_value_survey.csv'))
    rows_tv = load_rows(os.path.join(DATA_DIR, 'v4_tsh_vitd_survey.csv'))

    # Achilles frequency CSV 직접 로드 → availability 체크 (drilldown보다 신뢰 가능)
    achilles = load_achilles_frequency()
    print(f"Loaded Achilles freq: {len(achilles)} sites")

    # Wrong concept IDs from vocab check (Aspen IgG, fatty acid, NT-proBNP)
    EXCLUDE_CIDS = {'3019577', '3010137', '3029187'}
    all_rows = [r for r in (rows30 + rows11 + rows_tv)
                if r.get('concept_id', '') not in EXCLUDE_CIDS]

    # Aggregate per (site, concept_id): sum count, pick dominant unit/median
    site_concept_stats: dict = {}
    for r in all_rows:
        site = r.get('site', '')
        cid = r.get('concept_id', '')
        try:
            cnt = int(r.get('count', 0) or 0)
        except ValueError:
            cnt = 0
        if cnt == 0:
            continue
        key = (site, cid)
        cur = site_concept_stats.get(key, {'count': 0, 'median': None, 'unit': None})
        if cnt > cur.get('count', 0):
            try:
                med = float(r.get('median', '') or 'nan')
            except ValueError:
                med = None
            site_concept_stats[key] = {
                'count': cnt, 'median': med, 'unit': r.get('unit_name', '?')
            }

    # Build matrix: biomarker × site → used concept info
    all_sites = sorted({r.get('site', '') for r in all_rows if r.get('site', '')})
    matrix_rows = []
    bm_usable_sites = defaultdict(list)
    bm_unstable_sites = defaultdict(list)
    bm_nodata_sites = defaultdict(list)

    for bm, concepts in BIOMARKER_CONCEPTS.items():
        low, high = CLINICAL_RANGE.get(bm, (0, 1e9))
        # RDW special case: cid 3002385 shared with Mono (wrong old mapping)
        # We map 3002385 → RDW only (not Mono)
        if bm == 'Mono':
            concept_ids = [cid for cid, _ in concepts if cid != 3002385]
        else:
            concept_ids = [cid for cid, _ in concepts]

        for site in all_sites:
            # Find which concept this site uses (highest count)
            # Primary: Achilles frequency CSV (most reliable)
            # Fallback: drilldown survey
            best_cid, best_cnt, best_med, best_unit = None, 0, None, None
            for cid in concept_ids:
                # Prefer Achilles freq count
                achilles_cnt = achilles.get(site, {}).get(str(cid), 0)
                stats = site_concept_stats.get((site, str(cid)), {'count': 0, 'median': None, 'unit': None})
                effective_cnt = max(achilles_cnt, stats.get('count', 0) or 0)
                if effective_cnt > best_cnt:
                    best_cid = cid
                    best_cnt = effective_cnt
                    best_med = stats.get('median')
                    best_unit = stats.get('unit') or 'Achilles-only'

            # Classify
            # USABLE = count > 0 (has data at site)
            # UNSTABLE (참고용) = count > 0 but median way out of 10x range (unit/concept mislabel suspect)
            # NO_DATA = count == 0
            if best_cnt == 0:
                status = 'NO_DATA'
                bm_nodata_sites[bm].append(site)
            else:
                # 모든 데이터 있으면 usable로 간주
                bm_usable_sites[bm].append(site)
                # 추가 flag: median이 임상 10배 범위도 벗어나면 의심
                mislabel_suspect = (best_med is not None and
                                    (best_med < low * 0.1 or best_med > high * 10))
                if mislabel_suspect:
                    bm_unstable_sites[bm].append((site, best_med or 0.0, best_unit or '?'))
                    status = 'USABLE_BUT_MISLABEL_SUSPECT'
                else:
                    status = 'USABLE'

            matrix_rows.append({
                'biomarker': bm, 'site': site,
                'used_concept_id': best_cid or '',
                'count': best_cnt,
                'median': best_med if best_med is not None else '',
                'unit': best_unit or '',
                'status': status,
            })

    # Save matrix
    with open(OUT_MATRIX, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['biomarker', 'site', 'used_concept_id',
                                            'count', 'median', 'unit', 'status'])
        w.writeheader()
        w.writerows(matrix_rows)

    # Summary
    summary_rows = []
    for bm in sorted(BIOMARKER_CONCEPTS):
        n_usable = len(bm_usable_sites[bm])
        n_unstable = len(bm_unstable_sites[bm])
        n_nodata = len(bm_nodata_sites[bm])
        total = n_usable + n_unstable + n_nodata
        if n_usable >= 18:
            decision = 'INCLUDE'
        elif n_usable >= 15:
            decision = 'CONDITIONAL'
        else:
            decision = 'EXCLUDE'
        summary_rows.append({
            'biomarker': bm,
            'n_usable': n_usable,
            'n_unstable': n_unstable,
            'n_nodata': n_nodata,
            'n_total': total,
            'decision': decision,
            'unstable_detail': '; '.join(f'{s}(med={m:.1f})' for s, m, _ in bm_unstable_sites[bm][:5])
                              + (f'...+{n_unstable-5}' if n_unstable > 5 else ''),
        })

    with open(OUT_SUMMARY, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['biomarker', 'n_usable', 'n_unstable',
                                            'n_nodata', 'n_total', 'decision', 'unstable_detail'])
        w.writeheader()
        w.writerows(summary_rows)

    print(f"Saved matrix: {OUT_MATRIX}")
    print(f"Saved summary: {OUT_SUMMARY}")
    print()
    print(f"{'biomarker':15} {'usable':>6} {'unstable':>8} {'nodata':>6}  decision")
    print('-' * 60)
    for r in summary_rows:
        print(f"{r['biomarker']:15} {r['n_usable']:>6} {r['n_unstable']:>8} "
              f"{r['n_nodata']:>6}  {r['decision']}")


if __name__ == '__main__':
    main()
