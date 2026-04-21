"""
Build eTable 7: decomposition of Neutrophilia/Eosinophilia combined endpoints
into their component measurements (% vs absolute count).

Uses v2 backup (16-site, 32-outcome version where %/count were separate)
to show granular estimates, alongside v3 combined main.

Output: studies/appendectomy/docs/eTable7_neutro_eosino_decomposition.csv
"""
import csv
from pathlib import Path

V2_BACKUP = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output\v2_16site_32outcome_backup\v4_fu365d_primary.csv')
V3_MAIN = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output\v4_fu365d_primary.csv')
OUT = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable7_neutro_eosino_decomposition.csv')

def load(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))

def fmt_hr(r):
    try:
        return f'{float(r["calHr"]):.2f} ({float(r["calCiLb"]):.2f}–{float(r["calCiUb"]):.2f})'
    except (ValueError, KeyError):
        return '—'

def fmt_p(r):
    try:
        p = float(r['calP'])
        return f'{p:.2e}' if p < 0.001 else f'{p:.3f}' if p < 0.01 else f'{p:.2f}'
    except (ValueError, KeyError):
        return '—'

def main():
    v2 = load(V2_BACKUP)
    v3 = load(V3_MAIN) if V3_MAIN.exists() else []
    # Get the 5 decomposition endpoints
    decomp = {
        'Neutrophil % (alone)': ['Neutro_pct_high'],
        'Absolute neutrophil count (dual-unit combined)': ['NeutroAbs_high'],
        'Neutrophilia — ANY (v3 combined: % + absolute count)': ['Neutrophilia_any'],
        'Eosinophil % (alone)': ['Eosino_pct_high'],
        'Absolute eosinophil count (dual-unit combined)': ['EosinoAbs_high'],
        'Eosinophilia — ANY (v3 combined: % + absolute count)': ['Eosinophilia_any'],
    }
    rows = []
    for label, names in decomp.items():
        for comp in ('Chole', 'Hernia'):
            src = v3 if 'v3' in label else v2
            r = next((x for x in src if x['outcomeName'] in names and x['comparator']==comp), None)
            if r is None: continue
            rows.append({
                'Endpoint': label,
                'Comparator': comp,
                'Events T/C': f'{r["evT"]}/{r["evC"]}',
                'Matched pairs': f'{r["nT"]}',
                'Raw HR (95% CI)': f'{float(r["hr"]):.2f} ({float(r["ciLb"]):.2f}–{float(r["ciUb"]):.2f})' if r.get('hr') and r['hr']!='NA' else '—',
                'Calibrated HR (95% CI)': fmt_hr(r),
                'Calibrated P': fmt_p(r),
                'E-value (calibrated)': r.get('cal_eval_hr','—'),
            })

    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f'Wrote {len(rows)} rows to {OUT}')
    for r in rows:
        print(f'  {r["Endpoint"][:55]:55s} {r["Comparator"]:6s} {r["Calibrated HR (95% CI)"]:22s} P={r["Calibrated P"]:10s} E={r["E-value (calibrated)"]}')

if __name__ == '__main__':
    main()
