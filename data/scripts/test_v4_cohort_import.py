import sys
sys.path.insert(0, r'G:\My Drive\KHNMC\atlas_auto_with_claude\automation')
from credentials import get_feedernet_credentials

"""
v4 cohort 1개 ATLAS import 테스트 (WBC_high)
- import 후 KHNMC에서 generate → count 확인 → 검증
"""
import json, os, sys, time, functools
print = functools.partial(print, flush=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

COHORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                            'studies', 'appendectomy', 'cohort_definitions', 'v4')

TEST_COHORT = 'v4_WBC_high'  # 첫 테스트

# KHNMC
KHNMC = {'group_id': 7, 'site_id': 203, 'sourceKey': 'cdmpv53_251128'}


def main():
    c = FedernetClient()
    c.login_portal(*get_feedernet_credentials())
    c.connect_site(group_id=KHNMC['group_id'], site_id=KHNMC['site_id'])

    # 1. Create cohort from JSON
    json_path = os.path.join(COHORT_DIR, f'{TEST_COHORT}.json')
    print(f'[1] Creating cohort from {TEST_COHORT}.json...')
    try:
        result = c.create_cohort_from_json_file(TEST_COHORT, json_path)
        cohort_id = result.get('id')
        print(f'    Cohort ID: {cohort_id}')
    except Exception as e:
        print(f'    ERR: {e}')
        return

    # 2. Generate at KHNMC
    print(f'\n[2] Generating at KHNMC ({KHNMC["sourceKey"]})...')
    try:
        gen_result = c.generate_cohort(cohort_id, KHNMC['sourceKey'])
        print(f'    Generate triggered: {gen_result}')
    except Exception as e:
        print(f'    ERR: {e}')
        return

    # 3. Wait for completion (max 5 min)
    print(f'\n[3] Waiting for generation...')
    for i in range(30):  # 30 × 10s = 5min
        time.sleep(10)
        info = c.get_cohort_generation_info(cohort_id)
        if isinstance(info, list) and info:
            status_entries = [x for x in info if x.get('sourceKey') == KHNMC['sourceKey']]
            if status_entries:
                st = status_entries[0].get('status', '?')
                print(f'    [{i*10}s] status: {st}')
                if st in ('COMPLETE', 'FAILED'):
                    print(f'    Final: {json.dumps(status_entries[0], indent=2, ensure_ascii=False)}')
                    return

    print('    Timeout after 5 min')


if __name__ == '__main__':
    main()
