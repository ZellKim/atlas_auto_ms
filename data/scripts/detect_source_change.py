"""
Detect source-level changes between two refresh snapshots.

Compares meta.json sidecars in two directories (e.g., archived old refresh vs
current refresh) and flags changes that would invalidate downstream analyses:
  - source_key changed (different ATLAS instance)
  - source_name changed (ETL version bump)
  - vocabulary release changed
  - total_persons changed > ±5%
  - data_cutoff_month moved backwards (data loss) or jumped forward
  - measurement concept count changed > ±10%

Output: a diff CSV plus stdout summary highlighting concerning changes.

Usage:
  # Compare current vs an archived snapshot
  python detect_source_change.py \\
    --old data/concept_frequency/archive/2026-05-12_pre_next_refresh \\
    --new data/concept_frequency/by_site

  # Or compare two archives
  python detect_source_change.py --old A_dir --new B_dir --out diff.csv
"""
import argparse
import csv
import json
import os
import sys


def load_metas(directory):
    """Return {site_code, domain: meta_dict} for all *.meta.json in dir."""
    out = {}
    if not os.path.isdir(directory):
        return out
    for name in os.listdir(directory):
        if not name.endswith('.meta.json'):
            continue
        try:
            with open(os.path.join(directory, name), encoding='utf-8') as f:
                meta = json.load(f)
            key = (meta.get('site_code', name.split('_')[0]),
                   meta.get('domain', name.replace('.meta.json', '').split('_')[-1]))
            out[key] = meta
        except Exception as e:
            print(f"  [warn] couldn't read {name}: {e}", file=sys.stderr)
    return out


def percent_change(old, new):
    if old is None or new is None: return None
    try:
        old, new = float(old), float(new)
    except (TypeError, ValueError):
        return None
    if old == 0:
        return float('inf') if new != 0 else 0.0
    return (new - old) / old * 100


def compare_one(old, new):
    """Yield change events for one (site,domain) pair."""
    events = []

    # 1. source_key change → CRITICAL (different instance)
    if old.get('source_key') != new.get('source_key'):
        events.append(('CRITICAL', 'source_key changed',
                       f"{old.get('source_key')} → {new.get('source_key')}"))

    # 2. source_name change → CRITICAL (ETL version bump)
    if old.get('source_name') != new.get('source_name'):
        events.append(('CRITICAL', 'source_name changed',
                       f"{old.get('source_name')} → {new.get('source_name')}"))

    # 3. vocabulary release
    if old.get('omop_vocabulary_release') != new.get('omop_vocabulary_release'):
        events.append(('NOTABLE', 'vocabulary release changed',
                       f"{old.get('omop_vocabulary_release')} → {new.get('omop_vocabulary_release')}"))

    # 4. total_persons drift > ±5%
    pct = percent_change(old.get('total_persons'), new.get('total_persons'))
    if pct is not None and abs(pct) > 5:
        sev = 'CRITICAL' if abs(pct) > 20 else 'NOTABLE'
        events.append((sev, f'total_persons changed {pct:+.1f}%',
                       f"{old.get('total_persons')} → {new.get('total_persons')}"))

    # 5. data_cutoff_month
    if old.get('data_cutoff_month') and new.get('data_cutoff_month'):
        if new['data_cutoff_month'] < old['data_cutoff_month']:
            events.append(('CRITICAL', 'cutoff moved backward (data loss)',
                           f"{old['data_cutoff_month']} → {new['data_cutoff_month']}"))

    # 6. rows_returned drift > ±10%
    pct = percent_change(old.get('rows_returned'), new.get('rows_returned'))
    if pct is not None and abs(pct) > 10:
        sev = 'NOTABLE' if abs(pct) < 30 else 'CRITICAL'
        events.append((sev, f'concept count changed {pct:+.1f}%',
                       f"{old.get('rows_returned')} → {new.get('rows_returned')}"))

    # 7. New override applied
    if new.get('source_key_override') and not old.get('source_key_override'):
        events.append(('NOTABLE', 'sourceKey override newly applied',
                       f"override → {new.get('source_key')} ({new.get('override_reason','')})"))

    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', required=True, help='old meta dir (archive snapshot)')
    parser.add_argument('--new', required=True, help='new meta dir (current)')
    parser.add_argument('--out', default='', help='output diff CSV path (default: print only)')
    args = parser.parse_args()

    old_metas = load_metas(args.old)
    new_metas = load_metas(args.new)
    print(f"Old: {len(old_metas)} pairs from {args.old}")
    print(f"New: {len(new_metas)} pairs from {args.new}")

    all_keys = sorted(set(old_metas.keys()) | set(new_metas.keys()))
    rows = []
    summary = {'CRITICAL': 0, 'NOTABLE': 0, 'OK': 0, 'MISSING_OLD': 0, 'MISSING_NEW': 0}

    for key in all_keys:
        site, domain = key
        if key not in old_metas:
            summary['MISSING_OLD'] += 1
            rows.append({'site': site, 'domain': domain, 'severity': 'NEW',
                         'change': 'pair appeared in new only', 'detail': ''})
            continue
        if key not in new_metas:
            summary['MISSING_NEW'] += 1
            rows.append({'site': site, 'domain': domain, 'severity': 'REMOVED',
                         'change': 'pair missing in new', 'detail': ''})
            continue
        events = compare_one(old_metas[key], new_metas[key])
        if not events:
            summary['OK'] += 1
            continue
        for sev, change, detail in events:
            summary[sev] = summary.get(sev, 0) + 1
            rows.append({'site': site, 'domain': domain, 'severity': sev,
                         'change': change, 'detail': detail})

    # Stdout summary
    print(f"\nSummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Show critical/notable changes
    crit = [r for r in rows if r['severity'] in ('CRITICAL', 'NOTABLE', 'NEW', 'REMOVED')]
    if crit:
        print(f"\n=== Changes to review ({len(crit)}) ===")
        for r in crit[:50]:
            print(f"  [{r['severity']}] {r['site']}/{r['domain']:13s} {r['change']:40s} {r['detail']}")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        with open(args.out, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['site', 'domain', 'severity', 'change', 'detail'])
            w.writeheader()
            w.writerows(rows)
        print(f"\n→ {args.out}")


if __name__ == '__main__':
    main()
