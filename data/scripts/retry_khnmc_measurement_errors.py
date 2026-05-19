"""
Retry the 5 KHNMC concepts that returned ERROR during the 2026-05-11 collection.

Targets:
  3000330 — Specific gravity of Urine by Test strip (~959K persons)
  3009542 — Hematocrit [Volume Fraction] of Blood (~1.18M persons)
  3015884 — DHEA-S (~19K persons)
  3016244 — Insulin (~19K persons)
  3028026 — IgM (~27K persons)

Strategy:
  - Up to 3 retries per concept with exponential backoff
  - Verbose error capture (HTTP status, exception type, response body if available)
  - On success: merge into existing raw JSON and replace ERROR rows in output CSV
  - On final failure: keep ERROR row but update error message with diagnostic detail

Usage:
  python retry_khnmc_measurement_errors.py
  python retry_khnmc_measurement_errors.py --bearer "eyJ..."
"""
import csv
import json
import os
import sys
import time
import argparse
import functools

print = functools.partial(print, flush=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'automation'))

from atlas_auto.client import FedernetClient
from credentials import get_feedernet_credentials

CONCEPT_FREQ_CSV = os.path.join(REPO_ROOT, 'data', 'concept_frequency', 'by_site', 'KHNMC_measurement.csv')
OUTPUT_PATH = os.path.join(REPO_ROOT, 'data', 'measurement', 'khnmc_full_value_survey.csv')
RAW_PATH = os.path.join(REPO_ROOT, 'data', 'measurement', 'raw_drilldown', 'khnmc_full_measurement.json')

SITE = {'code': 'KHNMC', 'group_id': 7, 'site_id': 203, 'sourceKey': 'cdmpv53_251128'}

TARGET_CIDS = ['3000330', '3009542', '3015884', '3016244', '3028026']

# Import extract_values + FIELDS from the main collector to keep behaviour identical
sys.path.insert(0, SCRIPT_DIR)
from collect_khnmc_measurement_dist import extract_values, FIELDS, save_csv  # noqa: E402


def load_concept_meta():
    """Map cid -> (name, numPersons) from source CSV."""
    out = {}
    with open(CONCEPT_FREQ_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            cid = r.get('conceptId', '').strip()
            if cid in TARGET_CIDS:
                path = r.get('conceptPath', '')
                name = path.split('||')[-1].strip().strip('"')
                try:
                    np_ = int(r.get('numPersons', 0))
                except ValueError:
                    np_ = 0
                out[cid] = (name, np_)
    return out


def call_with_retry(client, cid, name, max_retries=3):
    """Return (raw_or_none, diagnostic_msg)."""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            raw = client.get_achilles_drilldown(SITE['sourceKey'], 'measurement', int(cid))
            elapsed = time.time() - t0
            if raw is None:
                last_err = f"attempt {attempt}: returned None"
                print(f"    {cid} attempt {attempt}: None response ({elapsed:.1f}s)")
            elif isinstance(raw, dict) and not raw:
                last_err = f"attempt {attempt}: empty dict"
                print(f"    {cid} attempt {attempt}: empty dict ({elapsed:.1f}s)")
            else:
                print(f"    {cid} attempt {attempt}: OK ({elapsed:.1f}s, keys={len(raw)})")
                return raw, "OK"
        except Exception as e:
            last_err = f"attempt {attempt}: {type(e).__name__}: {str(e)[:150]}"
            print(f"    {cid} attempt {attempt}: {type(e).__name__}: {str(e)[:120]}")
        if attempt < max_retries:
            backoff = 2 ** attempt
            print(f"    backoff {backoff}s ...")
            time.sleep(backoff)
    return None, last_err


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bearer', help='Bearer token (otherwise uses credentials.py)')
    parser.add_argument('--max-retries', type=int, default=3)
    args = parser.parse_args()

    # 1. Load concept meta
    meta = load_concept_meta()
    print(f"Targets: {len(meta)} concepts")
    for cid, (name, np_) in meta.items():
        print(f"  {cid}: persons={np_:,}, name={name[:80]}")

    # 2. Load existing raw + output CSV
    with open(RAW_PATH, 'r', encoding='utf-8') as f:
        raw_results = json.load(f)
    print(f"\nExisting raw JSON: {len(raw_results)} concepts")

    with open(OUTPUT_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    err_rows_before = sum(1 for r in rows if r.get('unit_name') == 'ERROR')
    print(f"Existing output CSV: {len(rows)} rows, {err_rows_before} ERROR rows")

    # 3. Login
    client = FedernetClient()
    if args.bearer:
        if not client.login_with_bearer_token(args.bearer):
            print("Bearer login failed")
            return
    else:
        email, pw = get_feedernet_credentials()
        if not client.login_portal(email, pw):
            print("Portal login failed")
            return

    if not client.connect_site(group_id=SITE['group_id'], site_id=SITE['site_id']):
        print("connect_site failed")
        return
    print(f"\nConnected to {SITE['code']}")

    # 4. Retry each target
    successes = 0
    print(f"\n=== Retrying {len(TARGET_CIDS)} concepts (max {args.max_retries} attempts each) ===")
    for cid in TARGET_CIDS:
        if cid not in meta:
            print(f"  [skip] {cid} not in source CSV")
            continue
        name, np_ = meta[cid]
        print(f"\n  → {cid} ({name[:60]}) persons={np_:,}")
        raw, msg = call_with_retry(client, cid, name, max_retries=args.max_retries)

        # Remove old ERROR rows for this cid from output
        rows = [r for r in rows if r['concept_id'] != cid]

        if raw is not None:
            successes += 1
            raw_results[cid] = raw
            entries = extract_values(raw)
            if not entries:
                rows.append({
                    'site': SITE['code'], 'concept_id': cid, 'concept_name': name,
                    'numPersons_achilles': str(np_),
                    'unit_concept_id': '0', 'unit_name': 'NO_DATA',
                    'count': '0', 'min': '', 'p10': '', 'p25': '',
                    'median': '', 'p75': '', 'p90': '', 'max': '',
                })
                print(f"    saved: NO_DATA (raw had no measurementValueDistribution)")
            else:
                for e in entries:
                    row = {'site': SITE['code'], 'concept_id': cid, 'concept_name': name,
                           'numPersons_achilles': str(np_)}
                    row.update({k: ('' if v is None else str(v)) for k, v in e.items()})
                    rows.append(row)
                print(f"    saved: {len(entries)} unit row(s)")
        else:
            # Keep ERROR but with updated diagnostic
            rows.append({
                'site': SITE['code'], 'concept_id': cid, 'concept_name': name,
                'numPersons_achilles': str(np_),
                'unit_concept_id': '0', 'unit_name': 'ERROR',
                'count': '0', 'min': '', 'p10': '', 'p25': '',
                'median': '', 'p75': '', 'p90': '', 'max': msg[:80],
            })
            print(f"    FAILED after {args.max_retries} attempts: {msg}")

    # 5. Save updated raw JSON + output CSV
    save_csv(rows, OUTPUT_PATH)
    with open(RAW_PATH, 'w', encoding='utf-8') as f:
        json.dump(raw_results, f, ensure_ascii=False)
    size_mb = os.path.getsize(RAW_PATH) / 1024 / 1024

    err_rows_after = sum(1 for r in rows if r.get('unit_name') == 'ERROR')
    print(f"\n=== Summary ===")
    print(f"Recovered: {successes}/{len(TARGET_CIDS)}")
    print(f"ERROR rows: {err_rows_before} -> {err_rows_after}")
    print(f"Raw JSON now has {len(raw_results)} concepts ({size_mb:.1f} MB)")
    print(f"Output CSV: {len(rows)} rows")


if __name__ == '__main__':
    main()
