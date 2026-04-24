"""Hgb_low_sex 재import 테스트 (fallback 추가 후 count 증가 확인)"""
import os, sys, time, functools
print = functools.partial(print, flush=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

COHORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            'studies', 'appendectomy', 'cohort_definitions', 'v4')

c = FedernetClient()
c.login_portal('20230172@khnmc.or.kr', 'rlaaudtjr1!')
c.connect_site(group_id=7, site_id=203)

name = 'v4_Hgb_low_sex'
print(f'[+] {name} (re-import with fallback fix)')
r = c.create_cohort_from_json_file(name + '_v2', os.path.join(COHORT_DIR, f'{name}.json'))
cid = r.get('id')
print(f'  Cohort ID: {cid}')
c.generate_cohort(cid, 'cdmpv53_251128')
for i in range(50):  # 50 × 30s = 25min
    time.sleep(30)
    info = c.get_cohort_generation_info(cid)
    st = info[0].get('status')
    pc = info[0].get('personCount')
    print(f'  [{(i+1)*30}s] status={st} pc={pc}')
    if st in ('COMPLETE','FAILED'): break
