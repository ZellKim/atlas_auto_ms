import sys
sys.path.insert(0, r'G:\My Drive\KHNMC\atlas_auto_with_claude\automation')
from credentials import get_feedernet_credentials

"""
Phase C: Deploy 5 v4 estimations to feedernet project 5115.

For each of 5:
1. Create analysis (POST /projects/{pid}/analysis)
2. Get atlas list (GET /projects/{pid}/analysis/{aid}/atlas) → find KHNMC site
3. Import estimation (POST /projects/{pid}/analysis/{aid}/atlas/{atlasSiteId})

Output: data/v4_analysis_map.json = {est_name: {atlas_id, analysis_id, atlas_site_id}}
"""
import os, sys, json, io, time, functools
print = functools.partial(print, flush=True)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

PROJECT_ID = 5115  # appendectomy_v4
KHNMC_GROUP = 7
KHNMC_SITE = 203

EST_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'v4_atlas_estimations.json')
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'v4_analysis_map.json')


def find_khnmc_atlas(atlas_list):
    """Find the KHNMC entry in the atlas list. atlasId == KHNMC_SITE (203)."""
    for a in atlas_list:
        if a.get('atlasId') == KHNMC_SITE:
            return a
    return None


def deploy(client, est_name, atlas_id):
    base = client.portal_url
    s = client.session
    print(f'\n=== Deploy: {est_name} (ATLAS id={atlas_id}) ===')

    # 1. Create analysis (or reuse existing by name)
    analysis_name = f'AD_{est_name}_v4'
    r2 = s.get(f'{base}/api/v1/projects/{PROJECT_ID}/analysis', timeout=15)
    analyses = r2.json().get('content', [])
    fed_aid = None
    for a in analyses:
        if a.get('name') == analysis_name:
            fed_aid = a.get('id')
            print(f'  reuse existing analysis: {fed_aid}')
            break
    if fed_aid is None:
        r = s.post(f'{base}/api/v1/projects/{PROJECT_ID}/analysis',
                   json={'name': analysis_name, 'analysisType': 'ESTIMATION'},
                   timeout=30)
        print(f'  create analysis: {r.status_code}')
        if r.status_code != 200:
            print(f'    {r.text[:200]}')
        time.sleep(1)
        r2 = s.get(f'{base}/api/v1/projects/{PROJECT_ID}/analysis', timeout=15)
        analyses = r2.json().get('content', [])
        for a in analyses:
            if a.get('name') == analysis_name:
                fed_aid = a.get('id')
                break
        if fed_aid is None:
            raise RuntimeError(f'Could not find created analysis {analysis_name}')
        print(f'  analysis id: {fed_aid}')

    # 2. Get atlas list → find KHNMC
    r3 = s.get(f'{base}/api/v1/projects/{PROJECT_ID}/analysis/{fed_aid}/atlas', timeout=15)
    atlas_list = r3.json().get('content', []) if r3.status_code == 200 else []
    khnmc = find_khnmc_atlas(atlas_list)
    if khnmc is None:
        print(f'  atlas entries: {[a.get("name") for a in atlas_list[:5]]}')
        raise RuntimeError('KHNMC atlas not found in analysis')
    atlas_site_id = khnmc.get('atlasId')
    print(f'  KHNMC atlas site id: {atlas_site_id}')

    # 3. Import estimation
    r4 = s.post(
        f'{base}/api/v1/projects/{PROJECT_ID}/analysis/{fed_aid}/atlas/{atlas_site_id}',
        json={
            'atlasResearchId': atlas_id,
            'atlasResearchName': analysis_name,
            'researchType': 'ESTIMATION',
        },
        timeout=60,
    )
    print(f'  import estimation: {r4.status_code}')
    if r4.status_code != 200:
        print(f'    {r4.text[:300]}')
        raise RuntimeError('estimation import failed')
    print(f'  ✅ Imported')

    return {'atlas_id': atlas_id, 'analysis_id': fed_aid, 'atlas_site_id': atlas_site_id,
            'analysis_name': analysis_name}


def main():
    with open(EST_MAP_PATH, encoding='utf-8') as f:
        est_map = json.load(f)
    print(f'Estimations to deploy: {est_map}')

    c = FedernetClient()
    c.login_portal(*get_feedernet_credentials())
    c.connect_site(group_id=KHNMC_GROUP, site_id=KHNMC_SITE)

    # Verify project
    r = c.session.get(f'{c.portal_url}/api/v1/projects/{PROJECT_ID}', timeout=15)
    print(f'Project {PROJECT_ID}: {r.status_code}')

    results = {}
    for est_name, atlas_id in est_map.items():
        if atlas_id is None:
            print(f'  skip {est_name}: atlas_id=None')
            continue
        try:
            info = deploy(c, est_name, atlas_id)
            results[est_name] = info
        except Exception as e:
            print(f'  ❌ {est_name}: {e}')
            results[est_name] = {'error': str(e), 'atlas_id': atlas_id}

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f'\n=== Saved {OUT_PATH} ===')
    for name, info in results.items():
        print(f'  {name}: {info}')


if __name__ == '__main__':
    main()
