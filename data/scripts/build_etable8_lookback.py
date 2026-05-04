"""
eTable 8: lookback (prior-outcome filter) sensitivity.

Compare 90d / 365d (main β) / unlimited Full-Union lookback (skip 30d inner)
for each biomarker endpoint × comparator.

Source: paper β analysis (15 sites, Full-Union 365-30 + 90/unlimited variants) on data1.
Reproduces adam machine's v4_1_15site_beta_primary lookback grid bit-for-bit
(verified 2026-05-05: matched 15681/13225/5086/8732/7151/2625
 + sig 25/23/22/14/16/16 — 5/6 exact match with paper, 1 off-by-one).
"""
import csv
from pathlib import Path

SRC_DIR = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\appendectomy\v4\v4_1_15site_beta_primary')
OUT_CSV = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable8_lookback_sensitivity.csv')

LOOKBACKS = ('90d', '365d', 'unlimited')

# Same outcomeId → name mapping as build_etable4
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
}

LABEL = {
    'WBC_high': 'WBC',
    'Neutrophilia_any': 'Neutrophilia (any indicator)',
    'Eosinophilia_any': 'Eosinophilia (any indicator)',
    'Mono_high': 'Monocyte %', 'Baso_pct_high': 'Basophil %',
    'CRP': 'CRP', 'AST_high': 'AST', 'ALT_high': 'ALT', 'ALP_high': 'ALP',
    'TotBili_high': 'Total bilirubin', 'Albumin_low': 'Albumin',
    'HbA1c_high': 'HbA1c', 'VitD_low': 'Vitamin D', 'RDW_high': 'RDW',
    'BUN_high': 'BUN', 'TG_high': 'Triglycerides',
    'LDL_high': 'LDL cholesterol', 'TC_high': 'Total cholesterol',
    'Lympho_pct_low': 'Lymphocyte % (low)', 'Lympho_pct_high': 'Lymphocyte % (elevated)',
    'TotProt_low': 'Total protein (low)', 'TotProt_high': 'Total protein (elevated)',
    'TSH_low': 'TSH (low)', 'TSH_high': 'TSH (elevated)',
    'MCV_low': 'MCV (low)', 'MCV_high': 'MCV (elevated)',
    'Platelet_low': 'Platelet (low)', 'Platelet_high': 'Platelet (elevated)',
    'GlucDM': 'Glucose, diabetic range', 'GlucPreDM': 'Glucose, prediabetic range',
}


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fmt_hr(hr, lb, ub):
    if hr is None or lb is None or ub is None:
        return ''
    return f'{hr:.2f} ({lb:.2f}–{ub:.2f})'


def fmt_p(p):
    if p is None:
        return ''
    if p < 1e-4:
        return f'{p:.2e}'
    if p < 0.01:
        return f'{p:.4f}'
    return f'{p:.3f}'


def load_lookback(comp, lb):
    """Load one lookback CSV → dict[outcomeName] = row."""
    path = SRC_DIR / f'lookback_grid_{comp.lower()}_{lb}_primary.csv'
    by_name = {}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        oid = int(r['outcomeId'])
        name = OUTCOME_NAMES.get(oid)
        if name is None:
            continue
        by_name[name] = r
    return by_name


def main():
    # Load all 6 lookback runs
    data = {}  # data[(comp, lb)] = dict[outcomeName] = row
    for comp in ('Chole', 'Hernia'):
        for lb in LOOKBACKS:
            data[(comp, lb)] = load_lookback(comp, lb)

    # Endpoint order: matches build_etable4 (alphabetical-ish by display name)
    endpoints = sorted(set(LABEL.keys()),
                       key=lambda k: LABEL[k].replace(' (low)', ' a').replace(' (elevated)', ' b'))

    out_rows = []
    for ep in endpoints:
        for comp in ('Chole', 'Hernia'):
            row = {
                'Endpoint': LABEL[ep],
                'Comparator': comp,
            }
            for lb in LOOKBACKS:
                r = data[(comp, lb)].get(ep, {})
                hr = fmt_hr(f(r.get('calHr')), f(r.get('calCiLb')), f(r.get('calCiUb')))
                p = fmt_p(f(r.get('calP')))
                ev = f"{r.get('evT', '')}/{r.get('evC', '')}" if r else ''
                nT = r.get('nT', '') if r else ''
                row[f'{lb} nT'] = nT
                row[f'{lb} events T/C'] = ev
                row[f'{lb} cal HR (95% CI)'] = hr
                row[f'{lb} cal P'] = p
            out_rows.append(row)

    fieldnames = ['Endpoint', 'Comparator']
    for lb in LOOKBACKS:
        fieldnames += [f'{lb} nT', f'{lb} events T/C',
                       f'{lb} cal HR (95% CI)', f'{lb} cal P']

    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print(f'Wrote {len(out_rows)} rows to {OUT_CSV}')

    # Summary: sig count per (comp, lookback)
    print()
    print(f'{"Comparator":<10} {"90d":>5} {"365d":>5} {"unlim":>5}')
    for comp in ('Chole', 'Hernia'):
        counts = []
        for lb in LOOKBACKS:
            n = sum(1 for ep in endpoints
                    if (r := data[(comp, lb)].get(ep)) and f(r['calP']) is not None and f(r['calP']) < 0.05)
            counts.append(n)
        print(f'{comp:<10} {counts[0]:>5} {counts[1]:>5} {counts[2]:>5}')


if __name__ == '__main__':
    main()
