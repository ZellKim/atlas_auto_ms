"""
eTable 5: σ-grid sensitivity for empirical calibration.

For each primary outcome (biomarker + clinical) × comparator, recompute calibrated
HR/CI/P using alternate null σ values while holding fitted null_mean constant.

Purpose: demonstrate robustness to null-variance mis-specification. Hernia comparator
null hit σ≈0 boundary (method-of-moments); reviewer likely to question whether that
masks residual confounding. σ-grid shows how calibrated CI widens under alternative
σ and whether significance is preserved.

Output: studies/appendectomy/docs/eTable5_sigma_grid.csv

Schuemie 2014 formula (same as v4_main_365d_analysis.R:265-269):
    calLogHr = logHr - nullMean
    calSe    = sqrt(seLogHr^2 + sigma^2)
    calCi    = exp(calLogHr ± 1.96 * calSe)
    calP     = 2 * pnorm(-|calLogHr|/calSe)
"""
import csv
import math
from pathlib import Path

OUT_DIR = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output')
DOCS_DIR = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs')

SIGMAS = [0.10, 0.20, 0.30]
Z = 1.959964  # qnorm(0.975)

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def calibrate(log_hr, se, null_mean, sigma):
    cal_log = log_hr - null_mean
    cal_se = math.sqrt(se*se + sigma*sigma)
    return {
        'calHr': math.exp(cal_log),
        'calCiLb': math.exp(cal_log - Z * cal_se),
        'calCiUb': math.exp(cal_log + Z * cal_se),
        'calP': 2 * phi(-abs(cal_log) / cal_se),
    }

def load_diag(path):
    """Return {comparator: {null_mean: float, null_sd_fitted: float, n_nc: int}}"""
    diag = {}
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            diag[r['comparator']] = {
                'null_mean': float(r['null_mean']),
                'null_sd_fitted': float(r['null_sd']),
                'n_nc': int(r['n_nc']),
            }
    return diag

def process(primary_csv, diag_csv, analysis_tag):
    diag = load_diag(diag_csv)
    rows = []
    with open(primary_csv, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            cname = r['comparator']
            d = diag.get(cname)
            if not d:
                continue
            try:
                log_hr = float(r['logHr']); se = float(r['seLogHr'])
            except (ValueError, KeyError):
                continue
            if not (math.isfinite(log_hr) and math.isfinite(se)):
                continue
            base = {
                'analysis': analysis_tag,
                'outcomeName': r.get('outcomeName',''),
                'category': r.get('category',''),
                'comparator': cname,
                'null_mean': d['null_mean'],
                'null_sd_fitted': d['null_sd_fitted'],
                'logHr': log_hr,
                'seLogHr': se,
                'hr_raw': float(r['hr']) if r.get('hr') else float('nan'),
                'ciLb_raw': float(r['ciLb']) if r.get('ciLb') else float('nan'),
                'ciUb_raw': float(r['ciUb']) if r.get('ciUb') else float('nan'),
                'calHr_fitted': float(r['calHr']) if r.get('calHr') else float('nan'),
                'calCiLb_fitted': float(r['calCiLb']) if r.get('calCiLb') else float('nan'),
                'calCiUb_fitted': float(r['calCiUb']) if r.get('calCiUb') else float('nan'),
                'calP_fitted': float(r['calP']) if r.get('calP') else float('nan'),
            }
            for sigma in SIGMAS:
                cal = calibrate(log_hr, se, d['null_mean'], sigma)
                base[f'calHr_sig{sigma:.2f}']   = cal['calHr']
                base[f'calCiLb_sig{sigma:.2f}'] = cal['calCiLb']
                base[f'calCiUb_sig{sigma:.2f}'] = cal['calCiUb']
                base[f'calP_sig{sigma:.2f}']   = cal['calP']
            rows.append(base)
    return rows

def main():
    all_rows = []
    all_rows += process(OUT_DIR / 'v4_fu365d_primary.csv',
                        OUT_DIR / 'v4_fu365d_diagnostics.csv',
                        'biomarker_365d')
    all_rows += process(OUT_DIR / 'v4_clinical365d_primary.csv',
                        OUT_DIR / 'v4_clinical365d_diagnostics.csv',
                        'clinical_365d')
    if not all_rows:
        raise SystemExit('No rows produced — check input CSV paths')
    out = DOCS_DIR / 'eTable5_sigma_grid.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(all_rows[0].keys())
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f'Wrote {len(all_rows)} rows to {out}')

    # Summary: across primary outcomes, how many flip significance at each σ?
    print('\n=== σ-grid impact summary (calP < 0.05) ===')
    for tag in ('biomarker_365d','clinical_365d'):
        for cname in ('Chole','Hernia'):
            subset = [r for r in all_rows if r['analysis']==tag and r['comparator']==cname]
            if not subset:
                continue
            fitted_sig = sum(1 for r in subset if r['calP_fitted']<0.05)
            header = f'  {tag:15s} {cname:6s} fitted_σ={subset[0]["null_sd_fitted"]:.3f} → sig={fitted_sig}/{len(subset)}'
            print(header)
            for sigma in SIGMAS:
                key = f'calP_sig{sigma:.2f}'
                sig_n = sum(1 for r in subset if r[key]<0.05)
                preserved = sum(1 for r in subset if (r['calP_fitted']<0.05) == (r[key]<0.05))
                print(f'    σ={sigma:.2f}: sig={sig_n:3d}/{len(subset)}  preserved={preserved}/{len(subset)}')

if __name__ == '__main__':
    main()
