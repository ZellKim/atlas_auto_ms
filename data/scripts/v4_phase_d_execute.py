import sys
sys.path.insert(0, r'G:\My Drive\KHNMC\atlas_auto_with_claude\automation')
from credentials import get_feedernet_credentials

"""
Phase D: Trigger 22-site execution for each of 5 v4 analyses in project 5115.

For each analysis:
  POST /api/v1/project/{pid}/analysis/{aid}/execution  (singular 'project'!)
  body: {cdmIds: [all 22], researchName, executionType: 'ESTIMATION'}

Input: data/v4_analysis_map.json
Output: data/v4_execution_trigger_log.json
"""
import os, sys, json, io, time, functools, csv
print = functools.partial(print, flush=True)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

PROJECT_ID = 5115
SITE_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                           'data', 'site_mapping', 'site_id_mapping_full.csv')
ANA_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                              'v4_analysis_map.json')
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                          'v4_execution_trigger_log.json')


# MJH excluded: observation_period median 53d, 46.5% < 30d → 1 pt qualifies (commit 092522c)
EXCLUDED_CODES = {'MJH'}


def load_all_cdm_ids():
    """Load all site cdmIds excluding known-bad (MJH)."""
    cdm_ids = []
    codes = []
    with open(SITE_MAP, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            code = r.get('code', '').strip()
            cid = r.get('cdmId', '').strip()
            if not cid or code in EXCLUDED_CODES:
                continue
            cdm_ids.append(int(cid))
            codes.append(code)
    return cdm_ids, codes


def trigger(client, est_name, info, cdm_ids):
    aid = info['analysis_id']
    name = info['analysis_name']
    base = client.portal_url
    s = client.session
    print(f'\n=== Execute: {est_name} (analysis {aid}) — {len(cdm_ids)} sites ===')

    r = s.post(
        f'{base}/api/v1/project/{PROJECT_ID}/analysis/{aid}/execution',
        json={
            'cdmIds': cdm_ids,
            'researchName': name,
            'executionType': 'ESTIMATION',
        },
        timeout=30,
    )
    print(f'  trigger: {r.status_code}')
    try:
        body = r.json()
    except Exception:
        body = {'raw': r.text[:300]}
    print(f'  resp: {json.dumps(body, ensure_ascii=False)[:500]}')
    return {'status_code': r.status_code, 'body': body}


def main():
    with open(ANA_MAP_PATH, encoding='utf-8') as f:
        ana_map = json.load(f)
    cdm_ids, codes = load_all_cdm_ids()
    print(f'Target {len(cdm_ids)} sites: {codes}')

    c = FedernetClient()
    c.login_portal(*get_feedernet_credentials())

    results = {}
    for est_name, info in ana_map.items():
        if info.get('error'):
            print(f'  skip {est_name}: {info.get("error")}')
            continue
        try:
            r = trigger(c, est_name, info, cdm_ids)
            results[est_name] = r
        except Exception as e:
            print(f'  ❌ {est_name}: {e}')
            results[est_name] = {'error': str(e)}
        time.sleep(2)  # space out triggers

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f'\n=== Saved {OUT_PATH} ===')


if __name__ == '__main__':
    main()
