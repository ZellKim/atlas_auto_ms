"""
Phase 3: consolidate 19 pooled_*/ snapshot folders into archive/{version}/pooled_snapshots/.
"""
import os, shutil, sys

ROOT = r'C:\Users\data1\Desktop\atlas_auto_cmdata'
AP = 'appendectomy/archive'

# Source → destination (dest folder created if missing)
MOVES = [
    # v7b
    ('pooled_7sites_v7b',            f'{AP}/v7b/pooled_snapshots/7sites'),
    ('pooled_10sites_v7b',           f'{AP}/v7b/pooled_snapshots/10sites'),
    ('pooled_14sites_v7b',           f'{AP}/v7b/pooled_snapshots/14sites'),
    ('pooled_results_1to1_v7b',      f'{AP}/v7b/pooled_snapshots/1to1'),
    ('pooled_results_v7b',           f'{AP}/v7b/pooled_snapshots/main'),

    # biomarker_initial (bio + nc variants = same analysis, NC is part of bio pipeline)
    ('pooled_7sites_bio',            f'{AP}/biomarker_initial/pooled_snapshots/7sites_bio'),
    ('pooled_10sites_bio',           f'{AP}/biomarker_initial/pooled_snapshots/10sites_bio'),
    ('pooled_14sites_bio',           f'{AP}/biomarker_initial/pooled_snapshots/14sites_bio'),
    ('pooled_7sites_nc',             f'{AP}/biomarker_initial/pooled_snapshots/7sites_nc'),
    ('pooled_10sites_nc',            f'{AP}/biomarker_initial/pooled_snapshots/10sites_nc'),
    ('pooled_14sites_nc',            f'{AP}/biomarker_initial/pooled_snapshots/14sites_nc'),
    ('pooled_results_1to1_bio',      f'{AP}/biomarker_initial/pooled_snapshots/1to1_bio'),
    ('pooled_results_1to1_nc',       f'{AP}/biomarker_initial/pooled_snapshots/1to1_nc'),
    ('pooled_results_biomarker',     f'{AP}/biomarker_initial/pooled_snapshots/main'),
    ('pooled_results_nc',            f'{AP}/biomarker_initial/pooled_snapshots/main_nc'),
    ('pooled_results_timewindow',    f'{AP}/biomarker_initial/pooled_snapshots/timewindow'),
    ('pooled_results_timewindow_bio',f'{AP}/biomarker_initial/pooled_snapshots/timewindow_bio'),

    # v3_bio
    ('pooled_v3_bio_11sites',        f'{AP}/v3_bio/pooled_snapshots/11sites'),
    ('pooled_v3_bio_11sites_genpop', f'{AP}/v3_bio/pooled_snapshots/11sites_genpop'),
    ('pooled_v3_bio_11sites_hernia', f'{AP}/v3_bio/pooled_snapshots/11sites_hernia'),
    ('pooled_v3_bio_11sites_tw',     f'{AP}/v3_bio/pooled_snapshots/11sites_tw'),
]

def main():
    os.chdir(ROOT)
    missing_src = [s for s, d in MOVES if not os.path.exists(s)]
    dest_exists = [d for s, d in MOVES if os.path.exists(d)]
    if missing_src:
        print(f'Missing sources: {missing_src}')
    if dest_exists:
        print(f'Destinations already exist: {dest_exists}')

    print(f'\nPlanned moves: {len(MOVES)}')
    for s, d in MOVES:
        mark = '' if os.path.exists(s) else ' (missing)'
        print(f'  {s:<35} -> {d}{mark}')

    if os.environ.get('EXECUTE') != '1':
        print('\nSet EXECUTE=1 to perform.')
        return

    done = 0
    for s, d in MOVES:
        if not os.path.exists(s):
            print(f'skip (missing): {s}')
            continue
        if os.path.exists(d):
            print(f'skip (dest exists): {d}')
            continue
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.move(s, d)
        print(f'[{done+1}] moved: {s}')
        done += 1
    print(f'\n{done} pooled snapshots moved.')

if __name__ == '__main__':
    main()
