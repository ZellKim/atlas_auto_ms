"""
Phase 2: rename 한글 filenames in appendectomy/v4/results/ to English CODE.

Examples:
  강동경희대학교병원_583_result.zip → KHNMC_583_result.zip
  순천향대학교_부천병원_318_result.zip → SCHBC_318_result.zip
"""
import os, csv, shutil, sys

ROOT = r'C:\Users\data1\Desktop\atlas_auto_cmdata\appendectomy\v4\results'

# Build cdmId → English code map (deterministic, immune to Korean naming variants)
CDM_TO_CODE = {}
site_map_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '..', 'site_mapping', 'site_id_mapping_full.csv')
with open(site_map_csv, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        CDM_TO_CODE[r['cdmId'].strip()] = r['code'].strip()

def classify(fname):
    """filename pattern: {ANYTHING}_{cdmId}_result.zip → (english_code, cdmId) or None"""
    if not fname.endswith('_result.zip'): return None
    stem = fname[:-len('_result.zip')]
    # Last underscore-separated segment must be the cdmId (digits)
    parts = stem.rsplit('_', 1)
    if len(parts) != 2 or not parts[1].isdigit(): return None
    cdm_id = parts[1]
    en = CDM_TO_CODE.get(cdm_id)
    return (en, cdm_id) if en else None

renamed = 0; skipped = 0; unmatched = []
for analysis_dir in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, analysis_dir)
    if not os.path.isdir(d): continue
    for f in sorted(os.listdir(d)):
        if not f.endswith('.zip'): continue
        cls = classify(f)
        if cls is None:
            unmatched.append(f'{analysis_dir}/{f}')
            skipped += 1
            continue
        code, cid = cls
        new_name = f'{code}_{cid}_result.zip'
        if new_name == f:
            skipped += 1
            continue
        src = os.path.join(d, f); dst = os.path.join(d, new_name)
        if os.path.exists(dst):
            print(f'  ⚠️  dest exists, skip: {analysis_dir}/{new_name}')
            skipped += 1
            continue
        if os.environ.get('EXECUTE') == '1':
            shutil.move(src, dst)
        print(f'  {analysis_dir}/{f} -> {new_name}')
        renamed += 1

print(f'\nRenamed: {renamed}, Skipped: {skipped}')
if unmatched:
    print(f'Unmatched ({len(unmatched)}):')
    for u in unmatched[:20]: print(f'  {u}')
if os.environ.get('EXECUTE') != '1':
    print('\nSet EXECUTE=1 to perform rename.')
