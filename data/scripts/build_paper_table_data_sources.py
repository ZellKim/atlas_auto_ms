"""
Generate paper-ready Table 1 (data source description) from site_summary_23.csv.
3 columns: Site, Observation Period, Total Persons.

Outputs:
- docs/paper_table1_data_sources.md (Markdown + CSV copy)
"""
import os, csv

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
SUMMARY = os.path.join(ROOT, 'data', 'site_mapping', 'site_summary_23.csv')
OUT_MD  = os.path.join(ROOT, 'docs', 'paper_table1_data_sources.md')

with open(SUMMARY, encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

def persons_int(s):
    try: return int(s.replace(',', ''))
    except: return 0

rows = [r for r in rows if persons_int(r['total_persons']) > 0]
rows.sort(key=lambda r: r['code'])
total = sum(persons_int(r['total_persons']) for r in rows)

md = []
md.append('# Table 1. Participating Databases and Observation Periods')
md.append('')
md.append(f'*Auto-generated from `data/site_mapping/site_summary_23.csv` — '
          f'regenerate with `python data/scripts/build_paper_table_data_sources.py`*')
md.append('')
md.append('| Site | Observation Period | Total Persons (N) |')
md.append('|------|-------------------:|------------------:|')
for r in rows:
    period = f"{r['period_start']}–{r['period_end']}"
    md.append(f"| {r['code']} | {period} | {r['total_persons']} |")
md.append(f'| **Total (n={len(rows)} sites)** | — | **{total:,}** |')
md.append('')

# Plain CSV for pasting into Word/LaTeX
md.append('## CSV (for paste)')
md.append('')
md.append('```')
md.append('Site,Observation Period,Total Persons')
for r in rows:
    md.append(f"{r['code']},{r['period_start']}-{r['period_end']},{r['total_persons']}")
md.append(f'Total,—,{total:,}')
md.append('```')
md.append('')

# LaTeX booktabs version
md.append('## LaTeX (booktabs)')
md.append('')
md.append('```latex')
md.append(r'\begin{table}[h]')
md.append(r'\centering')
md.append(r'\caption{Participating Databases and Observation Periods}')
md.append(r'\begin{tabular}{lrr}')
md.append(r'\toprule')
md.append(r'Site & Observation Period & Total Persons (N) \\')
md.append(r'\midrule')
for r in rows:
    md.append(f"{r['code']} & {r['period_start']}--{r['period_end']} & {r['total_persons']} \\\\")
md.append(r'\midrule')
md.append(f"Total (n={len(rows)} sites) & --- & {total:,} \\\\")
md.append(r'\bottomrule')
md.append(r'\end{tabular}')
md.append(r'\end{table}')
md.append('```')

with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))
print(f'Wrote: {OUT_MD}')
print(f'Sites: {len(rows)}, Total persons: {total:,}')
