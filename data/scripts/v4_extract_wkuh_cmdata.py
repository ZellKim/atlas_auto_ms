"""
Extract WKUH CmData from result.zip files into v4_ipd_workspace/WKUH/.
Applies the standard 2-stage unzip: result.zip → cmOutput/CmData_*.zip → sqlite files.
"""
import zipfile
import shutil
from pathlib import Path

RESULTS_DIR   = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_results')
WORKSPACE_DIR = Path(r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_ipd_workspace\WKUH')

ANALYSES = ['v4_1a_cbc_wbc','v4_1b_cbc_rbc','v4_2_chem_hepa',
            'v4_3_meta_endo','v4_4_sex_specific','v4_5_clinical']
COMPARATORS = [1074, 1121]  # Chole, Hernia
TARGET = 1072  # appendectomy
WKUH_CDM = '312'

def extract_one(analysis):
    src_dir = RESULTS_DIR / analysis
    src_zip = None
    for p in src_dir.iterdir():
        if f'_{WKUH_CDM}_result.zip' in p.name:
            src_zip = p; break
    if not src_zip:
        raise FileNotFoundError(f'No WKUH result.zip in {src_dir}')

    out_base = WORKSPACE_DIR / analysis
    out_base.mkdir(parents=True, exist_ok=True)

    # Stage 1: extract result.zip, find cmOutput/CmData_*.zip
    # Path inside result.zip: script/extras/result/cmOutput/CmData_l1_t1072_c{Chole|Hernia}.zip
    with zipfile.ZipFile(src_zip) as zf:
        members = [m for m in zf.namelist() if 'cmOutput/CmData_' in m and m.endswith('.zip')]
        for m in members:
            # e.g., cmOutput/CmData_l1_t1072_c1074.zip
            fname = Path(m).name  # CmData_l1_t1072_c1074.zip
            dst_zip = out_base / fname
            with zf.open(m) as fin, open(dst_zip, 'wb') as fout:
                shutil.copyfileobj(fin, fout)

            # Stage 2: unzip the CmData zip
            stem = fname.replace('.zip', '')
            dst_dir = out_base / stem
            dst_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(dst_zip) as cmzf:
                cmzf.extractall(dst_dir)

            sqlites = list(dst_dir.glob('*.sqlite'))
            print(f'  {analysis}/{stem}: {len(sqlites)} sqlite file(s)')

def main():
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    print(f'Extracting WKUH CmData into {WORKSPACE_DIR}')
    for a in ANALYSES:
        print(f'\n[{a}]')
        extract_one(a)
    print('\nDone.')

if __name__ == '__main__':
    main()
