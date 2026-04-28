"""
v4 / v4.2 estimation 현재 상태를 monitor_state.json 스냅샷에서 읽어 출력.

- API 호출 없이 마지막 poll 결과만 표시 (빠름, 무해).
- 라이브 상태 필요하면 `python v4_phase_e_monitor.py [--pid ... --map ... --state ...]` 재실행.

CLI:
  # default (v4.1)
  python v4_status_show.py
  # v4.2
  python v4_status_show.py --map data/v4_2_analysis_map.json --state data/v4_2_monitor_state.json

출력:
  analysis × status 집계, FAILED/WAITING per-site 상세, last_poll age.
"""
import os
import sys
import json
import datetime
import functools
import argparse

print = functools.partial(print, flush=True)

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, '..', 'v4_monitor_state.json')
ANA_MAP_PATH = os.path.join(HERE, '..', 'v4_analysis_map.json')
SITE_MAP_PATH = os.path.join(HERE, '..', 'site_mapping', 'site_id_mapping_full.csv')


def load_site_map():
    m = {}
    if not os.path.exists(SITE_MAP_PATH):
        return m
    import csv
    with open(SITE_MAP_PATH, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                m[int(r['cdmId'])] = r['code']
            except (KeyError, ValueError):
                pass
    return m


def main():
    parser = argparse.ArgumentParser(description='Show v4 / v4.2 estimation snapshot')
    parser.add_argument('--map', dest='map_path', default=ANA_MAP_PATH, help='analysis map JSON path')
    parser.add_argument('--state', dest='state_path', default=STATE_PATH, help='state JSON path')
    args = parser.parse_args()

    if not os.path.exists(args.state_path):
        print(f'(no state file: {args.state_path})')
        sys.exit(0)
    with open(args.state_path, encoding='utf-8') as f:
        state = json.load(f)
    with open(args.map_path, encoding='utf-8') as f:
        ana_map = json.load(f)
    sites = load_site_map()

    aid_to_name = {str(v['analysis_id']): k for k, v in ana_map.items()}

    now = datetime.datetime.now(datetime.timezone.utc)
    print('=== v4 estimation status (from snapshot) ===\n')
    print(f'{"analysis":22s}  {"C":>3s} {"R":>3s} {"W":>3s} {"F":>3s} {"X":>3s}  {"total":>5s}  last_poll(age)')
    print('-' * 90)

    for aid, st in sorted(state.items(), key=lambda x: int(x[0])):
        name = aid_to_name.get(aid, f'aid={aid}')
        counts = st.get('counts') or {}
        if not counts:
            print(f'{name:22s}  (no snapshot — run v4_phase_e_monitor.py to populate)')
            continue
        c = counts.get('COMPLETE', 0)
        r = counts.get('RUNNING', 0)
        w = counts.get('WAITING', 0)
        fa = counts.get('FAILED', 0)
        x = counts.get('CANCELED', 0)
        total = c + r + w + fa + x
        lp = st.get('last_poll', '?')
        try:
            lp_dt = datetime.datetime.fromisoformat(lp.replace('Z', '+00:00'))
            age = now - lp_dt
            age_str = f'{int(age.total_seconds()//60)}m ago'
        except Exception:
            age_str = f'{lp}'
        print(f'{name:22s}  {c:3d} {r:3d} {w:3d} {fa:3d} {x:3d}  {total:5d}  {lp} ({age_str})')

    # Per-site breakdown of non-complete sites (aggregate across analyses)
    print('\n=== Non-complete sites (aggregate across all analyses) ===\n')
    site_ana_status = {}  # cdm → {analysis: status}
    for aid, st in state.items():
        cur = st.get('current_status') or {}
        ana_name = aid_to_name.get(aid, aid)
        for cdm, info in cur.items():
            s = info.get('status')
            if s in ('COMPLETE',):
                continue
            site_ana_status.setdefault(cdm, {})[ana_name] = s

    if not site_ana_status:
        print('  (none — all 22 sites COMPLETE in all analyses)')
        return

    for cdm, by_ana in sorted(site_ana_status.items(), key=lambda x: int(x[0])):
        code = sites.get(int(cdm), '?')
        print(f'  cdm={cdm:<4s} ({code})')
        for ana, s in by_ana.items():
            print(f'     {s:10s}  {ana}')

    # Summary of sites reaching full 6/6 complete
    full_complete = set()
    any_seen = set()
    for aid, st in state.items():
        cur = st.get('current_status') or {}
        ana_name = aid_to_name.get(aid, aid)
        for cdm, info in cur.items():
            any_seen.add(cdm)
            if info.get('status') != 'COMPLETE':
                site_ana_status.setdefault(cdm, {})[ana_name] = info.get('status')
    for cdm in any_seen:
        non_complete = site_ana_status.get(cdm, {})
        if not non_complete:
            full_complete.add(cdm)
    print(f'\nSites with ALL 6 analyses COMPLETE: {len(full_complete)} / {len(any_seen)}')


if __name__ == '__main__':
    main()
