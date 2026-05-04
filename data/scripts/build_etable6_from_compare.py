"""
eTable 6: LOSO stability table — built from compare_15vs16site_long.csv
(15-site β analysis LOSO summary, originally extracted from adam machine).

Source: studies/appendectomy/compare_15vs16site_long.csv (Drive-synced subset
of adam's v4_1_15site_beta_primary LOSO output).

Use this when full LOSO re-run on data1 is impractically slow. Once data1
LOSO completes, build_etable6_loso.py provides cross-validation (expected
to match within rounding given primary β bit-for-bit reproduction confirmed
2026-05-05).
"""
import csv
import re
from pathlib import Path

SRC = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\compare_15vs16site_long.csv')
OUT_CSV = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable6_loso_stability_v3.csv')

LOSO_TOTAL = 15

# Internal name mapping (matches build_etable4 / build_etable6_loso convention)
INDICATOR_TO_INTERNAL = {
    'WBC': 'WBC_high',
    'Lymphocyte % (low)': 'Lympho_pct_low', 'Lymphocyte % (elevated)': 'Lympho_pct_high',
    'Monocyte %': 'Mono_high', 'Basophil %': 'Baso_pct_high',
    'MCV (low)': 'MCV_low', 'MCV (elevated)': 'MCV_high',
    'RDW': 'RDW_high',
    'Platelet count (low)': 'Platelet_low', 'Platelet count (elevated)': 'Platelet_high',
    'ALT': 'ALT_high', 'AST': 'AST_high', 'Alkaline phosphatase': 'ALP_high',
    'Total bilirubin': 'TotBili_high', 'Albumin': 'Albumin_low',
    'HbA1c': 'HbA1c_high', 'LDL cholesterol': 'LDL_high',
    'Triglycerides': 'TG_high', 'Total cholesterol': 'TC_high',
    'Glucose, diabetic range': 'GlucDM', 'Glucose, prediabetic range': 'GlucPreDM',
    'Total protein (low)': 'TotProt_low', 'Total protein (elevated)': 'TotProt_high',
    'Blood urea nitrogen': 'BUN_high',
    'TSH (low)': 'TSH_low', 'TSH (elevated)': 'TSH_high',
    'Vitamin D': 'VitD_low',
    'CRP': 'CRP', 'Neutrophilia (any)': 'Neutrophilia_any', 'Eosinophilia (any)': 'Eosinophilia_any',
    # clinical
    'Ulcerative colitis': 'UC', 'Crohn disease': 'CD', 'Asthma': 'Asthma',
    'Atopic dermatitis': 'AD', 'Rheumatoid arthritis': 'RA',
    'C. difficile': 'CDI', 'Parkinson disease': 'PD', 'Biliary calculus': 'BilCalc',
    'Colorectal cancer': 'CRC', 'Acute MI': 'AMI', 'Type-2 diabetes': 'T2DM',
}


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_ci(ci_str):
    """'(0.14–0.21)' → (0.14, 0.21)."""
    if not ci_str:
        return None, None
    m = re.match(r'\s*\(?\s*([\d.]+)\s*[–\-]\s*([\d.]+)\s*\)?\s*', ci_str)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def parse_loso_count(s):
    """'15/15' → (15, 15)."""
    if not s:
        return None, None
    m = re.match(r'\s*(\d+)\s*/\s*(\d+)\s*', s)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def parse_loso_range(s):
    """'0.16–0.18' → (0.16, 0.18)."""
    if not s:
        return None, None
    m = re.match(r'\s*([\d.]+)\s*[–\-]\s*([\d.]+)\s*', s)
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))


def parse_p(p_str):
    """'<.001' or '0.045' → 0.0005 or 0.045."""
    if not p_str:
        return None
    s = p_str.strip()
    if s.startswith('<'):
        v = f(s[1:])
        return v / 2 if v else None  # treat <.001 as 0.0005 (won't matter for sig check)
    return f(s)


def main():
    out_rows = []
    with open(SRC, encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            comp_full = r['comparator']  # 'vs Cholecystectomy' / 'vs Hernia repair'
            if 'Chole' in comp_full:
                comp = 'Chole'
            elif 'Hernia' in comp_full:
                comp = 'Hernia'
            else:
                continue
            kind = r['kind'].lower()  # 'biomarker' / 'clinical'
            indicator = r['indicator']
            internal = INDICATOR_TO_INTERNAL.get(indicator, indicator)

            cal_hr = f(r['calHr_15'])
            ci_lb, ci_ub = parse_ci(r['calCi_15'])
            cal_p = parse_p(r['calP_15'])
            sig = (ci_lb is not None and ci_ub is not None and (ci_ub < 1.0 or ci_lb > 1.0))

            sig_count, total = parse_loso_count(r['loso_15_15'])
            hr_min, hr_max = parse_loso_range(r['loso_hr_range_15'])
            hr_range = (hr_max - hr_min) if (hr_min is not None and hr_max is not None) else None

            if total is None:
                total = LOSO_TOTAL
            if sig_count == LOSO_TOTAL and sig:
                rclass = 'core'
            elif sig and sig_count is not None and sig_count >= LOSO_TOTAL - 1:
                rclass = 'near-core'
            elif sig:
                rclass = 'partial'
            else:
                rclass = 'main_NS'

            out_rows.append({
                'outcomeName': internal,
                'kind': kind,
                'comparator': comp,
                'main_calHr': f'{cal_hr:.3f}' if cal_hr is not None else '',
                'main_sig': 1 if sig else 0,
                'loso_chr_min': f'{hr_min:.3f}' if hr_min is not None else '',
                'loso_chr_max': f'{hr_max:.3f}' if hr_max is not None else '',
                'loso_chr_range': f'{hr_range:.3f}' if hr_range is not None else '',
                'loso_sig_count': sig_count if sig_count is not None else '',
                'loso_total': total,
                'robust_class': rclass,
            })

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

    # Summary by stratum
    print()
    print(f'{"stratum":<25} {"main_sig":>10} {"15/15":>8} {"≥14/15":>8}')
    for kind in ('biomarker', 'clinical'):
        for comp in ('Chole', 'Hernia'):
            sub = [r for r in out_rows if r['kind'] == kind and r['comparator'] == comp]
            n_main = sum(1 for r in sub if r['main_sig'])
            n_15 = sum(1 for r in sub if r['robust_class'] == 'core')
            n_14 = sum(1 for r in sub if r['robust_class'] in ('core', 'near-core'))
            print(f'{comp+" "+kind:<25} {n_main:>10} {n_15:>8} {n_14:>8}')

    # Cross-comparator core (biomarker, both 15/15, same direction = protective)
    chole_bio = {r['outcomeName']: r for r in out_rows
                 if r['kind'] == 'biomarker' and r['comparator'] == 'Chole'}
    hernia_bio = {r['outcomeName']: r for r in out_rows
                  if r['kind'] == 'biomarker' and r['comparator'] == 'Hernia'}
    both_15 = [n for n in chole_bio if n in hernia_bio
               and chole_bio[n]['robust_class'] == 'core'
               and hernia_bio[n]['robust_class'] == 'core']
    protective_core = [n for n in both_15
                       if float(chole_bio[n]['main_calHr']) < 1
                       and float(hernia_bio[n]['main_calHr']) < 1]
    discordant = [n for n in both_15 if n not in protective_core]
    print(f'\nCross-comparator LOSO 15/15 BOTH (any direction): {len(both_15)}')
    print(f'  protective (HR<1 both, paper "5-endpoint core"): {len(protective_core)}')
    for n in sorted(protective_core):
        cHR = float(chole_bio[n]['main_calHr']); hHR = float(hernia_bio[n]['main_calHr'])
        print(f'    {n:<25}  chole {cHR:.2f} / hernia {hHR:.2f}')
    if discordant:
        print(f'  comparator-discordant (direction flip): {len(discordant)}')
        for n in sorted(discordant):
            cHR = float(chole_bio[n]['main_calHr']); hHR = float(hernia_bio[n]['main_calHr'])
            print(f'    {n:<25}  chole {cHR:.2f} / hernia {hHR:.2f}')


if __name__ == '__main__':
    main()
