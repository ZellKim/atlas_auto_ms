"""
Generate Figure 1/2/3 from v3 pipeline output.

Figure 1: Forest plot — 30 biomarker endpoints × 2 comparators (Chole, Hernia)
         grouped by category, sorted by |log cHR| within category.
Figure 2: Forest plot — 11 clinical endpoints × 2 comparators.
Figure 3: Time-window cHR for 8 core outcomes across 5 landmark intervals.

Writes PNGs into studies/appendectomy/figures/.
"""
import csv
import math
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

OUT = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output')
FIG = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\figures')
FIG.mkdir(parents=True, exist_ok=True)

LABEL_MAP = {
    'WBC_high':'WBC', 'Neutrophilia_any':'Neutrophilia (any)', 'Eosinophilia_any':'Eosinophilia (any)',
    'Mono_high':'Monocyte %', 'Baso_pct_high':'Basophil %', 'CRP_high':'CRP',
    'AST_high':'AST', 'ALT_high':'ALT', 'ALP_high':'Alkaline phosphatase', 'TotBili_high':'Total bilirubin',
    'Albumin_low':'Albumin', 'HbA1c_high':'HbA1c', 'VitD_low':'Vitamin D', 'RDW_high':'RDW',
    'BUN_high':'Blood urea nitrogen', 'TG_high':'Triglycerides', 'LDL_high':'LDL cholesterol',
    'TC_high':'Total cholesterol',
    'Lympho_pct_low':'Lymphocyte % (low)', 'Lympho_pct_high':'Lymphocyte % (elevated)',
    'TotProt_low':'Total protein (low)', 'TotProt_high':'Total protein (elevated)',
    'TSH_low':'TSH (low)', 'TSH_high':'TSH (elevated)',
    'MCV_low':'MCV (low)', 'MCV_high':'MCV (elevated)',
    'Platelet_low':'Platelet (low)', 'Platelet_high':'Platelet (elevated)',
    'GlucDM':'Glucose, diabetic range', 'GlucPreDM':'Glucose, prediabetic range',
}

CATEGORY = {
    'WBC_high':'Immune', 'Neutrophilia_any':'Immune', 'Eosinophilia_any':'Immune',
    'Lympho_pct_low':'Immune', 'Lympho_pct_high':'Immune',
    'Mono_high':'Immune', 'Baso_pct_high':'Immune', 'CRP_high':'Immune', 'Albumin_low':'Immune',
    'AST_high':'Hepatic', 'ALT_high':'Hepatic', 'ALP_high':'Hepatic', 'TotBili_high':'Hepatic',
    'TotProt_low':'Hepatic', 'TotProt_high':'Hepatic',
    'HbA1c_high':'Metabolic', 'GlucDM':'Metabolic', 'GlucPreDM':'Metabolic',
    'TG_high':'Metabolic', 'LDL_high':'Metabolic', 'TC_high':'Metabolic',
    'MCV_low':'Hematologic', 'MCV_high':'Hematologic', 'RDW_high':'Hematologic',
    'Platelet_low':'Hematologic', 'Platelet_high':'Hematologic',
    'TSH_low':'Endocrine', 'TSH_high':'Endocrine', 'VitD_low':'Endocrine',
    'BUN_high':'Renal',
}

CATEGORY_ORDER = ['Immune','Hepatic','Metabolic','Hematologic','Endocrine','Renal']

CLINICAL_LABEL = {
    'UC':'Ulcerative colitis','CD':'Crohn disease','Asthma':'Asthma','AD':'Atopic dermatitis',
    'RA':'Rheumatoid arthritis','CDI':'C. difficile infection','PD':'Parkinson disease',
    'BilCalc':'Biliary calculus','CRC':'Colorectal cancer','AMI_v2':'Acute MI',
    'T2DM_v3':'Type-2 diabetes',
}

CORE_TIMEWINDOW = ['WBC_high','Neutrophilia_any','Lympho_pct_low','CRP_high',
                   'AST_high','ALT_high','TotBili_high','GlucDM']


def load(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def f(x):
    try: return float(x)
    except: return None


def forest(rows, outcomes, label_fn, fname, title, figsize=(10, 12)):
    """Two-panel forest: Chole (left) vs Hernia (right). outcomes = ordered list of outcomeName."""
    by = {(r['outcomeName'], r['comparator']): r for r in rows}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize, sharey=True)
    y = list(range(len(outcomes)))[::-1]  # top-down
    for ax, comp, color in [(ax1, 'Chole', '#1f77b4'), (ax2, 'Hernia', '#d62728')]:
        ax.axvline(1, color='gray', ls='--', lw=0.8)
        for i, name in enumerate(outcomes):
            r = by.get((name, comp))
            if not r: continue
            hr = f(r['calHr']); lb = f(r['calCiLb']); ub = f(r['calCiUb'])
            if hr is None: continue
            yy = y[i]
            ax.errorbar([hr], [yy], xerr=[[hr-lb],[ub-hr]],
                        fmt='o', color=color, ecolor=color, capsize=3, ms=5)
        ax.set_xscale('log')
        ax.set_xlim(0.1, 5)
        ax.set_xticks([0.2, 0.5, 1, 2, 5])
        ax.set_xticklabels(['0.2','0.5','1','2','5'])
        ax.set_title(f'{comp} comparator', fontsize=11)
        ax.set_xlabel('Calibrated HR (95% CI)', fontsize=10)
        ax.grid(axis='y', alpha=0.2)
    ax1.set_yticks(y)
    ax1.set_yticklabels([label_fn(n) for n in outcomes], fontsize=9)
    fig.suptitle(title, fontsize=12, y=0.995)
    fig.tight_layout()
    fig.savefig(fname, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f'  wrote {fname.name}')


def figure1_biomarker():
    rows = load(OUT / 'v4_fu365d_primary.csv')
    # Build ordered list: group by category, within category sort by |log(calHr Chole)|
    chole = {r['outcomeName']: r for r in rows if r['comparator']=='Chole'}
    outcomes_by_cat = {cat: [] for cat in CATEGORY_ORDER}
    for name in chole:
        cat = CATEGORY.get(name, 'Other')
        if cat not in outcomes_by_cat:
            outcomes_by_cat[cat] = []
        outcomes_by_cat[cat].append(name)
    for cat in outcomes_by_cat:
        outcomes_by_cat[cat].sort(key=lambda n: abs(math.log(f(chole[n]['calHr']))) if f(chole[n]['calHr']) else 0, reverse=True)
    ordered = []
    for cat in CATEGORY_ORDER:
        ordered.extend(outcomes_by_cat.get(cat, []))
    forest(rows, ordered, lambda n: LABEL_MAP.get(n, n),
           FIG / 'forest_primary_365d.png',
           'Figure 1. Calibrated hazard ratios for 30 biomarker endpoints (v3)',
           figsize=(10, 12))


def figure2_clinical():
    rows = load(OUT / 'v4_clinical365d_primary.csv')
    outcomes = ['UC','CD','Asthma','AD','RA','CDI','PD','BilCalc','CRC','AMI_v2','T2DM_v3']
    forest(rows, outcomes, lambda n: CLINICAL_LABEL.get(n, n),
           FIG / 'forest_clinical_365d.png',
           'Figure 2. Calibrated hazard ratios for 11 clinical endpoints',
           figsize=(10, 6))


def figure3_timewindow():
    rows = load(OUT / 'v4_fu365d_timewindow.csv')
    by = {(r['outcomeName'], r['comparator'], r['window']): r for r in rows}
    windows = ['1d-30d', '31d-90d', '91d-365d', '366d-1095d', '1096d-3650d']
    window_labels = ['1–30d','31–90d','91–365d','1–3y','3–10y']
    fig, axes = plt.subplots(2, 4, figsize=(14, 7), sharex=True, sharey=True)
    for ax, name in zip(axes.flat, CORE_TIMEWINDOW):
        for comp, color, marker in [('Chole','#1f77b4','o'), ('Hernia','#d62728','s')]:
            xs, ys, lbs, ubs = [], [], [], []
            for i, w in enumerate(windows):
                r = by.get((name, comp, w))
                if not r: continue
                hr = f(r['calHr']); lb = f(r['calCiLb']); ub = f(r['calCiUb'])
                if hr is None or hr <= 0: continue
                xs.append(i); ys.append(hr); lbs.append(hr-lb); ubs.append(ub-hr)
            if xs:
                ax.errorbar(xs, ys, yerr=[lbs, ubs], fmt=f'-{marker}', color=color,
                            ecolor=color, capsize=3, label=comp, ms=5, lw=1.2)
        ax.axhline(1, color='gray', ls='--', lw=0.7)
        ax.set_yscale('log')
        ax.set_ylim(0.08, 4)
        ax.set_xticks(range(len(windows)))
        ax.set_xticklabels(window_labels, rotation=30, fontsize=8)
        ax.set_title(LABEL_MAP.get(name, name), fontsize=10)
        ax.grid(alpha=0.2)
    axes[0,0].legend(loc='upper right', fontsize=8)
    axes[1,0].set_ylabel('Calibrated HR', fontsize=10)
    axes[0,0].set_ylabel('Calibrated HR', fontsize=10)
    fig.suptitle('Figure 3. Time-window calibrated HR for 8 core outcomes (v3)', fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG / 'timewindow_core_365d.png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f'  wrote timewindow_core_365d.png')


if __name__ == '__main__':
    print('=== Figure 1: biomarker forest ===')
    figure1_biomarker()
    print('=== Figure 2: clinical forest ===')
    figure2_clinical()
    print('=== Figure 3: timewindow ===')
    figure3_timewindow()
    print('\nAll figures written to', FIG)
