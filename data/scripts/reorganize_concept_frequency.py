"""
Reorganize data/concept_frequency/ into clean {CODE}_{domain}.csv structure.
- Korean-named files → English code (rename via mapping)
- When both English and Korean exist, keep the one with MORE rows (newer snapshot)
- _kcd files → kcd_vocab/ subfolder
- Open_Database → reference/
- Unmatched (인천_세종병원, KHNMC_measurement_distribution) → extras/
"""
import os, shutil, csv

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'concept_frequency')
DOMAINS = {'condition', 'drug', 'measurement', 'observation', 'procedure'}

# Korean full name → English site code (from data/site_mapping/site_id_mapping_full.csv)
KO_TO_EN = {
    '강동경희대학교병원': 'KHNMC',
    '강동성심병원': 'KDH',
    '경상국립대학교병원': 'GNUH',
    '경희의료원': 'KHMC',
    '대구동산병원': 'DSMC',
    '동탄성심병원': 'HUMC',
    '명지병원': 'MJH',
    '부산대학교병원': 'PNUH',
    '순천향대학교_구미병원': 'SCHGM',
    '순천향대학교_부천병원': 'SCHBC',
    '순천향대학교_천안병원': 'SCHCA',
    '울산대학교_병원': 'UUH',
    '원광대학교병원': 'WKUH',
    '원자력병원': 'KCCH',
    '이화의료원(목동,서울)': 'EUMC',
    '제천명지병원': 'JCMJ',
    '창원경상국립대학교병원': 'GNUCH',
    '충남대학교병원(대전,세종)': 'CHNUH',
}

# _kcd prefix → English code
KCD_TO_EN = {
    '경상국립대': 'GNUH',
    '경희의료원1': 'KHMC_v1',
    '경희의료원2': 'KHMC_v2',
    '대구카톨릭': 'DCMC',
    '부산대': 'PNUH',
    '순천향천안': 'SCHCA',
    '아주대': 'AUMC',
    '원광대': 'WKUH',
    '원주세브란스': 'WSMC',   # not in standard 23 but kept
    '이대목동': 'EUMC',
}

def rowcount(path):
    try:
        with open(path, encoding='utf-8') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def classify(name):
    """Return (category, site_code, domain) or (category, label, None) for specials.
    category ∈ {by_site, kcd_vocab, reference, extras}"""
    stem = name[:-4]  # drop .csv
    # Open_Database
    if stem.startswith('Open_Database_'):
        rest = stem[len('Open_Database_'):]
        if rest in DOMAINS:
            return ('benchmark', 'Open_Database', rest)
    # _kcd files
    if '_kcd_' in stem:
        head, domain = stem.rsplit('_', 1)
        if domain in DOMAINS:
            ko = head.replace('_kcd', '')
            code = KCD_TO_EN.get(ko)
            if code:
                return ('kcd_vocab', code, domain)
    # English code {CODE}_{domain}
    head, _, domain = stem.rpartition('_')
    if domain in DOMAINS:
        # Try Korean full-name mapping first
        if head in KO_TO_EN:
            return ('by_site', KO_TO_EN[head], domain)
        # Pure ASCII uppercase code (AUMC, SCHSU, HUMC_DONGTAN, etc.)
        if head.isascii() and head.replace('_', '').isupper() and head.replace('_', '').isalnum():
            return ('by_site', head, domain)
    # Unmatched
    return ('extras', stem, None)

def main():
    # Build resolution plan: (code, domain) → best file
    inventory = {}  # (category, code, domain) → list of (source_filename, rowcount)
    for f in sorted(os.listdir(ROOT)):
        if not f.endswith('.csv'): continue
        src = os.path.join(ROOT, f)
        cat, code, domain = classify(f)
        key = (cat, code, domain)
        inventory.setdefault(key, []).append((f, rowcount(src)))

    # Decide moves
    plan = []  # (src_filename, dest_relative_path)
    conflicts = []
    for (cat, code, domain), files in inventory.items():
        if len(files) == 1:
            src_f, _ = files[0]
            if cat == 'extras' and domain is None:
                dest = f'extras/{code}.csv'
            elif cat == 'kcd_vocab':
                dest = f'kcd_vocab/{code}_kcd_{domain}.csv'
            elif cat == 'benchmark':
                dest = f'reference/{code}_{domain}.csv'
            else:
                dest = f'by_site/{code}_{domain}.csv'
            plan.append((src_f, dest))
        else:
            # Conflict — pick highest rowcount (newer snapshot)
            files_sorted = sorted(files, key=lambda x: -x[1])
            chosen, drop = files_sorted[0], files_sorted[1:]
            if cat == 'by_site':
                dest = f'by_site/{code}_{domain}.csv'
            elif cat == 'kcd_vocab':
                dest = f'kcd_vocab/{code}_kcd_{domain}.csv'
            else:
                dest = f'{cat}/{code}_{domain}.csv'
            plan.append((chosen[0], dest))
            for df, dr in drop:
                plan.append((df, f'extras/duplicate_{df}'))
            conflicts.append({
                'cat': cat, 'code': code, 'domain': domain,
                'chosen': chosen, 'dropped': drop
            })

    print(f'Planned moves: {len(plan)}')
    print(f'Conflicts resolved (highest row count kept): {len(conflicts)}')
    for c in conflicts:
        print(f"  {c['cat']}/{c['code']}_{c['domain']}: "
              f"chose {c['chosen'][0]} ({c['chosen'][1]} rows), "
              f"dropped {[f'{f}({n})' for f,n in c['dropped']]}")

    # Write plan to CSV for audit
    audit = os.path.join(ROOT, 'reorganize_plan.csv')
    with open(audit, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['source', 'destination', 'rowcount'])
        for src_f, dest in plan:
            src_path = os.path.join(ROOT, src_f)
            rc = rowcount(src_path)
            w.writerow([src_f, dest, rc])
    print(f'\nPlan saved to: {audit}')
    print('Review the plan, then run with EXECUTE=1 to perform moves.')

    if os.environ.get('EXECUTE') == '1':
        os.makedirs(os.path.join(ROOT, 'by_site'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, 'kcd_vocab'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, 'benchmark'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, 'extras'), exist_ok=True)
        for src_f, dest in plan:
            src_path = os.path.join(ROOT, src_f)
            dst_path = os.path.join(ROOT, dest)
            shutil.move(src_path, dst_path)
        print(f'\nExecuted {len(plan)} moves.')

if __name__ == '__main__':
    main()
