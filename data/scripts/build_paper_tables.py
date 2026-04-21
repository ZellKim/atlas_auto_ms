"""
Build inline markdown result tables for paper_draft_v1_15site.md.

Generates Table 2 (biomarker results), Table 3 (clinical results), and
diagnostic summary — pulling actual numbers from v4_pooled_output CSVs.
Output printed to stdout for splicing into the draft.
"""
import csv
from pathlib import Path

OUT = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output')

def load(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))

def fmt_hr(hr, lb, ub):
    try:
        return f'{float(hr):.2f} ({float(lb):.2f}–{float(ub):.2f})'
    except (ValueError, TypeError):
        return '—'

def fmt_p(p):
    try:
        v = float(p)
        if v < 0.001: return f'{v:.1e}'.replace('e-0','e−')
        if v < 0.01:  return f'{v:.3f}'
        return f'{v:.2f}'
    except (ValueError, TypeError):
        return '—'

def fmt_e(e):
    try: return f'{float(e):.2f}'
    except: return '—'

LABEL_MAP = {
    # Unidirectional (no qualifier): default abnormality direction for each
    'WBC_high':          'WBC',
    # v3 clinical-state combined (replaces Neutro_pct_high + NeutroAbs_high)
    'Neutrophilia_any':  'Neutrophilia (any indicator)',
    'Eosinophilia_any':  'Eosinophilia (any indicator)',
    # v2 legacy separate (retained for decomposition eTable 7 only; v3 main uses combined)
    'Neutro_pct_high':   'Neutrophil % (alone)',
    'NeutroAbs_high':    'Absolute neutrophil count (alone)',
    'Eosino_pct_high':   'Eosinophil % (alone)',
    'EosinoAbs_high':    'Absolute eosinophil count (alone)',
    'Mono_high':         'Monocyte %',
    'Baso_pct_high':     'Basophil %',
    'CRP_high':          'CRP',
    'AST_high':          'AST',
    'ALT_high':          'ALT',
    'ALP_high':          'Alkaline phosphatase',
    'TotBili_high':      'Total bilirubin',
    'Albumin_low':       'Albumin',
    'HbA1c_high':        'HbA1c',
    'VitD_low':          'Vitamin D',
    'RDW_high':          'RDW',
    'BUN_high':          'Blood urea nitrogen',
    'TG_high':           'Triglycerides',
    'LDL_high':          'LDL cholesterol',
    'TC_high':           'Total cholesterol',
    # Bidirectional (both high and low tested): keep direction qualifier
    'Lympho_pct_low':    'Lymphocyte % (low)',
    'Lympho_pct_high':   'Lymphocyte % (elevated)',
    'TotProt_low':       'Total protein (low)',
    'TotProt_high':      'Total protein (elevated)',
    'TSH_low':           'TSH (low)',
    'TSH_high':          'TSH (elevated)',
    'MCV_low':           'MCV (low)',
    'MCV_high':          'MCV (elevated)',
    'Platelet_low':      'Platelet count (low)',
    'Platelet_high':     'Platelet count (elevated)',
    # Threshold variants (different cut-offs of same analyte; both represent elevation)
    'GlucDM':            'Glucose, diabetic range',
    'GlucPreDM':         'Glucose, prediabetic range',
}

INDICATOR_BASE = {
    'WBC_high': 'WBC',
    'Neutrophilia_any': 'Neutrophil', 'Neutro_pct_high': 'Neutrophil', 'NeutroAbs_high': 'Neutrophil',
    'Lympho_pct_low': 'Lymphocyte', 'Lympho_pct_high': 'Lymphocyte',
    'Eosinophilia_any': 'Eosinophil', 'Eosino_pct_high': 'Eosinophil', 'EosinoAbs_high': 'Eosinophil',
    'Mono_high': 'Monocyte',
    'Baso_pct_high': 'Basophil',
    'CRP_high': 'CRP',
    'AST_high': 'AST',
    'ALT_high': 'ALT',
    'ALP_high': 'ALP',
    'TotBili_high': 'Total bilirubin',
    'TotProt_high': 'Total protein', 'TotProt_low': 'Total protein',
    'Albumin_low': 'Albumin',
    'GlucDM': 'Glucose', 'GlucPreDM': 'Glucose',
    'HbA1c_high': 'HbA1c',
    'VitD_low': 'Vitamin D',
    'TSH_high': 'TSH', 'TSH_low': 'TSH',
    'RDW_high': 'RDW',
    'MCV_high': 'MCV', 'MCV_low': 'MCV',
    'Platelet_high': 'Platelet', 'Platelet_low': 'Platelet',
    'BUN_high': 'BUN',
    'TG_high': 'Triglycerides',
    'LDL_high': 'LDL cholesterol',
    'TC_high': 'Total cholesterol',
}

# Within-group ordering (lower = earlier). Neutrophil/Eosinophil: pct → absolute.
# Bidirectional pairs follow canonical clinical direction (low→high for protein,
# high→low for platelet/MCV/TSH). Glucose: prediabetic before diabetic (severity order).
INTRA_GROUP_ORDER = {
    'WBC_high': 0,
    'Neutrophilia_any': 0, 'Neutro_pct_high': 1, 'NeutroAbs_high': 2,
    'Lympho_pct_low': 0, 'Lympho_pct_high': 1,
    'Eosinophilia_any': 0, 'Eosino_pct_high': 1, 'EosinoAbs_high': 2,
    'CRP_high': 0,
    'TotProt_low': 0, 'TotProt_high': 1,
    'Platelet_high': 0, 'Platelet_low': 1,
    'MCV_high': 0, 'MCV_low': 1,
    'TSH_high': 0, 'TSH_low': 1,
    'GlucPreDM': 0, 'GlucDM': 1,
}

def build_biomarker_table():
    rows = load(OUT/'v4_fu365d_primary.csv')
    chole = {r['outcomeName']: r for r in rows if r['comparator']=='Chole'}
    hernia = {r['outcomeName']: r for r in rows if r['comparator']=='Hernia'}
    outcomes = sorted(set(chole) | set(hernia))

    # Group by base indicator
    groups = {}
    for name in outcomes:
        base = INDICATOR_BASE.get(name, name)
        groups.setdefault(base, []).append(name)

    # For each group, compute the strongest Chole effect (min calHr) to order groups
    def min_cal_hr(group_names):
        vals = []
        for n in group_names:
            try:
                vals.append(float(chole.get(n, {}).get('calHr', 'nan')))
            except (ValueError, TypeError):
                pass
        return min(vals) if vals else float('inf')

    ordered_groups = sorted(groups.items(), key=lambda kv: min_cal_hr(kv[1]))

    out = []
    out.append('| Indicator | Chole cHR (95% CI) | Chole E-val | Hernia cHR (95% CI) | Hernia E-val |')
    out.append('|---|---|---|---|---|')
    for base, group_names in ordered_groups:
        # Within group: sort by INTRA_GROUP_ORDER then by name
        group_names = sorted(group_names, key=lambda n: (INTRA_GROUP_ORDER.get(n, 99), n))
        for name in group_names:
            c = chole.get(name, {})
            h = hernia.get(name, {})
            label = LABEL_MAP.get(name, name)
            c_hr = fmt_hr(c.get('calHr'), c.get('calCiLb'), c.get('calCiUb'))
            h_hr = fmt_hr(h.get('calHr'), h.get('calCiLb'), h.get('calCiUb'))
            c_e = fmt_e(c.get('cal_eval_hr'))
            h_e = fmt_e(h.get('cal_eval_hr'))
            out.append(f'| {label} | {c_hr} | {c_e} | {h_hr} | {h_e} |')
    return '\n'.join(out)

def build_clinical_table():
    rows = load(OUT/'v4_clinical365d_primary.csv')
    chole = {r['outcomeName']: r for r in rows if r['comparator']=='Chole'}
    hernia = {r['outcomeName']: r for r in rows if r['comparator']=='Hernia'}
    outcomes = ['UC','CD','Asthma','AD','RA','CDI','PD','BilCalc','CRC','AMI_v2','T2DM_v3']
    label = {
        'UC':'Ulcerative colitis','CD':'Crohn disease','Asthma':'Asthma','AD':'Atopic dermatitis',
        'RA':'Rheumatoid arthritis','CDI':'C. difficile infection','PD':'Parkinson disease',
        'BilCalc':'Biliary calculus','CRC':'Colorectal cancer','AMI_v2':'Acute MI','T2DM_v3':'Type-2 diabetes',
    }
    out = []
    out.append('| Outcome | Chole events T/C | Chole cHR (95% CI) | Chole P | Hernia events T/C | Hernia cHR (95% CI) | Hernia P |')
    out.append('|---|---|---|---|---|---|---|')
    for o in outcomes:
        c = chole.get(o, {})
        h = hernia.get(o, {})
        c_ev = f"{c.get('evT','—')}/{c.get('evC','—')}"
        h_ev = f"{h.get('evT','—')}/{h.get('evC','—')}"
        c_hr = fmt_hr(c.get('calHr'), c.get('calCiLb'), c.get('calCiUb'))
        h_hr = fmt_hr(h.get('calHr'), h.get('calCiLb'), h.get('calCiUb'))
        c_p = fmt_p(c.get('calP'))
        h_p = fmt_p(h.get('calP'))
        out.append(f'| {label[o]} | {c_ev} | {c_hr} | {c_p} | {h_ev} | {h_hr} | {h_p} |')
    return '\n'.join(out)

def build_baseline_summary():
    out = []
    for cname, fn in [('Cholecystectomy','v4_fu365d_table1_c1074_Chole.csv'),
                       ('Hernia repair','v4_fu365d_table1_c1121_Hernia.csv')]:
        rows = load(OUT/fn)
        smds = [abs(float(r['SMD'])) for r in rows if r['SMD'] and r['SMD'] != 'NA']
        n = len(smds); gt10 = sum(1 for s in smds if s>0.10)
        med = sorted(smds)[n//2]
        mx = max(smds)
        out.append(f'- **{cname} comparator**: {n} covariates examined; median |SMD| = {med:.3f}; max |SMD| = {mx:.3f}; {gt10} covariates with |SMD| ≥ 0.10.')
    return '\n'.join(out)

if __name__ == '__main__':
    print('## TABLE 2: Biomarker calibrated HR\n')
    print(build_biomarker_table())
    print('\n\n## TABLE 3: Clinical outcome calibrated HR\n')
    print(build_clinical_table())
    print('\n\n## BASELINE BALANCE SUMMARY\n')
    print(build_baseline_summary())
