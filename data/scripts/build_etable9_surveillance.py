"""
eTable 9: per-cohort measurement intensity ratios across follow-up windows.

Source: studies/appendectomy/measurement_intensity_relative.csv (OHDSI Achilles
characterization aggregates from 8 contributing sites; sum of count column
across all biomarker concepts in {site × exposure × window}).

Caveat: char_preset_all.csv `count` interpretation is ambiguous (persons vs
records); use as RELATIVE within-site comparison only — NOT for absolute
"% coverage" claims. Relative ratios are robust to this ambiguity since the
same count semantics apply within each site×window cell.
"""
import csv
import statistics
from collections import defaultdict
from pathlib import Path

SRC = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\measurement_intensity_relative.csv')
OUT = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs\eTable9_measurement_intensity.csv')

WINDOWS = ['Bio_Pre365', 'Bio_Post1_30', 'Bio_Post31_90', 'Bio_Post91_365', 'Bio_Post1y3y']
WINDOW_LABEL = {
    'Bio_Pre365':     'Pre-op (-365 to -1 d)',
    'Bio_Post1_30':   'Post 1–30 d',
    'Bio_Post31_90':  'Post 31–90 d',
    'Bio_Post91_365': 'Post 91–365 d',
    'Bio_Post1y3y':   'Post 1–3 y',
}


def main():
    # data[(site, window)][exposure] = sum_count
    data = defaultdict(dict)
    with open(SRC, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            data[(r['site'], r['window'])][r['exposure']] = int(r['sum_count'])

    out_rows = []
    for win in WINDOWS:
        ratios_chole = []
        ratios_hernia = []
        per_site = []
        for (site, w), d in sorted(data.items()):
            if w != win:
                continue
            a = d.get('Appendectomy', 0)
            c = d.get('Cholecystectomy', 0)
            h = d.get('Hernia', 0)
            r_c = a / c if c > 0 else None
            r_h = a / h if h > 0 else None
            if r_c is not None:
                ratios_chole.append(r_c)
            if r_h is not None:
                ratios_hernia.append(r_h)
            per_site.append((site, a, c, h, r_c, r_h))

        med_c = statistics.median(ratios_chole) if ratios_chole else None
        med_h = statistics.median(ratios_hernia) if ratios_hernia else None
        iqr_c = (statistics.quantiles(ratios_chole, n=4)[0],
                 statistics.quantiles(ratios_chole, n=4)[2]) if len(ratios_chole) >= 4 else (None, None)
        iqr_h = (statistics.quantiles(ratios_hernia, n=4)[0],
                 statistics.quantiles(ratios_hernia, n=4)[2]) if len(ratios_hernia) >= 4 else (None, None)

        out_rows.append({
            'Window': WINDOW_LABEL[win],
            'n sites': len(ratios_chole),
            'Median App/Chole ratio (IQR)':
                (f'{med_c:.2f} ({iqr_c[0]:.2f}–{iqr_c[1]:.2f})'
                 if med_c is not None and iqr_c[0] is not None else f'{med_c:.2f}' if med_c else ''),
            'Median App/Hernia ratio (IQR)':
                (f'{med_h:.2f} ({iqr_h[0]:.2f}–{iqr_h[1]:.2f})'
                 if med_h is not None and iqr_h[0] is not None else f'{med_h:.2f}' if med_h else ''),
        })

    fieldnames = list(out_rows[0].keys())
    with open(OUT, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)
    print(f'Wrote {len(out_rows)} rows to {OUT}')

    # Summary
    print()
    print(f'{"Window":<22} {"App/Chole (med)":>18} {"App/Hernia (med)":>20} {"n sites":>8}')
    for r in out_rows:
        print(f'{r["Window"]:<22} {r["Median App/Chole ratio (IQR)"]:>18} {r["Median App/Hernia ratio (IQR)"]:>20} {r["n sites"]:>8}')


if __name__ == '__main__':
    main()
