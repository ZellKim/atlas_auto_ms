"""
Phase 5: move scattered scratch files/dirs on atlas_auto_cmdata/ root into _scratch/.

Keep at root: README.md, SENSITIVE_DO_NOT_COMMIT, appendectomy/, allergic_diseases/.
Everything else → _scratch/ organized by type.
"""
import os, shutil, sys

ROOT = r'C:\Users\data1\Desktop\atlas_auto_cmdata'
SCRATCH = os.path.join(ROOT, '_scratch')

KEEP_AT_ROOT = {
    'README.md', 'SENSITIVE_DO_NOT_COMMIT',
    'appendectomy', 'allergic_diseases',
    '_scratch',  # target itself
}

# Directory-based classifications (exact name match, case-sensitive)
DIR_MOVES = {
    'cmData': 'legacy_outputs/cmData_biomarker_7site',
    'concept_frequency': 'legacy_outputs/concept_frequency_copy',
    'calibration_results': 'legacy_outputs/calibration_results',
    'table1_output': 'legacy_outputs/table1_output',
}

# Suffix-based for loose files
def classify_file(name):
    """Return subfolder name under _scratch/, or None to leave alone."""
    low = name.lower()
    if low.endswith('.r'):                         return 'r_scripts'
    if low.endswith('.py'):                        return 'python_scripts'
    if low.endswith('.log') or low.endswith('.txt'): return 'logs'
    if low.endswith('.json'):                      return 'json_configs'
    if low.endswith('.csv'):                       return 'csv_misc'
    if low.endswith('.zip'):                       return 'zip_exports'
    if low.endswith('.html'):                      return 'misc'
    return 'misc'

def main():
    os.chdir(ROOT)
    entries = sorted(os.listdir('.'))

    dir_moves = []   # (src, dst)
    file_moves = []  # (src, dst)

    for name in entries:
        if name in KEEP_AT_ROOT: continue
        path = os.path.join(ROOT, name)
        if os.path.isdir(path):
            if name in DIR_MOVES:
                dir_moves.append((name, os.path.join(SCRATCH, DIR_MOVES[name])))
            else:
                # Unknown directory — leave alone unless we decide otherwise
                print(f'  UNKNOWN DIR (leaving): {name}')
        else:
            sub = classify_file(name)
            dst = os.path.join(SCRATCH, sub, name)
            file_moves.append((name, dst))

    print(f'\nDirectory moves: {len(dir_moves)}')
    for s, d in dir_moves:
        print(f'  {s:<30} -> {os.path.relpath(d, ROOT)}')
    print(f'\nFile moves: {len(file_moves)}')
    counts = {}
    for s, d in file_moves:
        sub = os.path.relpath(os.path.dirname(d), ROOT)
        counts[sub] = counts.get(sub, 0) + 1
    for k, v in sorted(counts.items()):
        print(f'  {k:<40}: {v} files')

    if os.environ.get('EXECUTE') != '1':
        print('\nSet EXECUTE=1 to perform.')
        return

    # Execute
    for s, d in dir_moves + file_moves:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        src = os.path.join(ROOT, s)
        if os.path.exists(d):
            print(f'  skip (dest exists): {d}')
            continue
        shutil.move(src, d)
    print(f'\n{len(dir_moves) + len(file_moves)} items moved.')

if __name__ == '__main__':
    main()
