"""
Build a one-time vocabulary cache for every measurement concept that appears
in any site's refreshed concept_frequency CSV. For each concept, look up
VOCABULARY_ID via /vocabulary/concept/{id} and write a JSON cache.

Used to filter LOINC-only concepts in subsequent drilldown collection (avoids
the slow SNOMED hierarchy parent drilldown queries that take ~18s each).

Output:
  data/concept_frequency/vocabulary_cache_2026-05-12.json
    {concept_id: VOCABULARY_ID, ...}

Usage:
  python build_loinc_concept_cache.py
"""
import csv
import os
import sys
import json
import glob
import time
import datetime as dt
import functools

print = functools.partial(print, flush=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'src'))
sys.path.insert(0, os.path.join(REPO_ROOT, 'automation'))

from atlas_auto.client import FedernetClient  # noqa: E402
from credentials import get_feedernet_credentials  # noqa: E402

FREQ_DIR = os.path.join(REPO_ROOT, 'data', 'concept_frequency', 'by_site')
CACHE_PATH = os.path.join(REPO_ROOT, 'data', 'concept_frequency',
                          f'vocabulary_cache_{dt.date.today().isoformat()}.json')
SITE_MAP_CSV = os.path.join(REPO_ROOT, 'data', 'site_mapping', 'source_key_mapping.csv')


def collect_unique_concepts():
    """Gather every concept_id present in any *_measurement.csv across all sites."""
    seen = set()
    for csv_path in glob.glob(os.path.join(FREQ_DIR, '*_measurement.csv')):
        with open(csv_path, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                cid = (r.get('conceptId') or '').strip()
                if cid:
                    try:
                        seen.add(int(cid))
                    except ValueError:
                        pass
    return sorted(seen)


def main():
    print("=== Build vocabulary cache for measurement concepts ===\n")

    concepts = collect_unique_concepts()
    print(f"Unique measurement concept_ids across 23 sites: {len(concepts):,}")

    # Load existing cache if present (resume support)
    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding='utf-8') as f:
            cache = json.load(f)
        print(f"Existing cache loaded: {len(cache):,} entries")

    todo = [c for c in concepts if str(c) not in cache]
    print(f"To lookup: {len(todo):,}\n")

    if not todo:
        print("All concepts already cached.")
        return

    client = FedernetClient()
    client.login_portal(*get_feedernet_credentials())

    # Use first site (KHNMC) for vocabulary lookups (vocabulary is global, so any site works)
    with open(SITE_MAP_CSV, encoding='utf-8') as f:
        site_map = {r['﻿code']: r for r in csv.DictReader(f)}
    khnmc = site_map['KHNMC']
    client.connect_site(group_id=int(khnmc['group_id']), site_id=int(khnmc['site_id']))

    t0 = time.time()
    base = client.webapi_url
    for i, cid in enumerate(todo, 1):
        try:
            r = client.session.get(f"{base}/vocabulary/concept/{cid}", timeout=15)
            if r.ok:
                voc = r.json().get('VOCABULARY_ID', '?')
            else:
                voc = f'HTTP{r.status_code}'
        except Exception as e:
            voc = f'EXC:{type(e).__name__}'
        cache[str(cid)] = voc

        if i % 200 == 0 or i == len(todo):
            elapsed = time.time() - t0
            rate = i / max(elapsed, 1e-9)
            eta = (len(todo) - i) / max(rate, 1e-9) / 60
            print(f"  [{i:>5}/{len(todo)}] {elapsed:>5.0f}s elapsed, ~{eta:.1f}min ETA")
            # Incremental save every 200
            with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

    # Final save
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"\n→ {os.path.relpath(CACHE_PATH, REPO_ROOT)} ({len(cache):,} entries)")

    # Summary by vocabulary
    from collections import Counter
    voc_counts = Counter(cache.values())
    print("\nVocabulary breakdown:")
    for voc, n in voc_counts.most_common(20):
        print(f"  {voc:<20s} {n:>6}")
    print(f"\nLOINC concepts (will be included in drilldown): {voc_counts.get('LOINC', 0):,}")
    print(f"Total to exclude: {len(cache) - voc_counts.get('LOINC', 0):,}")


if __name__ == '__main__':
    main()
