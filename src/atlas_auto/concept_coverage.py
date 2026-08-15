"""Check a whitelist concept set's coverage across site frequency snapshots.

A cohort built on a fixed concept set with `includeDescendants=false` is a
whitelist. A site whose local source-code mapping lands outside it contributes
nobody to the cohort, with no error and no warning — the site's N is simply
smaller, which then reads as a clinical difference. Checking that centrally,
against the `data/concept_frequency/by_site/*.csv` snapshots already in the
repository, is far cheaper than asking every institution to audit its own
mapping.

**Count concepts per group, never per site.** The obvious metric is how many
whitelist concepts a site shows, and it measures coding *granularity*, not
capture. Measured 2026-08-16 on the fracture-treatment whitelist of 85 concepts:
KHNMC shows 57 and DSMC 32, which looks like DSMC is losing patients. It is not.
KHNMC codes lumbar fracture across five concepts — the whole segment plus first
through fourth vertebra — where DSMC codes the same patients under one
`Fracture of lumbar spine`. The same pattern runs through the set: KHNMC uses the
`Closed fracture of X` member of each pair and DSMC the plain `Fracture of X`,
and the whitelist deliberately contains both. Grouped by the body site the study
actually asks about, both sites are covered everywhere.

So the actionable signal is not a count. It is a **group with no concept at all**,
which means a body site the study reports on is invisible at that institution.

Two limits worth stating whenever this is quoted:

- The snapshots carry a small-cell floor. Every site in the current set has a
  minimum `numPersons` of 6, so a concept used for fewer patients than that is
  absent everywhere and each count is a lower bound.
- A snapshot counts the whole database, not the study cohort. A covered group is
  not proof the cohort will populate; an uncovered group is strong evidence it
  will not.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

PATH_SEPARATOR = "||"


@dataclass(frozen=True)
class CoverageRow:
    """One site's coverage of one concept group."""

    site: str
    group: str
    concepts_seen: int
    concepts_total: int
    persons: int

    @property
    def covered(self) -> bool:
        return self.concepts_seen > 0


def concept_name_from_path(concept_path: str | None) -> str:
    """The concept name is the last segment of Achilles' `conceptPath`.

    The column is `conceptPath`, not anything containing "name", which is easy
    to miss and produces an analysis that silently sees no names at all.
    """
    if not concept_path:
        return ""
    return str(concept_path).split(PATH_SEPARATOR)[-1].strip()


def parse_site_frequency(path: Path | str) -> dict[int, tuple[int, str]]:
    """Read one `{SITE}_{domain}.csv` snapshot into concept id -> (persons, name).

    Rows whose id or person count will not parse are skipped rather than
    guessed at.
    """
    parsed: dict[int, tuple[int, str]] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                concept_id = int(row["conceptId"])
            except (KeyError, TypeError, ValueError):
                continue
            try:
                persons = int(float(row["numPersons"]))
            except (KeyError, TypeError, ValueError):
                persons = 0
            parsed[concept_id] = (persons, concept_name_from_path(row.get("conceptPath")))
    return parsed


def coverage_by_group(
    site: str,
    seen: Mapping[int, tuple[int, str]],
    groups: Mapping[int, str],
) -> list[CoverageRow]:
    """One row per group, whether or not the site shows anything for it.

    `groups` maps each whitelist concept id to the group it belongs to — for the
    fracture study, the body-site concept set the study reports on. Concepts
    outside `groups` are ignored: this measures the whitelist, not the database.
    """
    if not groups:
        raise ValueError("groups is empty; there is nothing to measure coverage against")

    totals: dict[str, int] = {}
    for label in groups.values():
        totals[label] = totals.get(label, 0) + 1

    found: dict[str, int] = {label: 0 for label in totals}
    persons: dict[str, int] = {label: 0 for label in totals}
    for concept_id, label in groups.items():
        entry = seen.get(concept_id)
        if entry is None:
            continue
        found[label] += 1
        persons[label] += entry[0]

    return [
        CoverageRow(site, label, found[label], totals[label], persons[label])
        for label in sorted(totals)
    ]


def uncovered_groups(rows: Iterable[CoverageRow]) -> list[str]:
    """The groups with no whitelist concept at all, sorted.

    This, not a low concept count, is the finding that requires action.
    """
    return sorted({row.group for row in rows if not row.covered})


def load_group_map(
    audit_rows: Iterable[Mapping[str, Any]],
    *,
    concept_column: str = "concept_id",
    group_column: str = "site_sets",
    labels: Mapping[str, str] | None = None,
) -> dict[int, str]:
    """Build the concept -> group map from an audit table.

    `labels` renames the raw group key, so a concept-set id such as `305` can be
    reported as `wrist/radius` without hard-coding the study's ids here.
    """
    mapping: dict[int, str] = {}
    for row in audit_rows:
        try:
            concept_id = int(row[concept_column])
        except (KeyError, TypeError, ValueError):
            continue
        raw = str(row.get(group_column, "")).strip()
        if not raw:
            continue
        mapping[concept_id] = labels.get(raw, raw) if labels else raw
    return mapping
