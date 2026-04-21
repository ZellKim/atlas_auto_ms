"""
Post-process LOSO output: identify core-robust vs peripheral-sensitive outcomes.

Reads v4_loso_primary.csv (16 dropped-sites × 32 outcomes × 2 comparators = 1024 rows)
and computes per (outcome, comparator):
  - 16-site main calHr (from v4_fu365d_primary.csv)
  - min/max/range of calHr across 16 LOSO runs
  - #LOSO runs with calP < 0.05
  - robust_class: "core" (sig in 16/16 LOSO) / "moderate" (11-15/16) / "peripheral" (<11/16) / "never_sig"

Output: eTable6_loso_stability.csv
"""
import csv
from pathlib import Path
from collections import defaultdict

OUT_DIR = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_pooled_output')
DOCS_DIR = Path(r'g:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs')

def load(p):
    with open(p, encoding='utf-8') as f:
        return list(csv.DictReader(f))

def f(x):
    try: return float(x)
    except: return None

def main():
    # 16-site main results
    main_rows = load(OUT_DIR / 'v4_fu365d_primary.csv')
    main_idx = {(r['outcomeName'], r['comparator']): r for r in main_rows}

    # LOSO results
    loso_rows = load(OUT_DIR / 'v4_loso_primary_v3.csv')
    by_key = defaultdict(list)
    for r in loso_rows:
        by_key[(r['outcomeName'], r['comparator'])].append(r)

    out = []
    for (name, comp), runs in sorted(by_key.items()):
        main = main_idx.get((name, comp), {})
        main_chr = f(main.get('calHr'))
        main_p = f(main.get('calP'))
        main_sig = 1 if (main_p is not None and main_p < 0.05) else 0

        # LOSO stats
        chrs = [v for r in runs if (v := f(r['calHr'])) is not None]
        sig_count = 0
        for r in runs:
            p = f(r.get('calP'))
            if p is not None and p < 0.05:
                sig_count += 1
        n_loso = len(runs)

        if not chrs:
            out.append({
                'outcomeName': name, 'comparator': comp,
                'main_calHr': main_chr, 'main_sig': main_sig,
                'loso_chr_min': None, 'loso_chr_max': None, 'loso_chr_range': None,
                'loso_sig_count': 0, 'loso_total': n_loso,
                'robust_class': 'no_data',
            })
            continue

        chr_min = min(chrs); chr_max = max(chrs); chr_range = chr_max - chr_min

        if main_sig:
            if sig_count == n_loso:
                cls = 'core'
            elif sig_count >= n_loso - 2:  # 14-15 out of 16
                cls = 'robust'
            elif sig_count >= n_loso * 0.6:  # 10-13 out of 16
                cls = 'moderate'
            else:
                cls = 'peripheral'
        else:
            if sig_count == 0:
                cls = 'never_sig'
            else:
                cls = 'borderline'  # sometimes sig under LOSO

        out.append({
            'outcomeName': name, 'comparator': comp,
            'main_calHr': f'{main_chr:.3f}' if main_chr is not None else None,
            'main_sig': main_sig,
            'loso_chr_min': f'{chr_min:.3f}',
            'loso_chr_max': f'{chr_max:.3f}',
            'loso_chr_range': f'{chr_range:.3f}',
            'loso_sig_count': sig_count,
            'loso_total': n_loso,
            'robust_class': cls,
        })

    # Sort by comparator then robustness class then outcome
    class_order = {'core': 0, 'robust': 1, 'moderate': 2, 'peripheral': 3, 'borderline': 4, 'never_sig': 5}
    out.sort(key=lambda r: (r['comparator'], class_order.get(r['robust_class'], 99), r['outcomeName']))

    csv_out = DOCS_DIR / 'eTable6_loso_stability_v3.csv'
    with open(csv_out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    print(f'Wrote {len(out)} rows to {csv_out}')

    # Per-comparator class breakdown
    print('\n=== LOSO robustness class distribution ===')
    for comp in ('Chole','Hernia'):
        from collections import Counter
        sub = [r for r in out if r['comparator']==comp]
        ct = Counter(r['robust_class'] for r in sub)
        print(f'  {comp}: {dict(ct)}')

    # List core/robust outcomes per comparator
    print('\n=== Outcomes classified as CORE (sig in all 16 LOSO) ===')
    for comp in ('Chole','Hernia'):
        cores = [r['outcomeName'] for r in out if r['comparator']==comp and r['robust_class']=='core']
        print(f'  {comp}: {", ".join(cores) if cores else "(none)"}')

if __name__ == '__main__':
    main()
