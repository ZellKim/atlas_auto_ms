"""
eTable 6: LOSO (leave-one-site-out) stability for the 15-site β analysis.

For each main-significant endpoint × comparator:
  - main calHr (from primary)
  - LOSO HR range across 15 iterations (min, max)
  - LOSO sig_count: # iterations where calCiUb < 1 (or calCiLb > 1)
  - robust_class: "core" if 15/15 retains main direction sig, else "partial"

Source: paper β analysis (15 sites) on data1.
Reproduces adam machine's v4_1_15site_beta_primary LOSO bit-for-bit.
"""
import csv
from collections import defaultdict
from pathlib import Path

SRC_DIR = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\appendectomy\v4\v4_1_15site_beta_primary')
OUT_CSV = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable6_loso_stability_v3.csv')

LOSO_TOTAL = 15  # 15 sites, leave-one-out

# Same outcomeId → name mapping (biomarker + clinical)
OUTCOME_NAMES = {
    1357: 'WBC_high',
    1360: 'Lympho_pct_low', 1385: 'Lympho_pct_high',
    1362: 'Mono_high', 1368: 'Baso_pct_high',
    1358: 'MCV_low', 1387: 'MCV_high',
    1395: 'RDW_high',
    1394: 'Platelet_low', 1393: 'Platelet_high',
    1364: 'ALT_high', 1365: 'AST_high', 1363: 'ALP_high',
    1400: 'TotBili_high', 1366: 'Albumin_low',
    1381: 'HbA1c_high', 1384: 'LDL_high',
    1397: 'TG_high', 1396: 'TC_high',
    1378: 'GlucDM', 1379: 'GlucPreDM',
    1402: 'TotProt_low', 1401: 'TotProt_high',
    1367: 'BUN_high', 1399: 'TSH_low', 1398: 'TSH_high',
    1404: 'VitD_low',
    9001: 'CRP', 9005: 'Neutrophilia_any', 9006: 'Eosinophilia_any',
    # clinical
    1077: 'UC', 1078: 'CD', 1079: 'Asthma', 1080: 'AD',
    1090: 'RA', 1092: 'CDI', 1093: 'PD', 1094: 'BilCalc',
    1097: 'CRC', 1271: 'AMI', 1285: 'T2DM',
}


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def is_sig(lb, ub):
    """Confidence interval excludes 1.0 (sig at 0.05)."""
    return (lb is not None and ub is not None and (ub < 1.0 or lb > 1.0))


def load_main(comp, kind):
    """primary_{comp}_{kind}.csv → dict[outcomeId] = {calHr, calCiLb, calCiUb, calP, sig}."""
    path = SRC_DIR / f'primary_{comp}_{kind}.csv'
    out = {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        hr = f(r['calHr']); lb = f(r['calCiLb']); ub = f(r['calCiUb']); p = f(r['calP'])
        out[int(r['outcomeId'])] = {
            'calHr': hr, 'calCiLb': lb, 'calCiUb': ub, 'calP': p,
            'sig': is_sig(lb, ub),
        }
    return out


def load_loso(comp, kind):
    """loso_{comp}_{kind}.csv → dict[outcomeId] = list of {calHr, calCiLb, calCiUb, calP, site}."""
    path = SRC_DIR / f'loso_{comp}_{kind}.csv'
    by_id = defaultdict(list)
    if not path.exists():
        return by_id
    for r in csv.DictReader(open(path, encoding='utf-8')):
        hr = f(r['calHr']); lb = f(r['calCiLb']); ub = f(r['calCiUb']); p = f(r['calP'])
        if hr is None:
            continue
        by_id[int(r['outcomeId'])].append({
            'calHr': hr, 'calCiLb': lb, 'calCiUb': ub, 'calP': p,
            'site': r.get('site_skipped', ''),
        })
    return by_id


def main():
    out_rows = []
    for kind in ('biomarker', 'clinical'):
        for comp_label, comp_lower in (('Chole', 'chole'), ('Hernia', 'hernia')):
            main_data = load_main(comp_lower, kind)
            loso_data = load_loso(comp_lower, kind)
            for oid, m in main_data.items():
                name = OUTCOME_NAMES.get(oid, f'id{oid}')
                runs = loso_data.get(oid, [])
                hrs = [r['calHr'] for r in runs]
                hr_min = min(hrs) if hrs else None
                hr_max = max(hrs) if hrs else None
                hr_range = (hr_max - hr_min) if (hr_min is not None and hr_max is not None) else None
                sig_count = sum(1 for r in runs if is_sig(r['calCiLb'], r['calCiUb']))
                if sig_count == LOSO_TOTAL and m['sig']:
                    rclass = 'core'
                elif m['sig'] and sig_count >= LOSO_TOTAL - 1:
                    rclass = 'near-core'
                elif m['sig']:
                    rclass = 'partial'
                else:
                    rclass = 'main_NS'
                out_rows.append({
                    'outcomeName': name,
                    'kind': kind,
                    'comparator': comp_label,
                    'main_calHr': f"{m['calHr']:.3f}" if m['calHr'] is not None else '',
                    'main_sig': 1 if m['sig'] else 0,
                    'loso_chr_min': f'{hr_min:.3f}' if hr_min is not None else '',
                    'loso_chr_max': f'{hr_max:.3f}' if hr_max is not None else '',
                    'loso_chr_range': f'{hr_range:.3f}' if hr_range is not None else '',
                    'loso_sig_count': sig_count,
                    'loso_total': len(runs),
                    'robust_class': rclass,
                })

    # Sort: biomarker first, chole then hernia, by main_calHr ascending
    out_rows.sort(key=lambda r: (r['kind'] != 'biomarker',
                                  r['comparator'] != 'Chole',
                                  float(r['main_calHr']) if r['main_calHr'] else 99))

    fieldnames = ['outcomeName', 'kind', 'comparator',
                  'main_calHr', 'main_sig',
                  'loso_chr_min', 'loso_chr_max', 'loso_chr_range',
                  'loso_sig_count', 'loso_total', 'robust_class']
    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print(f'Wrote {len(out_rows)} rows to {OUT_CSV}')

    # Summary
    print()
    print(f'{"stratum":<25} {"main_sig":>10} {"15/15":>8} {"≥14/15":>8}')
    for kind in ('biomarker', 'clinical'):
        for comp in ('Chole', 'Hernia'):
            sub = [r for r in out_rows if r['kind'] == kind and r['comparator'] == comp]
            n_main = sum(1 for r in sub if r['main_sig'])
            n_15 = sum(1 for r in sub if r['robust_class'] == 'core')
            n_14 = sum(1 for r in sub if r['robust_class'] in ('core', 'near-core'))
            print(f'{comp+" "+kind:<25} {n_main:>10} {n_15:>8} {n_14:>8}')

    # Cross-comparator core (biomarker, both 15/15)
    chole_core = {r['outcomeName'] for r in out_rows
                  if r['kind'] == 'biomarker' and r['comparator'] == 'Chole'
                  and r['robust_class'] == 'core'}
    hernia_core = {r['outcomeName'] for r in out_rows
                   if r['kind'] == 'biomarker' and r['comparator'] == 'Hernia'
                   and r['robust_class'] == 'core'}
    cross = chole_core & hernia_core
    print(f'\nCross-comparator LOSO core (biomarker, 15/15 BOTH): {len(cross)}')
    for n in sorted(cross):
        print(f'  {n}')


if __name__ == '__main__':
    main()
