import sys
sys.path.insert(0, r'G:\My Drive\KHNMC\atlas_auto_with_claude\automation')
from credentials import get_feedernet_credentials

"""
Phase B Clinical: Build v4_5_clinical estimation.

Same pattern as v4_phase_b_build.py but for clinical outcomes.
Root fix for 11019 FATAL error: fetch_cohort_def() fills expression for all 11 outcomes.

Output: data/v4_clinical_estimation.json = {name: atlas_id}
"""
import os, sys, json, io, functools
print = functools.partial(print, flush=True)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

BASE_ATLAS_ID = 212  # biomarker_changed_final_v3 (same as v4 biomarker — guarantees same T/C cohort)
KHNMC_GROUP = 7
KHNMC_SITE = 203

V5_ESTIMATIONS = {
    'v4_5_clinical': [1077, 1078, 1079, 1080, 1090, 1092, 1093, 1094, 1097, 1271, 1285],
    # UC, CD, Asthma, Atopic, RA, CDI, Parkinson, BilCalc, CRC, AMI_v2, T2DM_v3
}

TARGET_ID = 1072
COMPARATOR_IDS = [1074, 1121]  # Chole + Hernia (GenPop 1076 EXCLUDED)

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'v4_clinical_estimation.json')


def fetch_cohort_def(client, cohort_id):
    r = client.session.get(f'{client.webapi_url}/cohortdefinition/{cohort_id}', timeout=30)
    r.raise_for_status()
    d = r.json()
    expr = d.get('expression')
    if isinstance(expr, str):
        expr = json.loads(expr)
    return {
        'id': d['id'],
        'name': d.get('name', f'cohort_{cohort_id}').strip(),
        'expression': expr,
    }


def build_estimation(client, est_name, outcome_ids):
    print(f'\n=== Build: {est_name} (outcomes={len(outcome_ids)}) ===')

    # 1. Copy base 212
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

    # 3a. cohortDefinitions: keep needed IDs, fetch missing with full expression
    needed_ids = {TARGET_ID} | set(COMPARATOR_IDS) | set(outcome_ids)
    kept_cds = [cd for cd in spec.get('cohortDefinitions', []) if cd['id'] in needed_ids]
    have_ids = {cd['id'] for cd in kept_cds}

    missing = needed_ids - have_ids
    print(f'  cohortDefs: keep {len(kept_cds)}, fetch {len(missing)} more')
    for cid in sorted(missing):
        cd = fetch_cohort_def(client, cid)
        kept_cds.append(cd)
        print(f'    + fetched {cid}: {cd["name"][:50]}')

    # Also ensure outcome cohorts have expression (root fix for 214 FATAL)
    enriched_cds = []
    for cd in kept_cds:
        if cd['id'] in outcome_ids and not cd.get('expression'):
            print(f'    ! outcome {cd["id"]} missing expression → refetch')
            cd = fetch_cohort_def(client, cd['id'])
        enriched_cds.append(cd)
    spec['cohortDefinitions'] = enriched_cds

    # 3b. targetComparatorOutcomes: new (T=1072 × 2 comparators × 11 outcomes)
    cma = spec['estimationAnalysisSettings']['analysisSpecification']
    old_tcos = cma.get('targetComparatorOutcomes', [])
    templates = {t.get('comparatorId'): t for t in old_tcos}
    new_tcos = []
    for cid in COMPARATOR_IDS:
        tmpl = templates.get(cid, old_tcos[0] if old_tcos else {})
        new_tco = dict(tmpl)
        new_tco['targetId'] = TARGET_ID
        new_tco['comparatorId'] = cid
        new_tco['outcomeIds'] = list(outcome_ids)
        new_tcos.append(new_tco)
    cma['targetComparatorOutcomes'] = new_tcos
    print(f'  TCOs: {len(new_tcos)} (T=1072 × [{",".join(str(c) for c in COMPARATOR_IDS)}])')

    # 3b-2. Trim conceptSetCrossReference entries with targetIndex >= len(TCOs)
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

    # 3c. stopOnError=False
    for cmal in cma.get('cohortMethodAnalysisList', []):
        if 'createPsArgs' in cmal:
            cmal['createPsArgs']['stopOnError'] = False
    print(f'  stopOnError=False set')

    # 3d. Verify NC/exclude presence
    cs_list = spec.get('conceptSets', [])
    nc_cs = next((cs for cs in cs_list if 'negative_control' in cs.get('name', '').lower()), None)
    ex_cs = next((cs for cs in cs_list if 'exclude' in cs.get('name', '').lower()), None)
    assert nc_cs is not None, f'{est_name}: no NC conceptSet found'
    assert ex_cs is not None, f'{est_name}: no exclude conceptSet found'
    nc_items = len(nc_cs.get('expression', {}).get('items', []))
    ex_items = len(ex_cs.get('expression', {}).get('items', []))
    print(f'  conceptSets: NC={nc_items}items, exclude={ex_items}items')

    # 3e. Strip newlines from concept set names
    for cs in spec.get('conceptSets', []):
        cs['name'] = cs.get('name', '').strip()

    # 4. PUT
    est_data['name'] = f'AD_{est_name}_v4'
    est_data['specification'] = json.dumps(spec)
    r = client.session.put(f'{client.webapi_url}/estimation/{new_id}', json=est_data, timeout=60)
    if r.status_code != 200:
        print(f'  ❌ PUT failed {r.status_code}: {r.text[:200]}')
        raise RuntimeError(f'PUT failed for {est_name}')
    print(f'  ✅ PUT OK, name = AD_{est_name}_v4')

    # 5. Validate /export
    r = client.session.get(f'{client.webapi_url}/estimation/{new_id}/export', timeout=60)
    print(f'  /export: {r.status_code}, size={len(r.content)}')
    if r.status_code != 200:
        raise RuntimeError(f'/export failed — possibly crossRef or outcome cohort issue')

    # 6. Final check GET
    r = client.session.get(f'{client.webapi_url}/estimation/{new_id}', timeout=30)
    d = r.json()
    vspec = json.loads(d['specification'])
    cds = vspec.get('cohortDefinitions', [])
    n_filled = sum(1 for cd in cds if isinstance(cd.get('expression'), dict))
    tcos = vspec['estimationAnalysisSettings']['analysisSpecification']['targetComparatorOutcomes']
    print(f'  ✅ Validate: cohortDefs={len(cds)} ({n_filled} filled), TCOs={len(tcos)}, outcomeIds/TCO={len(tcos[0]["outcomeIds"])}')

    return new_id


def main():
    c = FedernetClient()
    c.login_portal(*get_feedernet_credentials())
    c.connect_site(group_id=KHNMC_GROUP, site_id=KHNMC_SITE)

    results = {}
    for est_name, outcome_ids in V5_ESTIMATIONS.items():
        try:
            new_id = build_estimation(c, est_name, outcome_ids)
            results[est_name] = new_id
        except Exception as e:
            print(f'❌ {est_name} failed: {e}')
            results[est_name] = None

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f'\n=== Output: {OUT_PATH} ===')
    for name, aid in results.items():
        print(f'  {name}: atlas_id={aid}')


if __name__ == '__main__':
    main()
