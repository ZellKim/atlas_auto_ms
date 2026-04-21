"""
eTable 8: lookback (prior-outcome filter) sensitivity.

Compare main 365-day Full-Union (v3) vs unlimited Full-Union for each biomarker endpoint.
Combined endpoints (CRP, Neutrophilia_any, Eosinophilia_any) show v3 365d alongside
the unlimited component variants until unlimited is re-run with v3 relabel.
"""
import csv
from pathlib import Path

OUT_DIR = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output')
OUT_CSV = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable8_lookback_sensitivity.csv')

UNLIM_COMPONENT_OF = {
    'CRP_mgL_high': 'CRP_high',
    'CRP_mgdL_high': 'CRP_high',
    'Neutro_pct_high': 'Neutrophilia_any',
    'Neutro#_thou_high': 'Neutrophilia_any',
    'Neutro#_uL_high': 'Neutrophilia_any',
    'Eosino_pct_high': 'Eosinophilia_any',
    'Eosino#_thou_high': 'Eosinophilia_any',
    'Eosino#_uL_high': 'Eosinophilia_any',
}

LABEL = {
    'WBC_high':'WBC', 'Neutrophilia_any':'Neutrophilia (any)',
    'Eosinophilia_any':'Eosinophilia (any)', 'Mono_high':'Monocyte %',
    'Baso_pct_high':'Basophil %', 'CRP_high':'CRP (dual-unit)',
    'AST_high':'AST', 'ALT_high':'ALT', 'ALP_high':'ALP',
    'TotBili_high':'Total bilirubin', 'Albumin_low':'Albumin',
    'HbA1c_high':'HbA1c', 'VitD_low':'Vitamin D', 'RDW_high':'RDW',
    'BUN_high':'BUN', 'TG_high':'Triglycerides',
    'LDL_high':'LDL', 'TC_high':'Total cholesterol',
    'Lympho_pct_low':'Lymphocyte % (low)', 'Lympho_pct_high':'Lymphocyte % (elevated)',
    'TotProt_low':'Total protein (low)', 'TotProt_high':'Total protein (elevated)',
    'TSH_low':'TSH (low)', 'TSH_high':'TSH (elevated)',
    'MCV_low':'MCV (low)', 'MCV_high':'MCV (elevated)',
    'Platelet_low':'Platelet (low)', 'Platelet_high':'Platelet (elevated)',
    'GlucDM':'Glucose, diabetic range', 'GlucPreDM':'Glucose, prediabetic range',
    # Unlimited-only component labels
    'CRP_mgL_high':'  └ CRP mg/L (unlim only)',
    'CRP_mgdL_high':'  └ CRP mg/dL (unlim only)',
    'Neutro_pct_high':'  └ Neutrophil % (unlim only)',
    'Neutro#_thou_high':'  └ ANC thou/µL (unlim only)',
    'Neutro#_uL_high':'  └ ANC /µL (unlim only)',
    'Eosino_pct_high':'  └ Eosinophil % (unlim only)',
    'Eosino#_thou_high':'  └ AEC thou/µL (unlim only)',
    'Eosino#_uL_high':'  └ AEC /µL (unlim only)',
}

def f(x):
    try: return float(x)
    except: return None

def fmt_hr(hr, lb, ub):
    if hr is None or lb is None or ub is None: return ''
    return f'{hr:.2f} ({lb:.2f}–{ub:.2f})'

def fmt_p(p):
    if p is None: return ''
    if p < 1e-4: return f'{p:.2e}'
    if p < 0.01: return f'{p:.4f}'
    return f'{p:.3f}'

def main():
    main365 = {(r['outcomeName'], r['comparator']): r
               for r in csv.DictReader(open(OUT_DIR/'v4_fu365d_primary.csv', encoding='utf-8'))}
    unlim = {(r['outcomeName'], r['comparator']): r
             for r in csv.DictReader(open(OUT_DIR/'v4_funlimited_summary.csv', encoding='utf-8'))}

    # Build ordered endpoint list in v3 (30 endpoints)
    v3_endpoints = sorted(set(r['outcomeName'] for r in main365.values()))

    out_rows = []
    for ep in v3_endpoints:
        for comp in ('Chole','Hernia'):
            m = main365.get((ep, comp), {})
            u = unlim.get((ep, comp), {})
            m_n = m.get('nT',''); m_ev = f"{m.get('evT','')}/{m.get('evC','')}"
            m_hr = fmt_hr(f(m.get('calHr')), f(m.get('calCiLb')), f(m.get('calCiUb')))
            m_p  = fmt_p(f(m.get('calP')))
            u_n = u.get('nT','—'); u_ev = f"{u.get('evT','—')}/{u.get('evC','—')}" if u else '—'
            u_hr = fmt_hr(f(u.get('calHr')), f(u.get('calCiLb')), f(u.get('calCiUb'))) if u else ''
            u_p  = fmt_p(f(u.get('calP'))) if u else ''
            out_rows.append({
                'Endpoint': LABEL.get(ep, ep),
                'Comparator': comp,
                '365d main nT': m_n,
                '365d events T/C': m_ev,
                '365d cal HR (95% CI)': m_hr,
                '365d cal P': m_p,
                'Unlimited nT': u_n,
                'Unlimited events T/C': u_ev,
                'Unlimited cal HR (95% CI)': u_hr,
                'Unlimited cal P': u_p,
                'Note': 'unlimited pending v3 re-run' if ep in ('CRP_high','Neutrophilia_any','Eosinophilia_any') else '',
            })
        # For combined endpoints, append their component rows from unlimited
        if ep in ('CRP_high','Neutrophilia_any','Eosinophilia_any'):
            component_names = [n for n,parent in UNLIM_COMPONENT_OF.items() if parent==ep]
            for cn in component_names:
                for comp in ('Chole','Hernia'):
                    u = unlim.get((cn, comp), {})
                    if not u: continue
                    out_rows.append({
                        'Endpoint': LABEL.get(cn, cn),
                        'Comparator': comp,
                        '365d main nT': '—',
                        '365d events T/C': '—',
                        '365d cal HR (95% CI)': '—',
                        '365d cal P': '—',
                        'Unlimited nT': u.get('nT',''),
                        'Unlimited events T/C': f"{u.get('evT','')}/{u.get('evC','')}",
                        'Unlimited cal HR (95% CI)': fmt_hr(f(u.get('calHr')), f(u.get('calCiLb')), f(u.get('calCiUb'))),
                        'Unlimited cal P': fmt_p(f(u.get('calP'))),
                        'Note': 'component (v2-era unlimited structure)',
                    })

    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader(); w.writerows(out_rows)
    print(f'Wrote {len(out_rows)} rows to {OUT_CSV}')

    # Sign-concordance summary: for non-combined endpoints, is cal HR direction preserved?
    preserved = 0; total = 0; flipped = []
    for r in out_rows:
        if r['Note']: continue  # skip combined-endpoint notes and components
        hr365 = r['365d cal HR (95% CI)']; hru = r['Unlimited cal HR (95% CI)']
        if not hr365 or not hru: continue
        try:
            m_hr = float(hr365.split(' ')[0])
            u_hr = float(hru.split(' ')[0])
        except: continue
        total += 1
        sign_preserved = (m_hr<1 and u_hr<1) or (m_hr>1 and u_hr>1) or (m_hr==1 and u_hr==1)
        if sign_preserved: preserved += 1
        else: flipped.append(f"  {r['Endpoint']:30s} {r['Comparator']:6s}  365d={m_hr:.2f}  unlim={u_hr:.2f}")
    print(f'\nDirection preserved: {preserved}/{total} (non-combined endpoints)')
    if flipped:
        print('Direction flips:')
        for line in flipped:
            print(line)

if __name__ == '__main__':
    main()
