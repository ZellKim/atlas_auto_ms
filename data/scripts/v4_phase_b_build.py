import sys
sys.path.insert(0, r'G:\My Drive\KHNMC\atlas_auto_with_claude\automation')
from credentials import get_feedernet_credentials

"""
Phase B: Build 5 v4 estimation by copying ATLAS 212 (biomarker_v3) base.

For each of 5 estimations:
1. Copy 212 → new ATLAS estimation ID
2. Modify spec: cohortDefinitions, targetComparatorOutcomes, stopOnError=False, name
3. PUT back
4. Validate

Output: data/v4_atlas_estimations.json = {estimation_name: atlas_id}
"""
import os, sys, json, io, time, functools
print = functools.partial(print, flush=True)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

BASE_ATLAS_ID = 212  # biomarker_changed_final_v3 = feedernet 11018
KHNMC_GROUP = 7
KHNMC_SITE = 203

# V4 5 estimation outcome mapping (cohort IDs at KHNMC ATLAS)
V4_ESTIMATIONS = {
    'v4_1a_cbc_wbc': [1357, 1390, 1391, 1392, 1360, 1385, 1373, 1374],
    # WBC_high, Neutro#_thou, Neutro#_uL, Neutro%, Lympho_low, Lympho_high, Eosino#_thou, Eosino#_uL
    'v4_1b_cbc_rbc': [1375, 1362, 1368, 1358, 1387, 1395, 1394, 1393],
    # Eosino%, Mono_v2, Baso%, MCV_low, MCV_high, RDW, Platelet_low, Platelet_high
    'v4_2_chem_hepa': [1370, 1369, 1364, 1365, 1363, 1400, 1366, 1381, 1384, 1397, 1396],
    # CRP_mgdL, CRP_mgL, ALT, AST, ALP, TotBili, Albumin, HbA1c, LDL, TG, TC
    'v4_3_meta_endo': [1378, 1379, 1402, 1401, 1367, 1399, 1398, 1404],
    # GlucDM, GlucPreDM, TotProt_low, TotProt_high, BUN, TSH_low, TSH_high, VitD
    'v4_4_sex_specific': [1361, 1382, 1376, 1377, 1372, 1403, 1380, 1371],
    # Hgb, Hct, Ferritin, GGT, ESR, UA, HDL, Creatinine
}

TARGET_ID = 1072
COMPARATOR_IDS = [1074, 1121]  # Chole + Hernia (GenPop 1076 EXCLUDED)

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'v4_atlas_estimations.json')


def fetch_cohort_def(client, cohort_id):
    """GET /cohortdefinition/{id} → standardized dict for spec inclusion"""
    r = client.session.get(f'{client.webapi_url}/cohortdefinition/{cohort_id}', timeout=30)
    r.raise_for_status()
    d = r.json()
    expr = d.get('expression')
    if isinstance(expr, str):
        expr = json.loads(expr)
    return {
        'id': d['id'],
        'name': d.get('name', f'cohort_{cohort_id}').strip(),  # strip \n
        'expression': expr,
    }


def build_estimation(client, est_name, outcome_ids, base_spec_str, base_data):
    """Build one estimation by copying 212 and modifying."""
    print(f'\n=== Build: {est_name} (outcomes={len(outcome_ids)}) ===')

    # 1. Copy
    r = client.session.get(f'{client.webapi_url}/estimation/{BASE_ATLAS_ID}/copy', timeout=30)
    r.raise_for_status()
    copy_resp = r.json()
    new_id = copy_resp['id']
    print(f'  copied → new ATLAS id: {new_id}')

    # 2. Fetch the copied estimation
    r = client.session.get(f'{client.webapi_url}/estimation/{new_id}', timeout=30)
    r.raise_for_status()
    est_data = r.json()
    spec = json.loads(est_data['specification'])

    # 3. Modify spec
    # 3a. cohortDefinitions: filter to needed IDs only
    needed_ids = {TARGET_ID} | set(COMPARATOR_IDS) | set(outcome_ids)
    kept_cds = [cd for cd in spec.get('cohortDefinitions', []) if cd['id'] in needed_ids]
    have_ids = {cd['id'] for cd in kept_cds}

    # Fetch missing cohortDefinitions (v4b outcomes)
    missing = needed_ids - have_ids
    print(f'  cohortDefs: keep {len(kept_cds)}, fetch {len(missing)} more')
    for cid in sorted(missing):
        cd = fetch_cohort_def(client, cid)
        kept_cds.append(cd)
        print(f'    + fetched {cid}: {cd["name"][:50]}')
    spec['cohortDefinitions'] = kept_cds

    # 3b. targetComparatorOutcomes: replace with new (T=1072 × 2 comparators × outcomes)
    cma = spec['estimationAnalysisSettings']['analysisSpecification']
    old_tcos = cma.get('targetComparatorOutcomes', [])
    # Use existing TCO as template (preserve covariate settings)
    templates = {}
    for t in old_tcos:
        templates[t.get('comparatorId')] = t
    new_tcos = []
    for cid in COMPARATOR_IDS:
        tmpl = templates.get(cid, old_tcos[0] if old_tcos else {})
        new_tco = dict(tmpl)  # shallow copy
        new_tco['targetId'] = TARGET_ID
        new_tco['comparatorId'] = cid
        new_tco['outcomeIds'] = list(outcome_ids)
        new_tcos.append(new_tco)
    cma['targetComparatorOutcomes'] = new_tcos
    print(f'  TCOs: {len(new_tcos)} (T=1072 × [{",".join(str(c) for c in COMPARATOR_IDS)}])')

    # 3b-2. Trim conceptSetCrossReference entries with targetIndex >= len(TCOs)
    # Both targetComparatorOutcomes AND negativeControlOutcomes are per-TCO arrays.
    # Dropping GenPop TCO invalidates crossRef at idx=2 → IndexOutOfBoundsException on /export.
    xrefs = spec.get('conceptSetCrossReference', [])
    kept_xrefs = []
    dropped = 0
    for x in xrefs:
        tidx = x.get('targetIndex', 0)
        if tidx >= len(new_tcos):
            dropped += 1
            continue
        kept_xrefs.append(x)
    spec['conceptSetCrossReference'] = kept_xrefs
    print(f'  crossRef: kept {len(kept_xrefs)}, dropped {dropped} (dangling TCO/NC refs)')

    # 3c. stopOnError=False in all cohortMethodAnalysisList entries
    for cmal in cma.get('cohortMethodAnalysisList', []):
        if 'createPsArgs' in cmal:
            cmal['createPsArgs']['stopOnError'] = False
    print(f'  stopOnError=False set')

    # 3d. Verify NC/exclude concept set presence (items=0 is normal — ATLAS runtime resolve)
    cs_list = spec.get('conceptSets', [])
    nc_cs = next((cs for cs in cs_list if 'negative_control' in cs.get('name','').lower()), None)
    ex_cs = next((cs for cs in cs_list if 'exclude' in cs.get('name','').lower()), None)
    assert nc_cs is not None, f'{est_name}: no NC conceptSet found! Aborting'
    assert ex_cs is not None, f'{est_name}: no exclude conceptSet found! Aborting'
    nc_items = len(nc_cs.get('expression', {}).get('items', []))
    ex_items = len(ex_cs.get('expression', {}).get('items', []))
    print(f'  conceptSets: NC={nc_items}items (OK if 0, ATLAS resolve), exclude={ex_items}items')

    # 3e. Strip newlines from concept set names
    for cs in spec.get('conceptSets', []):
        cs['name'] = cs.get('name','').strip()

    # 4. PUT
    est_data['name'] = f'AD_{est_name}_v4'
    est_data['specification'] = json.dumps(spec)

    r = client.session.put(f'{client.webapi_url}/estimation/{new_id}', json=est_data, timeout=60)
    if r.status_code != 200:
        print(f'  ❌ PUT failed {r.status_code}: {r.text[:200]}')
        raise RuntimeError(f'PUT failed for {est_name}')
    print(f'  ✅ PUT OK, name = AD_{est_name}_v4')

    # 5. Validate via GET + /export
    r = client.session.get(f'{client.webapi_url}/estimation/{new_id}', timeout=30)
    d = r.json()
    vspec = json.loads(d['specification'])
    cds = vspec.get('cohortDefinitions', [])
    tcos = vspec['estimationAnalysisSettings']['analysisSpecification']['targetComparatorOutcomes']
    print(f'  ✅ Validate: cohortDefs={len(cds)}, TCOs={len(tcos)}, '
          f'outcomeIds per TCO = {len(tcos[0]["outcomeIds"])}')

    return new_id


def main():
    c = FedernetClient()
    c.login_portal(*get_feedernet_credentials())
    c.connect_site(group_id=KHNMC_GROUP, site_id=KHNMC_SITE)

    # Fetch base 212 once to verify
    r = c.session.get(f'{c.webapi_url}/estimation/{BASE_ATLAS_ID}', timeout=30)
    r.raise_for_status()
    base_data = r.json()
    base_spec_str = base_data['specification']
    print(f'Base: {base_data.get("name")} (id={BASE_ATLAS_ID})')

    results = {}
    for est_name, outcome_ids in V4_ESTIMATIONS.items():
        try:
            new_id = build_estimation(c, est_name, outcome_ids, base_spec_str, base_data)
            results[est_name] = new_id
        except Exception as e:
            print(f'❌ {est_name} failed: {e}')
            results[est_name] = None

    # Save mapping
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f'\n=== Output: {OUT_PATH} ===')
    for name, aid in results.items():
        print(f'  {name}: atlas_id={aid}')


if __name__ == '__main__':
    main()
