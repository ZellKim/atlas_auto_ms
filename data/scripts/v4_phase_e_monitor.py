"""
Phase E: Local monitor for v4 / v4.2 executions.

Each invocation (manual or scheduled every 1h):
  1. Poll each analysis → per-site execution status
  2. On FAILED with retry_count < 2 → re-trigger that site
  3. On first FINISHED_SUCCESSFULLY per analysis → download result.zip
  4. Log progress (Telegram handled by cloud_monitor separately)
  5. Persist state in --state path

CLI:
  # default = v4.1 (PID 5115)
  python v4_phase_e_monitor.py
  # v4.2 (PID 5126):
  python v4_phase_e_monitor.py --pid 5126 \
    --map data/v4_2_analysis_map.json \
    --state data/v4_2_monitor_state.json \
    --results "C:\\Users\\data1\\Desktop\\atlas_auto_cmdata\\v4_2_results"

State format:
  {
    "11034": {
      "retries": {"535": 1, ...},      # cdmId → retry count
      "downloaded": {"583": true, ...},# cdmId → already downloaded?
      "last_poll": "2026-04-18T14:00Z",
      "current_status": {...},         # per-cdm latest meaningful status
      "counts": {...}
    }, ...
  }

CANCELED handling: a CANCELED execution with startedAt=None AND completedAt=None
preceded by an earlier execution for the same cdm is treated as a "preempted-
duplicate" (e.g. bulk-POST verification trigger that was canceled before starting)
and is IGNORED — the latest meaningful prior execution is reported instead.
This pattern was introduced after the 2026-04-26 v4.2 bulk POST safety test
where 110 verification executions were intentionally canceled. See KB §2.4a.
"""
import os, sys, json, io, time, functools, csv, datetime, argparse
print = functools.partial(print, flush=True)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

MAX_RETRIES = 2
HERE = os.path.dirname(os.path.abspath(__file__))

# Defaults (v4.1) — overridable via CLI args. Module-level so handle_analysis can read.
PROJECT_ID = 5115
RESULT_DIR = r'C:\Users\data1\Desktop\atlas_auto_cmdata\v4_results'
ANA_MAP_PATH = os.path.join(HERE, '..', 'v4_analysis_map.json')
STATE_PATH = os.path.join(HERE, '..', 'v4_monitor_state.json')
LOG_PATH = os.path.join(HERE, '..', 'v4_monitor_log.csv')


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_execution_groups(client, aid):
    """Return raw groups (content[]) with executionList[]."""
    r = client.session.get(
        f'{client.portal_url}/api/v1/project/{PROJECT_ID}/analysis/{aid}/execution',
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get('content', [])


def flatten_latest_per_cdm(groups):
    """Build {cdmId: latest_meaningful_execution_dict}.

    Rule: collect all executions per cdmId, sort by eid asc.
      - If the latest is a 'preempted-duplicate' CANCELED (status==CANCELED AND
        startedAt is None AND completedAt is None) AND there is at least one
        earlier execution for that cdm → return the latest non-preempted-CANCELED
        execution instead.
      - Otherwise → return the actual latest.

    Why: 2026-04-26 v4.2 bulk POST safety test intentionally canceled 110
    verification executions. Reporting their CANCELED state as the live status
    triggered a false "v4.2 폭망" alarm. See docs/system_knowledge_base.md §2.4a.
    """
    by_cdm = {}
    for g in groups:
        for ex in g.get('executionList', []):
            cdm_id = ex.get('cdmId')
            if cdm_id is None:
                continue
            by_cdm.setdefault(cdm_id, []).append(ex)
    latest = {}
    for cdm_id, execs in by_cdm.items():
        execs_sorted = sorted(execs, key=lambda e: (e.get('id') or 0))
        chosen = execs_sorted[-1]
        if (
            len(execs_sorted) >= 2
            and chosen.get('executionStatus') == 'CANCELED'
            and chosen.get('startedAt') is None
            and chosen.get('completedAt') is None
        ):
            # Walk back to most recent non-preempted-CANCELED execution.
            for ex in reversed(execs_sorted[:-1]):
                if not (
                    ex.get('executionStatus') == 'CANCELED'
                    and ex.get('startedAt') is None
                    and ex.get('completedAt') is None
                ):
                    chosen = ex
                    break
        latest[cdm_id] = chosen
    return latest


def classify(status):
    if status == 'FINISHED_SUCCESSFULLY':
        return 'COMPLETE'
    if status in ('EXECUTING_DOCKER', 'RUNNING'):
        return 'RUNNING'
    if status == 'WAITING':
        return 'WAITING'
    if status == 'CANCELED':
        return 'CANCELED'
    return 'FAILED'


def re_trigger_site(client, aid, research_name, cdm_id):
    r = client.session.post(
        f'{client.portal_url}/api/v1/project/{PROJECT_ID}/analysis/{aid}/execution',
        json={'cdmIds': [cdm_id], 'researchName': research_name, 'executionType': 'ESTIMATION'},
        timeout=30,
    )
    return r.status_code, r.text[:200]


def list_files(client, aid, eid):
    r = client.session.get(
        f'{client.portal_url}/api/v1/project/{PROJECT_ID}/analysis/{aid}/execution/{eid}/files',
        timeout=30,
    )
    if r.status_code != 200:
        return []
    body = r.json()
    content = body.get('content', []) if isinstance(body, dict) else body
    return content or []


def download_file(client, aid, eid, fid, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    r = client.session.get(
        f'{client.portal_url}/api/v1/project/{PROJECT_ID}/analysis/{aid}/execution/{eid}/files/{fid}/download',
        stream=True, timeout=180,
    )
    if r.status_code != 200:
        return False, r.status_code
    with open(out_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    return True, os.path.getsize(out_path)


def handle_analysis(client, est_name, info, state):
    aid = info['analysis_id']
    research_name = info['analysis_name']
    print(f'\n=== Poll: {est_name} (aid={aid}) ===')

    st = state.setdefault(str(aid), {'retries': {}, 'downloaded': {}, 'last_poll': None})
    st['last_poll'] = datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z'

    try:
        groups = get_execution_groups(client, aid)
    except Exception as e:
        print(f'  poll error: {e}')
        return

    latest = flatten_latest_per_cdm(groups)
    counts = {'COMPLETE': 0, 'RUNNING': 0, 'WAITING': 0, 'FAILED': 0, 'CANCELED': 0}
    failed_sites = []  # (cdm_id, orgName)
    waiting_ranks = []  # (rank, cdm_id)
    per_site = {}  # cdm_id(str) → {'status', 'orgName', 'waitingRank', 'executionId'}
    for cdm_id, ex in latest.items():
        tag = classify(ex.get('executionStatus', ''))
        counts[tag] += 1
        if tag == 'FAILED':
            failed_sites.append((cdm_id, ex.get('orgName', '?')))
        if tag == 'WAITING':
            waiting_ranks.append((ex.get('waitingRank'), cdm_id))
        per_site[str(cdm_id)] = {
            'status': tag,
            'orgName': ex.get('orgName', '?'),
            'waitingRank': ex.get('waitingRank'),
            'executionId': ex.get('id'),
        }

    # Persist live snapshot (not just retries/downloaded) so status can be read without re-polling.
    st['current_status'] = per_site
    st['counts'] = counts

    total = sum(counts.values())
    print(f'  total={total} {counts}')
    if waiting_ranks:
        waiting_ranks.sort(key=lambda x: (x[0] is None, x[0]))
        head = waiting_ranks[:3]
        tail = waiting_ranks[-1:] if len(waiting_ranks) > 3 else []
        preview = ', '.join(f'cdm{c}=#{r}' for r, c in head) + (f' ... cdm{tail[0][1]}=#{tail[0][0]}' if tail else '')
        print(f'  waitingRank (전체 큐): {preview}')

    # Auto-download: first COMPLETE per analysis, skip if already downloaded
    downloaded_any_new = False
    if not SKIP_DOWNLOAD:
        for cdm_id, ex in latest.items():
            if classify(ex.get('executionStatus', '')) != 'COMPLETE':
                continue
            sid = str(cdm_id)
            if st['downloaded'].get(sid):
                continue
            eid = ex.get('id')
            org = ex.get('orgName', f'cdm_{cdm_id}')
            safe_org = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in str(org))[:50]
            files = list_files(client, aid, eid)
            if not files:
                continue
            fid = files[0].get('id')
            if fid is None:
                continue
            out_dir = os.path.join(RESULT_DIR, est_name)
            out_path = os.path.join(out_dir, f'{safe_org}_{cdm_id}_result.zip')
            print(f'  ⬇ download {org} (cdm={cdm_id}, eid={eid}) → {out_path}')
            ok, size = download_file(client, aid, eid, fid, out_path)
            if ok:
                print(f'     OK {size/1024:.0f} KB')
                st['downloaded'][sid] = True
                downloaded_any_new = True
            else:
                print(f'     FAIL {size}')

    # Retry FAILED sites up to MAX_RETRIES
    retries_done = 0
    if not SKIP_RETRY:
        for cdm_id, org in failed_sites:
            sid = str(cdm_id)
            n = int(st['retries'].get(sid, 0))
            if n >= MAX_RETRIES:
                continue
            code, body = re_trigger_site(client, aid, research_name, cdm_id)
            st['retries'][sid] = n + 1
            retries_done += 1
            print(f'  ↻ retry #{n+1} {org} (cdm={cdm_id}): {code}')

    print(f'  retries_done_this_run={retries_done}, new_downloads={1 if downloaded_any_new else 0}')


SKIP_DOWNLOAD = False
SKIP_RETRY = False


def main():
    global PROJECT_ID, RESULT_DIR, ANA_MAP_PATH, STATE_PATH, SKIP_DOWNLOAD, SKIP_RETRY
    parser = argparse.ArgumentParser(description='v4 / v4.2 estimation monitor')
    parser.add_argument('--pid', type=int, default=PROJECT_ID, help=f'feedernet project_id (default {PROJECT_ID})')
    parser.add_argument('--map', dest='map_path', default=ANA_MAP_PATH, help='analysis map JSON path')
    parser.add_argument('--state', dest='state_path', default=STATE_PATH, help='state JSON path (per-pid)')
    parser.add_argument('--results', dest='results_dir', default=RESULT_DIR, help='download dir for result.zip')
    parser.add_argument('--no-download', action='store_true', help='skip auto-download of result.zip (status only)')
    parser.add_argument('--no-retry', action='store_true', help='skip auto-retry of FAILED sites (status only)')
    args = parser.parse_args()
    PROJECT_ID = args.pid
    ANA_MAP_PATH = args.map_path
    STATE_PATH = args.state_path
    RESULT_DIR = args.results_dir
    SKIP_DOWNLOAD = args.no_download
    SKIP_RETRY = args.no_retry
    print(f'[config] pid={PROJECT_ID} map={ANA_MAP_PATH} state={STATE_PATH} results={RESULT_DIR} no_download={SKIP_DOWNLOAD} no_retry={SKIP_RETRY}')

    with open(ANA_MAP_PATH, encoding='utf-8') as f:
        ana_map = json.load(f)

    state = load_state()

    c = FedernetClient()
    c.login_portal('20230172@khnmc.or.kr', 'rlaaudtjr1!')

    for est_name, info in ana_map.items():
        if info.get('error'):
            continue
        try:
            handle_analysis(c, est_name, info, state)
        except Exception as e:
            print(f'❌ {est_name}: {e}')

    save_state(state)
    print(f'\nState saved: {STATE_PATH}')


if __name__ == '__main__':
    main()
