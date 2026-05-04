"""
eTable 4: Full calibrated results for all 30 biomarker endpoints.

Columns: endpoint, comparator, nT, nC, evT, evC, raw HR (95% CI), raw P,
null_mean, null_sd, cal HR (95% CI), cal P, E-value.

Split-wide format for easy reading.

Source: paper β analysis (15 sites, Full-Union 365-30 lookback) on data1.
Reproduces adam machine's v4_1_15site_beta_primary results bit-for-bit
(verified 2026-05-05: matched 13225/16108/7151/9187 + sig 23/1/16/1).
"""
import csv
from pathlib import Path

SRC_DIR = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\appendectomy\v4\v4_1_15site_beta_primary')
SRC_CHOLE  = SRC_DIR / 'primary_chole_biomarker.csv'
SRC_HERNIA = SRC_DIR / 'primary_hernia_biomarker.csv'
DIAG_CHOLE  = SRC_DIR / 'diag_chole_biomarker.csv'
DIAG_HERNIA = SRC_DIR / 'diag_hernia_biomarker.csv'
NULL_CHOLE  = SRC_DIR / 'null_chole_biomarker.csv'
NULL_HERNIA = SRC_DIR / 'null_hernia_biomarker.csv'
OUT = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable4_full_biomarker.csv')

# outcomeId → internal name (matches LABEL keys below)
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
    'WBC_high':'WBC (elevated)', 'Neutrophilia_any':'Neutrophilia (any indicator)',
    'Eosinophilia_any':'Eosinophilia (any indicator)', 'Mono_high':'Monocyte % (elevated)',
    'Baso_pct_high':'Basophil % (elevated)', 'CRP':'CRP (elevated)',
    'AST_high':'AST (elevated)', 'ALT_high':'ALT (elevated)', 'ALP_high':'ALP (elevated)',
    'TotBili_high':'Total bilirubin (elevated)', 'Albumin_low':'Albumin (low)',
    'HbA1c_high':'HbA1c (elevated)', 'VitD_low':'Vitamin D (low)', 'RDW_high':'RDW (elevated)',
    'BUN_high':'BUN (elevated)', 'TG_high':'Triglycerides (elevated)',
    'LDL_high':'LDL cholesterol (elevated)', 'TC_high':'Total cholesterol (elevated)',
    'Lympho_pct_low':'Lymphocyte % (low)', 'Lympho_pct_high':'Lymphocyte % (elevated)',
    'TotProt_low':'Total protein (low)', 'TotProt_high':'Total protein (elevated)',
    'TSH_low':'TSH (low)', 'TSH_high':'TSH (elevated)',
    'MCV_low':'MCV (low)', 'MCV_high':'MCV (elevated)',
    'Platelet_low':'Platelet (low)', 'Platelet_high':'Platelet (elevated)',
    'GlucDM':'Glucose, diabetic range', 'GlucPreDM':'Glucose, prediabetic range',
}

def fx(x):
    try: return float(x)
    except: return None

def fmt(v, d=3):
    if v is None or v != v: return ''  # NaN or None
    return f'{v:.{d}f}'

def fmt_hr(hr, lb, ub, d=2):
    if hr is None: return ''
    return f'{hr:.{d}f} ({lb:.{d}f}–{ub:.{d}f})'

def fmt_p(p):
    if p is None: return ''
    if p < 1e-4: return f'{p:.2e}'
    if p < 0.01: return f'{p:.4f}'
    return f'{p:.3f}'

def load_diag_null(diag_path, null_path):
    """Combine per-comparator diag (n_matched, n_nc) + null (mean, sd)."""
    d = next(csv.DictReader(open(diag_path, encoding='utf-8')))
    n = next(csv.DictReader(open(null_path, encoding='utf-8')))
    return {
        'null_mean': fx(n['mean']),
        'null_sd': fx(n['sd']),
        'n_nc': n.get('n_used', d.get('n_nc', '')),
    }


def load_primary(path, comparator):
    """Load primary CSV, attach outcomeName + comparator."""
    rows = []
    for r in csv.DictReader(open(path, encoding='utf-8')):
        oid = int(r['outcomeId'])
        name = OUTCOME_NAMES.get(oid)
        if name is None:
            continue  # skip unmapped (NC outcomes etc.)
        rec = dict(r)
        rec['outcomeName'] = name
        rec['comparator']  = comparator
        rows.append(rec)
    return rows


def main():
    # Load per-comparator diagnostics + null
    diag = {
        'Chole':  load_diag_null(DIAG_CHOLE,  NULL_CHOLE),
        'Hernia': load_diag_null(DIAG_HERNIA, NULL_HERNIA),
    }

    # Load + tag both comparators
    rows = load_primary(SRC_CHOLE, 'Chole') + load_primary(SRC_HERNIA, 'Hernia')

    out_rows = []
    for r in rows:
        name = r['outcomeName']
        comp = r['comparator']
        d = diag.get(comp, {})
        hr = fx(r['hr']); lb = fx(r['ciLb']); ub = fx(r['ciUb']); p = fx(r['p'])
        chr_ = fx(r['calHr']); clb = fx(r['calCiLb']); cub = fx(r['calCiUb']); cp = fx(r['calP'])
        e = fx(r.get('cal_eval_hr') or r.get('cal_eval'))
        out_rows.append({
            'Endpoint': LABEL.get(name, name),
            'Comparator': comp,
            'nT (matched)': r['nT'],
            'nC (matched)': r['nC'],
            'Events T': r['evT'],
            'Events C': r['evC'],
            'Raw HR (95% CI)': fmt_hr(hr, lb, ub),
            'Raw P': fmt_p(p),
            'null_mean': fmt(d.get('null_mean')),
            'null_sd': fmt(d.get('null_sd')),
            'n_nc': d.get('n_nc',''),
            'Calibrated HR (95% CI)': fmt_hr(chr_, clb, cub),
            'Calibrated P': fmt_p(cp),
            'E-value (calibrated)': fmt(e, 2) if e else '',
        })

    # Order: Chole first (sorted by calHr asc), then Hernia (sorted by calHr asc)
    def key(r):
        comp_rank = 0 if r['Comparator']=='Chole' else 1
        # extract cal HR numeric
        chr_str = r['Calibrated HR (95% CI)']
        if chr_str and '(' in chr_str:
            try: hr_val = float(chr_str.split(' ')[0])
            except: hr_val = 99
        else:
            hr_val = 99
        return (comp_rank, hr_val)
    out_rows.sort(key=key)

    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader(); w.writerows(out_rows)
    print(f'Wrote {len(out_rows)} rows to {OUT}')

    # Summary
    for comp in ('Chole','Hernia'):
        sub = [r for r in out_rows if r['Comparator']==comp]
        sig = sum(1 for r in sub if r['Calibrated P'] and float(r['Calibrated P'].replace('e','E').replace('−','-'))<0.05)
        print(f'  {comp}: {len(sub)} endpoints, {sig} significant (cal P<0.05)')

if __name__ == '__main__':
    main()
