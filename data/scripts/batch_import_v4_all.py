"""
v4 43개 cohort 전체 batch import + KHNMC generate + count 집계
"""
import json, os, sys, time, functools, glob, csv
print = functools.partial(print, flush=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

COHORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            'studies', 'appendectomy', 'cohort_definitions', 'v4')
OUT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                         'v4_cohort_import_log.csv')

KHNMC = {'group_id': 7, 'site_id': 203, 'sourceKey': 'cdmpv53_251128'}

# 기존 import된 것 (1312 WBC_high, 1313 Hgb_low_sex v1, 1314 CRP_mgdL_high, 1315 MCV_low)
# Hgb_low_sex v1 (13 persons)은 old 구조 - skip하고 v2 이후 생성된 건 재사용
EXISTING = {
    'v4_WBC_high': 1312,
    'v4_CRP_mgdL_high': 1314,
    'v4_MCV_low': 1315,
    # Hgb_low_sex v2: 25812 — new ID from the fix test
}


def main():
    c = FedernetClient()
    c.login_portal('20230172@khnmc.or.kr', 'rlaaudtjr1!')
    c.connect_site(group_id=KHNMC['group_id'], site_id=KHNMC['site_id'])

    # Get all 43 JSON files
    files = sorted(glob.glob(os.path.join(COHORT_DIR, 'v4_*.json')))
    print(f'Found {len(files)} cohort JSONs')

    # Import (skip existing)
    cohorts = []  # [(name, cid)]
    for f in files:
        name = os.path.basename(f).replace('.json', '')
        if name in EXISTING:
            print(f'  reuse {name}: ID={EXISTING[name]}')
            cohorts.append((name, EXISTING[name]))
            continue
        try:
            r = c.create_cohort_from_json_file(name, f)
            cid = r.get('id')
            print(f'  created {name}: ID={cid}')
            cohorts.append((name, cid))
        except Exception as e:
            print(f'  ERR {name}: {e}')
            cohorts.append((name, None))

    # Trigger generate for all (not just new) to get fresh counts
    print(f'\n=== Generate all {len(cohorts)} at KHNMC ===')
    for name, cid in cohorts:
        if cid is None: continue
        try:
            c.generate_cohort(cid, KHNMC['sourceKey'])
        except Exception as e:
            print(f'  gen ERR {name}: {e}')

    # Poll all
    print(f'\n=== Polling every 60s (max 40min) ===')
    results = {name: None for name, _ in cohorts}
    for poll in range(40):
        time.sleep(60)
        all_done = True
        for name, cid in cohorts:
            if cid is None or results[name] is not None: continue
            try:
                info = c.get_cohort_generation_info(cid)
                if not info: continue
                entry = [x for x in info if x.get('id',{}).get('sourceId') == 9][0] if info else None
                # use source_id from KHNMC = 14? Check first entry
                entry = info[0] if info else None
                st = entry.get('status','?')
                pc = entry.get('personCount')
                if st in ('COMPLETE','FAILED'):
                    results[name] = {'status': st, 'count': pc,
                                       'fail': entry.get('failMessage','')[:150] if st=='FAILED' else ''}
                else:
                    all_done = False
            except Exception as e:
                pass
        done_n = sum(1 for v in results.values() if v is not None)
        print(f'  [{(poll+1)*60}s] done {done_n}/{len(cohorts)}')
        if all_done: break

    # Save results
    with open(OUT_LOG, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['cohort_name', 'cohort_id', 'status', 'person_count', 'fail_message'])
        for name, cid in cohorts:
            r = results.get(name) or {}
            w.writerow([name, cid, r.get('status','?'),
                        r.get('count','-'), r.get('fail','')])
    print(f'\n=== Saved: {OUT_LOG} ===')
    print()
    print(f"{'cohort':35} {'ID':>6}  {'status':12} {'count':>10}")
    print('-'*70)
    for name, cid in cohorts:
        r = results.get(name) or {}
        print(f"{name:35} {cid or '?':>6}  {r.get('status','?'):12} {r.get('count','-'):>10}")


if __name__ == '__main__':
    main()
