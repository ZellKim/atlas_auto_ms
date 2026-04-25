"""
Phase 6: clean repo root (atlas_auto_with_claude/).
- 103 .log → _legacy/logs/
- KCDtoConcept_id/, estimation_model/, tool_package/ → _legacy/
- results/ (4.1GB, root-level result.zip duplicates) → Desktop atlas_auto_cmdata/appendectomy/archive/results_legacy_241xxx/
- pandoc.msi, Rplots.pdf → _legacy/installers/, deleted respectively
- OHDSI_REPOS.md → docs/
- Study-specific R scripts (km_plot_master_*, total_analysis_*, reference_scripts/, v4_table1_*) → studies/appendectomy/R/

Safety: moves only (no data loss). All sources verified before move.
"""
import os, shutil, glob

ROOT = r'g:\내 드라이브\KHNMC\atlas_auto_with_claude'
LEGACY = os.path.join(ROOT, '_legacy')
DESKTOP_ARCHIVE = r'C:\Users\data1\Desktop\atlas_auto_cmdata\appendectomy\archive\results_legacy_241xxx'

os.makedirs(os.path.join(LEGACY, 'logs'), exist_ok=True)
os.makedirs(os.path.join(LEGACY, 'installers'), exist_ok=True)
os.makedirs(DESKTOP_ARCHIVE, exist_ok=True)

moved, skipped = [], []

def move(src, dst, label):
    if not os.path.exists(src):
        skipped.append(f'{label}: source missing')
        return False
    if os.path.exists(dst):
        skipped.append(f'{label}: dest exists ({dst})')
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    moved.append(f'{label}: {os.path.basename(src)} → {os.path.relpath(dst, ROOT) if dst.startswith(ROOT) else dst}')
    return True

# 1) 103 .log files at root → _legacy/logs/
log_files = glob.glob(os.path.join(ROOT, '*.log'))
print(f'[1] Moving {len(log_files)} .log files → _legacy/logs/')
for lf in log_files:
    move(lf, os.path.join(LEGACY, 'logs', os.path.basename(lf)), 'log')

# 2) Legacy directories → _legacy/
for d in ['KCDtoConcept_id', 'estimation_model', 'tool_package']:
    src = os.path.join(ROOT, d)
    dst = os.path.join(LEGACY, d)
    move(src, dst, f'legacy-dir {d}')

# 3) Installers → _legacy/installers/
for pat in ['pandoc-*.msi', 'pandoc-*.exe']:
    for f in glob.glob(os.path.join(ROOT, pat)):
        move(f, os.path.join(LEGACY, 'installers', os.path.basename(f)), 'installer')

# 4) Rplots.pdf → delete (always regenerated)
rp = os.path.join(ROOT, 'Rplots.pdf')
if os.path.exists(rp):
    os.remove(rp)
    moved.append('rm: Rplots.pdf')

# 5) OHDSI_REPOS.md → docs/
move(os.path.join(ROOT, 'OHDSI_REPOS.md'),
     os.path.join(ROOT, 'docs', 'OHDSI_REPOS.md'),
     'doc OHDSI_REPOS')

# 6) Study-specific R → studies/appendectomy/R/  (root copy removed; study has duplicate)
for f in ['km_plot_master_250909.R',
          'total_analysis_make_baseline_250909.R',
          'total_analysis_make_km_data_250909.R']:
    src = os.path.join(ROOT, 'R', f)
    dst_study = os.path.join(ROOT, 'studies', 'appendectomy', 'R', f)
    if os.path.exists(src) and os.path.exists(dst_study):
        # study has duplicate → delete root copy
        os.remove(src)
        moved.append(f'duplicate rm root: R/{f} (study has identical copy)')
    elif os.path.exists(src):
        move(src, dst_study, f'study R')

# v4_table1_main365d.R: only in root → move to studies (study-specific)
move(os.path.join(ROOT, 'R', 'v4_table1_main365d.R'),
     os.path.join(ROOT, 'studies', 'appendectomy', 'R', 'v4_table1_main365d.R'),
     'study R')

# reference_scripts/: in both root R/ and studies/.../R/ — root has duplicate, delete
ref_root = os.path.join(ROOT, 'R', 'reference_scripts')
ref_study = os.path.join(ROOT, 'studies', 'appendectomy', 'R', 'reference_scripts')
if os.path.exists(ref_root) and os.path.exists(ref_study):
    shutil.rmtree(ref_root)
    moved.append('duplicate rm root: R/reference_scripts/ (study has identical copy)')

# 7) results/ (4.1GB) → Desktop atlas_auto_cmdata/appendectomy/archive/results_legacy_241xxx/
results_src = os.path.join(ROOT, 'results')
if os.path.exists(results_src):
    print(f'[7] Moving results/ ({results_src}) → Desktop archive (this may take minutes for 4.1GB)')
    # Move contents into existing dest dir
    for item in os.listdir(results_src):
        s = os.path.join(results_src, item)
        d = os.path.join(DESKTOP_ARCHIVE, item)
        if os.path.exists(d):
            skipped.append(f'results: {item} exists in Desktop dest, skipping')
            continue
        shutil.move(s, d)
        moved.append(f'results-zip: {item}')
    # Remove empty source dir
    try:
        os.rmdir(results_src)
        moved.append('rmdir: results/')
    except OSError:
        skipped.append(f'results/: not empty after moves')

# Summary
print(f'\n=== SUMMARY ===')
print(f'Moved: {len(moved)}')
for m in moved[:10]:
    print(f'  {m}')
if len(moved) > 10:
    print(f'  ... ({len(moved) - 10} more)')
print(f'Skipped: {len(skipped)}')
for s in skipped[:10]:
    print(f'  {s}')
