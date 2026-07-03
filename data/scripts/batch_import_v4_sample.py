import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'automation'))
from credentials import get_feedernet_credentials

"""
v4 cohort 대표 샘플 4개 batch import + KHNMC 동시 generate
- WBC_high (single, high threshold) - already done ID 1312
- Hgb_low_sex (sex-specific)
- CRP_mgdL_high (dual-unit)
- MCV_low (bidirectional low half)
"""
import json, os, sys, time, functools
print = functools.partial(print, flush=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

COHORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            'studies', 'appendectomy', 'cohort_definitions', 'v4')

SAMPLES = ['v4_Hgb_low_sex', 'v4_CRP_mgdL_high', 'v4_MCV_low']
KHNMC = {'group_id': 7, 'site_id': 203, 'sourceKey': 'cdmpv53_251128'}

def main():
    c = FedernetClient()
    c.login_portal(*get_feedernet_credentials())
    c.connect_site(group_id=KHNMC['group_id'], site_id=KHNMC['site_id'])

    created = []
    for name in SAMPLES:
        json_path = os.path.join(COHORT_DIR, f'{name}.json')
        print(f'\n[+] {name}')
        try:
            r = c.create_cohort_from_json_file(name, json_path)
            cid = r.get('id')
            print(f'    created ID: {cid}')
            created.append((name, cid))
        except Exception as e:
            print(f'    ERR: {e}')
            continue
        try:
            gen = c.generate_cohort(cid, KHNMC['sourceKey'])
            print(f'    generate triggered: executionId={gen.get("executionId")}')
        except Exception as e:
            print(f'    gen ERR: {e}')

    print('\n\nAll cohort IDs:', created)
    print('\n[Polling status every 30s, max 20 min]')
    done = set()
    for i in range(40):
        time.sleep(30)
        still_running = False
        for name, cid in created:
            if cid in done:
                continue
            info = c.get_cohort_generation_info(cid)
            if not info:
                continue
            st = info[0].get('status', '?')
            pc = info[0].get('personCount')
            print(f'[{(i+1)*30}s] {name} ID={cid}: status={st} pc={pc}')
            if st in ('COMPLETE', 'FAILED'):
                done.add(cid)
                if st == 'FAILED':
                    print(f'  failMessage: {info[0].get("failMessage","")[:200]}')
            else:
                still_running = True
        if not still_running:
            break
    print('\nDone.')


if __name__ == '__main__':
    main()
