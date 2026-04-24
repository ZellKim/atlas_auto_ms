"""
Phase 1: Reorganize C:\\Users\\data1\\Desktop\\atlas_auto_cmdata/ into study-centric tree.

Moves only; no rename, no dedupe (duplicate zip+SQLite intentionally kept).

Target structure:
  appendectomy/
    v4/
      results/            ← v4_results/
      cmData/             ← v4_ipd_workspace/
      cmData_clinical/    ← v4_clinical_workspace/
      pooled_output/      ← v4_pooled_output/
      regression_tests/   ← v4_lib_regression_output/
    archive/
      v2_bio/results/     ← results_v2_bio/
      v3_bio/results/     ← results_v3_bio/
      v3_bio/cmData/      ← cmData_v3_bio/
      v7/cmData/          ← cmData_v7/   (orphan, no results folder)
      v7b/results/        ← results_v7b/
      v7b/cmData/         ← cmData_v7b/
      biomarker_initial/results/  ← results_biomarker/
      biomarker_initial/cmData/   ← cmData_biomarker/
  allergic_diseases/
    results/              ← results_allergic/
    cmData/               ← cmData_allergic/
    pooled_output/        ← allergic_pooled_output/

Safety: checks each source exists before move. Aborts on first conflict.
pooled_*/ folders are NOT touched in Phase 1 (Phase 3 scope).
"""
import os, shutil, sys

ROOT = r'C:\Users\data1\Desktop\atlas_auto_cmdata'

MOVES = [
    # appendectomy v4 canonical
    ('v4_results',              'appendectomy/v4/results'),
    ('v4_ipd_workspace',        'appendectomy/v4/cmData'),
    ('v4_clinical_workspace',   'appendectomy/v4/cmData_clinical'),
    ('v4_pooled_output',        'appendectomy/v4/pooled_output'),
    ('v4_lib_regression_output','appendectomy/v4/regression_tests'),

    # appendectomy archive (older versions)
    ('results_v2_bio',          'appendectomy/archive/v2_bio/results'),
    ('results_v3_bio',          'appendectomy/archive/v3_bio/results'),
    ('cmData_v3_bio',           'appendectomy/archive/v3_bio/cmData'),
    ('cmData_v7',               'appendectomy/archive/v7/cmData'),
    ('results_v7b',             'appendectomy/archive/v7b/results'),
    ('cmData_v7b',              'appendectomy/archive/v7b/cmData'),
    ('results_biomarker',       'appendectomy/archive/biomarker_initial/results'),
    ('cmData_biomarker',        'appendectomy/archive/biomarker_initial/cmData'),

    # allergic
    ('results_allergic',        'allergic_diseases/results'),
    ('cmData_allergic',         'allergic_diseases/cmData'),
    ('allergic_pooled_output',  'allergic_diseases/pooled_output'),
]

def main():
    os.chdir(ROOT)
    # preflight: check every source + none of the destinations exist already
    errors = []
    for src, dst in MOVES:
        if not os.path.exists(src):
            errors.append(f'MISSING source: {src}')
        if os.path.exists(dst):
            errors.append(f'DEST EXISTS already: {dst}')
    if errors:
        print('Preflight failed:')
        for e in errors: print(f'  {e}')
        sys.exit(1)

    # Dry-run listing
    print('Planned moves:')
    for src, dst in MOVES:
        print(f'  {src:<28} -> {dst}')

    if os.environ.get('EXECUTE') != '1':
        print('\nSet EXECUTE=1 to perform moves.')
        return

    # Execute
    for i, (src, dst) in enumerate(MOVES, 1):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print(f'[{i}/{len(MOVES)}] {src} -> {dst} ...', end=' ', flush=True)
        shutil.move(src, dst)
        print('OK')

    print(f'\n{len(MOVES)} moves completed.')

if __name__ == '__main__':
    main()
