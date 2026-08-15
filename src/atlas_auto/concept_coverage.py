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
import json
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


@dataclass(frozen=True)
class WhitelistSet:
    """A concept set that admits only the concepts named in it."""

    name: str
    concept_ids: frozenset
    domain: str | None
    used_by_count: int


def _expression_of(body: Mapping[str, Any]) -> dict:
    expr = body.get("expression", body)
    if isinstance(expr, str):
        expr = json.loads(expr)
    return expr or {}


def whitelist_concept_sets(
    cohort_bodies: Iterable[Mapping[str, Any]],
) -> dict[str, WhitelistSet]:
    """The concept sets that are whitelists, keyed by name.

    `includeDescendants=true` on any item makes a set robust: a site coding a
    descendant still matches, and the local frequency snapshots cannot check it
    anyway because they do not carry the hierarchy. `includeDescendants=false`
    everywhere makes the set a whitelist, which is exactly the kind that fails
    silently when an institution's mapping lands on a sibling.

    Sets appearing in several cohorts are merged and counted once.
    """
    concepts: dict[str, set[int]] = {}
    domains: dict[str, set[str]] = {}
    descendants: dict[str, set[bool]] = {}
    uses: dict[str, int] = {}

    for body in cohort_bodies:
        for concept_set in _expression_of(body).get("ConceptSets", []) or []:
            name = concept_set.get("name")
            if not name:
                continue
            items = (concept_set.get("expression") or {}).get("items") or []
            found = set()
            for item in items:
                concept = item.get("concept") or {}
                concept_id = concept.get("CONCEPT_ID")
                if concept_id is None:
                    continue
                found.add(int(concept_id))
                descendants.setdefault(name, set()).add(
                    bool(item.get("includeDescendants"))
                )
                if concept.get("DOMAIN_ID"):
                    domains.setdefault(name, set()).add(concept["DOMAIN_ID"])
            if not found:
                continue
            concepts.setdefault(name, set()).update(found)
            uses[name] = uses.get(name, 0) + 1

    result: dict[str, WhitelistSet] = {}
    for name, ids in concepts.items():
        if descendants.get(name) != {False}:
            continue
        site_domains = sorted(domains.get(name, ()))
        result[name] = WhitelistSet(
            name=name,
            concept_ids=frozenset(ids),
            domain=site_domains[0] if len(site_domains) == 1 else None,
            used_by_count=uses[name],
        )
    return result


def concept_set_coverage(
    site: str,
    seen: Mapping[int, tuple[int, str]],
    sets: Mapping[str, Iterable[int]],
) -> list[CoverageRow]:
    """One row per concept set, however the sets overlap.

    `coverage_by_group` assumes a concept belongs to one group. Exclusion sets
    genuinely overlap — the same concept can sit in a site set and in an
    exclusion — so this counts each set independently.
    """
    if not sets:
        raise ValueError("no concept sets given; there is nothing to measure")

    rows = []
    for name in sorted(sets):
        ids = list(sets[name])
        found = [cid for cid in ids if cid in seen]
        rows.append(CoverageRow(
            site, name, len(found), len(ids),
            sum(seen[cid][0] for cid in found),
        ))
    return rows


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
