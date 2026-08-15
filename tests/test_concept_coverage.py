"""Contract tests for whitelist coverage across site concept-frequency snapshots.

A study cohort built on a fixed concept set with `includeDescendants=false` is a
whitelist: a site whose local coding maps outside it contributes nobody, with no
error. Checking that centrally, from the snapshots already in the repo, is
cheaper than asking every site.

The trap this module exists to close is the obvious metric. Counting how many
whitelist concepts a site shows measures **coding granularity, not capture**.
KHNMC codes lumbar fracture across five concepts (whole segment plus first
through fourth vertebra); DSMC codes the same patients under one. Raw counts read
57 versus 32 and invite the conclusion that DSMC is missing patients, which is
wrong. Group by the body site the study actually asks about, and both are
covered.
"""

import pytest

from atlas_auto.concept_coverage import (
    CoverageRow,
    concept_name_from_path,
    concept_set_coverage,
    coverage_by_group,
    parse_site_frequency,
    uncovered_groups,
    whitelist_concept_sets,
)

# Three concepts for one body site, two for another.
GROUPS = {
    101: "spine", 102: "spine", 103: "spine",
    201: "wrist", 202: "wrist",
}


# ── snapshot parsing ──────────────────────────────────────────────────────


def test_the_concept_name_is_the_last_segment_of_concept_path():
    path = "NA||NA||NA||NA||Closed fracture of distal end of radius"

    assert concept_name_from_path(path) == "Closed fracture of distal end of radius"


def test_a_path_without_separators_is_the_name_itself():
    assert concept_name_from_path("Fracture of lumbar spine") == "Fracture of lumbar spine"


def test_an_empty_path_gives_an_empty_name():
    assert concept_name_from_path("") == ""
    assert concept_name_from_path(None) == ""


def test_parse_site_frequency_reads_id_persons_and_name(tmp_path):
    csv_path = tmp_path / "SITE_condition.csv"
    csv_path.write_text(
        "conceptId,conceptPath,numPersons,percentPersons,recordsPerPerson\n"
        "101,NA||NA||Closed fracture lumbar vertebra,3389,0.05,2.1\n"
        "201,NA||Fracture of distal end of radius,895,0.01,1.4\n",
        encoding="utf-8",
    )

    parsed = parse_site_frequency(csv_path)

    assert parsed[101] == (3389, "Closed fracture lumbar vertebra")
    assert parsed[201] == (895, "Fracture of distal end of radius")


def test_parse_site_frequency_skips_unparseable_rows(tmp_path):
    csv_path = tmp_path / "SITE_condition.csv"
    csv_path.write_text(
        "conceptId,conceptPath,numPersons,percentPersons,recordsPerPerson\n"
        "not-an-id,NA||junk,10,0.0,1.0\n"
        "101,NA||ok,5,0.0,1.0\n",
        encoding="utf-8",
    )

    assert set(parse_site_frequency(csv_path)) == {101}


# ── coverage ──────────────────────────────────────────────────────────────


def test_coverage_counts_concepts_and_sums_persons_per_group():
    seen = {101: (3389, "a"), 102: (2369, "b"), 201: (895, "c")}

    rows = {row.group: row for row in coverage_by_group("KHNMC", seen, GROUPS)}

    assert rows["spine"] == CoverageRow("KHNMC", "spine", 2, 3, 5758)
    assert rows["wrist"] == CoverageRow("KHNMC", "wrist", 1, 2, 895)


def test_every_group_gets_a_row_even_with_nothing_seen():
    rows = {row.group: row for row in coverage_by_group("EMPTY", {}, GROUPS)}

    assert set(rows) == {"spine", "wrist"}
    assert rows["spine"].concepts_seen == 0
    assert rows["spine"].persons == 0


def test_concepts_outside_every_group_are_ignored():
    seen = {101: (10, "a"), 999: (1_000_000, "not in the whitelist")}

    rows = {row.group: row for row in coverage_by_group("S", seen, GROUPS)}

    assert rows["spine"].persons == 10
    assert sum(row.persons for row in rows.values()) == 10


def test_coarse_and_granular_coding_both_read_as_covered():
    """The whole point: one concept for 3,000 people is not worse coverage."""
    granular = {101: (1000, "a"), 102: (1000, "b"), 103: (1000, "c")}
    coarse = {101: (3000, "one concept, same patients")}

    g = {r.group: r for r in coverage_by_group("G", granular, GROUPS)}["spine"]
    c = {r.group: r for r in coverage_by_group("C", coarse, GROUPS)}["spine"]

    assert g.concepts_seen == 3 and c.concepts_seen == 1
    assert g.persons == c.persons == 3000
    # One third the concepts, same patients, and still covered.
    assert c.covered is True
    assert "spine" not in uncovered_groups(coverage_by_group("C", coarse, GROUPS))


# ── the actionable signal ─────────────────────────────────────────────────


def test_a_group_with_no_concept_at_all_is_reported():
    """This is the real finding: a body site the study asks about is invisible."""
    seen = {101: (500, "spine only")}

    missing = uncovered_groups(coverage_by_group("S", seen, GROUPS))

    assert missing == ["wrist"]


def test_nothing_is_reported_when_every_group_has_a_concept():
    seen = {101: (500, "a"), 201: (5, "b")}

    assert uncovered_groups(coverage_by_group("S", seen, GROUPS)) == []


def test_uncovered_groups_are_returned_in_a_stable_order():
    rows = coverage_by_group("S", {}, GROUPS)

    assert uncovered_groups(rows) == ["spine", "wrist"]


def test_a_group_map_that_is_empty_is_refused():
    with pytest.raises(ValueError):
        list(coverage_by_group("S", {101: (1, "a")}, {}))


# ── which concept sets are whitelists at all ──────────────────────────────
#
# includeDescendants=true is robust: any descendant of the named concept counts,
# so a site's choice among siblings does not matter and the snapshots cannot
# check it anyway. includeDescendants=false is a whitelist and is exactly what
# needs checking. Separating the two is the first step of any such audit.


def _cohort(*concept_sets):
    return {"expression": {"ConceptSets": list(concept_sets)}}


def _cs(name, items):
    return {
        "name": name,
        "expression": {"items": [
            {"concept": {"CONCEPT_ID": cid, "DOMAIN_ID": domain},
             "includeDescendants": desc}
            for cid, domain, desc in items
        ]},
    }


def test_a_set_with_no_descendants_anywhere_is_a_whitelist():
    body = _cohort(_cs("exact", [(1, "Condition", False), (2, "Condition", False)]))

    found = whitelist_concept_sets([body])

    assert set(found) == {"exact"}
    assert found["exact"].concept_ids == {1, 2}
    assert found["exact"].domain == "Condition"


def test_a_set_with_any_descendant_item_is_not_a_whitelist():
    body = _cohort(_cs("robust", [(1, "Drug", True), (2, "Drug", False)]))

    assert whitelist_concept_sets([body]) == {}


def test_an_expression_delivered_as_a_json_string_is_parsed():
    import json
    body = {"expression": json.dumps(
        _cohort(_cs("exact", [(1, "Condition", False)]))["expression"])}

    assert set(whitelist_concept_sets([body])) == {"exact"}


def test_sets_with_the_same_name_across_cohorts_are_merged_once():
    a = _cohort(_cs("shared", [(1, "Condition", False)]))
    b = _cohort(_cs("shared", [(1, "Condition", False)]))

    found = whitelist_concept_sets([a, b])

    assert found["shared"].used_by_count == 2


def test_a_set_with_no_concepts_is_skipped():
    body = _cohort({"name": "empty", "expression": {"items": []}})

    assert whitelist_concept_sets([body]) == {}


# ── per-set coverage ──────────────────────────────────────────────────────


def test_concept_set_coverage_reports_one_row_per_set():
    sets = {"fracture": {101, 102}, "paget": {901}}
    seen = {101: (500, "a"), 102: (300, "b")}

    rows = {r.group: r for r in concept_set_coverage("SITE", seen, sets)}

    assert rows["fracture"] == CoverageRow("SITE", "fracture", 2, 2, 800)
    assert rows["paget"] == CoverageRow("SITE", "paget", 0, 1, 0)


def test_a_concept_in_two_sets_counts_in_both():
    """Group maps cannot express this; exclusion sets genuinely overlap."""
    sets = {"a": {101}, "b": {101}}

    rows = {r.group: r for r in concept_set_coverage("S", {101: (7, "x")}, sets)}

    assert rows["a"].persons == rows["b"].persons == 7


def test_an_empty_set_collection_is_refused():
    with pytest.raises(ValueError):
        concept_set_coverage("S", {101: (1, "a")}, {})
