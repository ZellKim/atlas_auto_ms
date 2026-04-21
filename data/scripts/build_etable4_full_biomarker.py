"""
eTable 4: Full calibrated results for all 30 biomarker endpoints.

Columns: endpoint, comparator, nT, nC, evT, evC, raw HR (95% CI), raw P,
null_mean, null_sd, cal HR (95% CI), cal P, E-value.

Split-wide format for easy reading.
"""
import csv
from pathlib import Path

SRC = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output\v4_fu365d_primary.csv')
DIAG = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output\v4_fu365d_diagnostics.csv')
OUT = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable4_full_biomarker.csv')

LABEL = {
    'WBC_high':'WBC (elevated)', 'Neutrophilia_any':'Neutrophilia (any indicator)',
    'Eosinophilia_any':'Eosinophilia (any indicator)', 'Mono_high':'Monocyte % (elevated)',
    'Baso_pct_high':'Basophil % (elevated)', 'CRP_high':'CRP (elevated)',
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

def main():
    # Load diagnostics
    diag = {}
    with open(DIAG, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            diag[r['comparator']] = {
                'null_mean': fx(r['null_mean']),
                'null_sd': fx(r['null_sd']),
                'n_nc': r['n_nc'],
            }

    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
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
