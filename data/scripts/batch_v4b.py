import sys
sys.path.insert(0, r'G:\My Drive\KHNMC\atlas_auto_with_claude\automation')
from credentials import get_feedernet_credentials

"""v4b 43 cohort 전체 batch import + KHNMC generate + count 집계"""
import os, sys, time, functools, glob, csv
print = functools.partial(print, flush=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

COHORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            'studies', 'appendectomy', 'cohort_definitions', 'v4b')
OUT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                         'v4b_cohort_import_log.csv')
KHNMC = {'group_id': 7, 'site_id': 203, 'sourceKey': 'cdmpv53_251128'}

c = FedernetClient()
c.login_portal(*get_feedernet_credentials())
c.connect_site(group_id=KHNMC['group_id'], site_id=KHNMC['site_id'])

files = sorted(glob.glob(os.path.join(COHORT_DIR, 'v4_*.json')))
print(f'Found {len(files)} cohort JSONs')
cohorts = []
for f in files:
    name = os.path.basename(f).replace('.json', '').replace('v4_', 'v4b_')
    try:
        r = c.create_cohort_from_json_file(name, f)
        cid = r.get('id')
        print(f'  {name}: ID={cid}')
        cohorts.append((name, cid))
    except Exception as e:
        print(f'  ERR {name}: {e}')

for name, cid in cohorts:
    if cid is None: continue
    try: c.generate_cohort(cid, KHNMC['sourceKey'])
    except: pass

results = {name: None for name, _ in cohorts}
for poll in range(40):
    time.sleep(60)
    all_done = True
    for name, cid in cohorts:
        if cid is None or results[name] is not None: continue
        try:
            info = c.get_cohort_generation_info(cid)
            if not info: continue
            entry = info[0]
            st = entry.get('status','?')
            pc = entry.get('personCount')
            if st in ('COMPLETE','FAILED'):
                results[name] = {'status': st, 'count': pc}
            else:
                all_done = False
        except Exception:
            pass
    done_n = sum(1 for v in results.values() if v is not None)
    print(f'[{(poll+1)*60}s] done {done_n}/{len(cohorts)}')
    if all_done: break

with open(OUT_LOG, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['name', 'id', 'status', 'count'])
    for name, cid in cohorts:
        r = results.get(name) or {}
        w.writerow([name, cid, r.get('status','?'), r.get('count','-')])
print(f'Saved: {OUT_LOG}')
print()
print(f"{'cohort':38} {'ID':>6}  {'count':>10}")
for name, cid in cohorts:
    r = results.get(name) or {}
    print(f"{name:38} {cid or '?':>6}  {r.get('count','-'):>10}")
