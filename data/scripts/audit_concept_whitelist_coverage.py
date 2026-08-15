"""Audit a whitelist concept set's coverage across every site snapshot.

A cohort built on a fixed concept set with `includeDescendants=false` is a
whitelist: a site whose local source-code mapping lands outside it contributes
nobody, with no error. This answers that question centrally, from the snapshots
already in `data/concept_frequency/by_site/`, instead of asking 23 institutions
to audit their own mapping.

    python data/scripts/audit_concept_whitelist_coverage.py

Defaults to the fracture-treatment whitelist: the 85 concepts of concept set
`#100`, grouped by the seven body-site concept sets `300`-`306` recorded in the
audit table's `site_sets` column.

Writes two CSVs beside the audit table:

    {stem}_site_group_coverage.csv   one row per site x body site
    {stem}_site_summary.csv          one row per site, with any uncovered groups

**Read the group columns, not the concept count.** The count measures coding
granularity, not capture: KHNMC shows 57 of 85 and DSMC 32, because KHNMC codes
lumbar fracture across five concepts where DSMC uses one, and the whitelist
deliberately holds both the `Closed fracture of X` and plain `Fracture of X`
members of each pair. Grouped by body site both are covered. The finding that
requires action is `uncovered_groups` being non-empty.

It also audits every other whitelist concept set the deployed cohorts carry, so
an exclusion criterion that matches nothing at a site is surfaced rather than
silently excluding nobody.

Two limits carry into any figure quoted from here. The snapshots have a
small-cell floor - every site's minimum `numPersons` is 6 - so each count is a
lower bound. And a snapshot counts the whole database, not the study cohort, so
a covered group is not proof the cohort will populate; an uncovered one is
strong evidence it will not.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from atlas_auto.concept_coverage import (  # noqa: E402
    concept_set_coverage,
    coverage_by_group,
    load_group_map,
    parse_site_frequency,
    uncovered_groups,
    whitelist_concept_sets,
)

DEFAULT_COHORTS = (
    REPO / "studies" / "fracture_treatment" / "portable_assets" / "cohorts"
)

DOMAIN_FILE = {
    "Condition": "condition", "Drug": "drug", "Procedure": "procedure",
    "Measurement": "measurement", "Observation": "observation",
}

DEFAULT_AUDIT = (
    REPO / "studies" / "fracture_treatment" / "extracted_concepts"
    / "fracture_site_concept_recoding_audit.csv"
)
DEFAULT_SNAPSHOTS = REPO / "data" / "concept_frequency" / "by_site"

# The study's seven body-site concept sets, from the v1.9 refracture outcome.
SITE_SET_LABELS = {
    "300": "spine",
    "301": "pelvis/ramus",
    "302": "sacrum",
    "303": "hip/femur",
    "304": "proximal humerus",
    "305": "wrist/radius",
    "306": "ankle",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT,
                        help="table of whitelist concepts with a group column")
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS,
                        help="directory of {SITE}_{domain}.csv frequency files")
    parser.add_argument("--domain", default="condition",
                        help="which snapshot domain to read (default: condition)")
    parser.add_argument("--group-column", default="site_sets")
    parser.add_argument("--cohorts", type=Path, default=DEFAULT_COHORTS,
                        help="deployed cohort JSONs; every whitelist concept "
                             "set in them is audited too")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="defaults to the audit table's directory")
    args = parser.parse_args(argv)

    with args.audit.open(encoding="utf-8-sig", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    groups = load_group_map(
        audit_rows, group_column=args.group_column, labels=SITE_SET_LABELS,
    )
    if not groups:
        raise SystemExit(f"no group mapping found in {args.audit}")

    group_names = sorted(set(groups.values()))
    print(f"whitelist concepts : {len(groups)}")
    print(f"groups             : {', '.join(group_names)}")

    snapshots = sorted(args.snapshots.glob(f"*_{args.domain}.csv"))
    if not snapshots:
        raise SystemExit(f"no *_{args.domain}.csv under {args.snapshots}")

    coverage_rows = []
    summary_rows = []
    for path in snapshots:
        site = path.name[: -len(f"_{args.domain}.csv")]
        seen = parse_site_frequency(path)
        rows = coverage_by_group(site, seen, groups)
        coverage_rows.extend(rows)
        missing = uncovered_groups(rows)
        summary_rows.append({
            "site": site,
            "snapshot_concepts": len(seen),
            "whitelist_concepts_seen": sum(r.concepts_seen for r in rows),
            "whitelist_concepts_total": len(groups),
            "groups_covered": sum(1 for r in rows if r.covered),
            "groups_total": len(group_names),
            "uncovered_groups": ";".join(missing),
            "whitelist_persons": sum(r.persons for r in rows),
        })

    out_dir = args.out_dir or args.audit.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.audit.stem

    detail_path = out_dir / f"{stem}_site_group_coverage.csv"
    with open(detail_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["site", "group", "concepts_seen", "concepts_total", "persons", "covered"]
        )
        for row in coverage_rows:
            writer.writerow([
                row.site, row.group, row.concepts_seen, row.concepts_total,
                row.persons, int(row.covered),
            ])

    summary_path = out_dir / f"{stem}_site_summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    print()
    header = f"{'site':<8}{'concepts':>10}{'groups':>9}  uncovered"
    print(header)
    print("-" * len(header))
    flagged = 0
    for row in sorted(summary_rows, key=lambda r: (-len(r["uncovered_groups"]), r["site"])):
        if row["uncovered_groups"]:
            flagged += 1
        print(
            f"{row['site']:<8}"
            f"{row['whitelist_concepts_seen']:>4}/{row['whitelist_concepts_total']:<5}"
            f"{row['groups_covered']:>4}/{row['groups_total']:<4}  "
            f"{row['uncovered_groups'] or '-'}"
        )

    print()
    print(f"sites with an uncovered body site: {flagged} of {len(summary_rows)}")
    print(f"wrote {detail_path.relative_to(REPO)}")
    print(f"wrote {summary_path.relative_to(REPO)}")
    if flagged:
        print()
        print("An uncovered group means the study reports on a body site that is "
              "invisible at that institution. Confirm with a live Achilles "
              "drilldown before acting; the snapshot has a 6-person floor.")

    if args.cohorts and args.cohorts.is_dir():
        audit_every_whitelist_set(args)
    return 0


def audit_every_whitelist_set(args) -> None:
    """Every whitelist concept set in the deployed cohorts, at every site.

    The body-site check above answers one question. A cohort carries many more
    concept sets, and each one that is a whitelist can fail the same way. An
    exclusion criterion whose set matches nothing at a site does not raise; it
    silently excludes nobody, and the cohort then means a different thing there.

    Judging a zero needs the clinical prior. For a rare disease, matching nothing
    is expected and harmless ??excluding zero patients equals not excluding. For
    a common condition it means the criterion is inert, which is a real
    cross-site difference in what the cohort selects.
    """
    bodies = []
    for path in sorted(args.cohorts.glob("*.json")):
        bodies.append(json.loads(path.read_text(encoding="utf-8")))
    sets = whitelist_concept_sets(bodies)
    if not sets:
        return

    print()
    print("=" * 78)
    print(f"whitelist concept sets in {len(bodies)} deployed cohorts: {len(sets)}")
    print("(sets with includeDescendants=true are robust and are not listed)")
    print()

    snapshots: dict[tuple[str, str], dict[int, tuple[int, str]]] = {}
    sites = set()
    for path in args.snapshots.glob("*_*.csv"):
        site, domain = path.name[:-4].split("_", 1)
        if domain not in DOMAIN_FILE.values():
            continue
        snapshots[(site, domain)] = parse_site_frequency(path)
        sites.add(site)
    sites = sorted(sites)

    out_rows = []
    print(f"{'concept set':<52}{'n':>4}{'domain':>11}  sites matching nothing")
    print("-" * 108)
    for name, spec in sorted(sets.items(), key=lambda kv: -len(kv[1].concept_ids)):
        domain_file = DOMAIN_FILE.get(spec.domain or "")
        if domain_file is None:
            print(f"{name[:52]:<52}{len(spec.concept_ids):>4}"
                  f"{str(spec.domain):>11}  (no snapshot for this domain)")
            continue
        empty = []
        for site in sites:
            seen = snapshots.get((site, domain_file), {})
            row = concept_set_coverage(site, seen, {name: spec.concept_ids})[0]
            out_rows.append(row)
            if row.concepts_seen == 0:
                empty.append(site)
        print(f"{name[:52]:<52}{len(spec.concept_ids):>4}{spec.domain:>11}  "
              f"{(str(len(empty)) + ': ' + ','.join(empty)) if empty else '-'}")

    out_dir = args.out_dir or args.audit.parent
    path = out_dir / f"{args.audit.stem}_concept_set_coverage.csv"
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["site", "concept_set", "concepts_seen",
                         "concepts_total", "persons"])
        for row in out_rows:
            writer.writerow([row.site, row.group, row.concepts_seen,
                             row.concepts_total, row.persons])
    print()
    print(f"wrote {path.relative_to(REPO)}")
    print("A zero is only actionable once you know whether the condition is rare "
          "at that site. Excluding nobody for a disease nobody has is fine; "
          "excluding nobody for a common condition changes what the cohort means.")


if __name__ == "__main__":
    raise SystemExit(main())
