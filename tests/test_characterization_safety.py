"""Contract tests for the guarded characterization helpers.

Each test pins a WebAPI behaviour that produced a wrong or failed result during
the fracture-treatment study on 2026-08-13 and 2026-08-14.
"""

import copy
import json

import pytest

from atlas_auto.characterization_safety import (
    CharacterizationSafetyError,
    assert_design_present,
    assert_membership,
    cohort_entry,
    counts_by_analysis,
    design_of,
    preset_name,
    fetch_results,
    import_characterization_checked,
    import_characterization_mapped,
    feature_identity,
)


class FakeClient:
    def __init__(self, *, results=None, reported=None, features=None,
                 cohorts=None, export=None, imported_id=900):
        self.results = results or []
        self.reported = len(self.results) if reported is None else reported
        self.features = features or {}
        self.cohorts = cohorts or {}
        self.export_payloads = export or {}
        self.imported_id = imported_id
        self.imported_body = None

    def get_characterization_result_count(self, generation_id):
        return self.reported

    def get_characterization_results(self, generation_id, threshold_level=0.01):
        assert threshold_level == 0, "results must be fetched with threshold_level=0"
        return list(self.results)

    def get_feature_analysis(self, feature_id):
        return self.features[feature_id]

    def get_cohort_definition(self, cohort_id):
        return self.cohorts[cohort_id]

    def export_characterization(self, characterization_id):
        return self.export_payloads[characterization_id]

    def import_characterization(self, body):
        self.imported_body = body
        return {"id": self.imported_id}


def _row(analysis_id, cohort_id=1, count=5):
    return {"analysisId": analysis_id, "cohortId": cohort_id, "count": count}


def test_membership_ignores_order_but_catches_a_real_difference():
    assert_membership([3, 1, 2], [1, 2, 3], "features")
    with pytest.raises(CharacterizationSafetyError, match="missing=\\[4\\]"):
        assert_membership([1, 2, 3], [1, 2, 3, 4], "features")
    with pytest.raises(CharacterizationSafetyError, match="unexpected=\\[9\\]"):
        assert_membership([1, 2, 9], [1, 2], "features")


def test_a_trimmed_result_set_is_rejected():
    """thresholdLevel above 0 drops low-prevalence rows and totals stop matching."""
    client = FakeClient(results=[_row(1), _row(2)], reported=8)
    with pytest.raises(CharacterizationSafetyError, match="thresholdLevel"):
        fetch_results(client, 5001)


def test_results_are_always_requested_with_threshold_zero():
    client = FakeClient(results=[_row(1)])
    assert fetch_results(client, 5001) == [_row(1)]


def test_a_missing_analysis_row_is_an_error_not_a_zero():
    client = FakeClient(results=[_row(1), _row(2)])
    with pytest.raises(CharacterizationSafetyError, match="absence is not a zero count"):
        fetch_results(client, 5001, required_analysis_ids=[1, 2, 3])


def test_required_ids_are_checked_within_the_named_cohort():
    client = FakeClient(results=[_row(1, cohort_id=1), _row(2, cohort_id=7)])
    fetch_results(client, 5001, required_analysis_ids=[2], cohort_id=7)
    with pytest.raises(CharacterizationSafetyError, match="absence is not a zero count"):
        fetch_results(client, 5001, required_analysis_ids=[2], cohort_id=1)


def test_duplicate_result_rows_are_rejected():
    rows = [_row(1, count=5), _row(1, count=6)]
    with pytest.raises(CharacterizationSafetyError, match="duplicate result row"):
        counts_by_analysis(rows, cohort_id=1)


def test_counts_are_scoped_to_one_cohort():
    rows = [_row(1, cohort_id=1, count=5), _row(1, cohort_id=2, count=9)]
    assert counts_by_analysis(rows, cohort_id=2) == {1: 9}


@pytest.mark.parametrize("stored", [None, [], "", "[]"])
def test_an_unreported_design_reads_as_none_not_as_broken(stored):
    """An empty design read is 'unknown'. Features with empty reads still work."""
    assert design_of({"design": stored}) is None


def test_an_unparseable_design_reads_as_none_rather_than_raising():
    """Surveying many features must not abort on one malformed record."""
    assert design_of({"design": "not json"}) is None
    assert design_of({"design": "{"}) is None


def test_a_preset_design_is_a_preset_name_not_a_criteria_list():
    """PRESET features store the preset's name in `design`; ids 49/71/74/77/80."""
    feature = {"type": "PRESET", "design": "DemographicsGender"}
    assert preset_name(feature) == "DemographicsGender"
    assert design_of(feature) is None
    assert preset_name({"type": "CRITERIA_SET", "design": "DemographicsGender"}) is None
    assert preset_name({"type": "PRESET", "design": ""}) is None


def test_assert_design_present_accepts_a_preset():
    client = FakeClient(features={80: {"type": "PRESET", "design": "DemographicsIndexYear"}})
    assert assert_design_present(client, 80, "index year") == "DemographicsIndexYear"


def test_a_present_design_is_parsed_from_either_shape():
    parsed = [{"expression": {"Type": "ALL", "CriteriaList": []}}]
    assert design_of({"design": parsed}) == parsed
    assert design_of({"design": json.dumps(parsed)}) == parsed


def test_assert_design_present_flags_a_dropped_write():
    client = FakeClient(features={5: {"design": []}})
    with pytest.raises(CharacterizationSafetyError, match="the write was dropped"):
        assert_design_present(client, 5, "refill BP PO")


def test_cohort_entry_carries_description_and_expression():
    """The import DTO rejects a cohort entry holding only id and name."""
    template = {"id": 1, "name": "t", "description": "", "expression": {"a": 1}}
    client = FakeClient(cohorts={42: {"id": 42, "name": "target",
                                      "description": None,
                                      "expression": json.dumps({"b": 2})}})
    entry = cohort_entry(client, template, 42)
    assert set(entry) == {"id", "name", "description", "expression"}
    assert entry["id"] == 42 and entry["name"] == "target"
    assert entry["description"] == ""
    assert entry["expression"] == {"b": 2}


def _export(name="template"):
    return {
        "id": 215,
        "name": name,
        "skeletonType": "COHORT_CHARACTERIZATION",
        "skeletonVersion": "v0",
        "parameters": [],
        "stratas": [],
        "strataOnly": False,
        "strataConceptSets": [],
        "cohorts": [{"id": 1, "name": "c", "description": "", "expression": {"a": 1}}],
        "featureAnalyses": [],
    }


def _inline(name="f1"):
    return {
        "name": name,
        "type": "CRITERIA_SET",
        "domain": "DRUG",
        "statType": "PREVALENCE",
        "descr": "",
        "description": "",
        "conceptSets": [{"id": 0, "name": "cs", "expression": {"items": []}}],
        "design": [{"criteriaType": "CriteriaGroup", "id": 1, "name": "",
                    "aggregate": {}, "expression": {"Type": "ALL", "CriteriaList": []}}],
    }


def test_import_rejects_a_feature_passed_by_id():
    client = FakeClient(export={215: _export()}, cohorts={42: {"id": 42, "name": "t",
                                                              "description": "",
                                                              "expression": {"a": 1}}})
    with pytest.raises(CharacterizationSafetyError, match="must not carry an id"):
        import_characterization_checked(
            client, template_characterization_id=215, name="new",
            cohort_ids=[42], inline_features=[{**_inline(), "id": 851}])


def test_import_rejects_a_feature_with_no_design():
    client = FakeClient(export={215: _export()}, cohorts={42: {"id": 42, "name": "t",
                                                              "description": "",
                                                              "expression": {"a": 1}}})
    broken = {**_inline(), "design": []}
    with pytest.raises(CharacterizationSafetyError, match="no design to import"):
        import_characterization_checked(
            client, template_characterization_id=215, name="new",
            cohort_ids=[42], inline_features=[broken])


def test_import_verifies_the_stored_result():
    inline = _inline("refill BP PO")
    stored = {
        **_export("new"),
        "id": 900,
        "cohorts": [{"id": 42, "name": "t", "description": "", "expression": {"a": 1}}],
        "featureAnalyses": [{"id": 867, "name": "refill BP PO"}],
    }
    client = FakeClient(
        export={215: _export(), 900: stored},
        cohorts={42: {"id": 42, "name": "t", "description": "", "expression": {"a": 1}}},
        features={867: {"design": inline["design"]}},
    )
    created = import_characterization_checked(
        client, template_characterization_id=215, name="new",
        cohort_ids=[42], inline_features=[inline])
    assert created == 900
    assert client.imported_body["name"] == "new"
    assert "id" not in client.imported_body
    assert client.imported_body["cohorts"][0]["id"] == 42
    assert client.imported_body["skeletonVersion"] == "v0"


def test_import_fails_when_the_stored_feature_lost_its_design():
    inline = _inline("refill BP PO")
    stored = {
        **_export("new"),
        "id": 900,
        "cohorts": [{"id": 42, "name": "t", "description": "", "expression": {"a": 1}}],
        "featureAnalyses": [{"id": 867, "name": "refill BP PO"}],
    }
    client = FakeClient(
        export={215: _export(), 900: stored},
        cohorts={42: {"id": 42, "name": "t", "description": "", "expression": {"a": 1}}},
        features={867: {"design": []}},
    )
    with pytest.raises(CharacterizationSafetyError, match="the write was dropped"):
        import_characterization_checked(
            client, template_characterization_id=215, name="new",
            cohort_ids=[42], inline_features=[inline])


def test_import_accepts_a_server_substituted_feature_with_the_same_design():
    """The server reuses an existing feature whose design matches, ignoring the
    submitted name. Observed on 2026-08-15: the derived zoledronic feature came
    back as `#881`, whose design differed only in a surrogate CriteriaGroup id."""
    inline = _inline("v1.18v derived zoledronic")
    substituted = copy.deepcopy(inline["design"])
    substituted[0]["id"] = 593  # server-assigned surrogate, not part of the meaning
    stored = {
        **_export("new"),
        "id": 900,
        "cohorts": [{"id": 42, "name": "t", "description": "", "expression": {"a": 1}}],
        "featureAnalyses": [{"id": 881, "name": "v1.17 zoledronic second dose starters"}],
    }
    client = FakeClient(
        export={215: _export(), 900: stored},
        cohorts={42: {"id": 42, "name": "t", "description": "", "expression": {"a": 1}}},
        # a real `get_feature_analysis` returns the concept sets too, and identity
        # needs them: every ingredient feature shares one design
        features={881: {"design": substituted, "conceptSets": inline["conceptSets"]}},
    )
    characterization_id, mapping = import_characterization_mapped(
        client, template_characterization_id=215, name="new",
        cohort_ids=[42], inline_features=[inline])
    assert characterization_id == 900
    assert mapping["v1.18v derived zoledronic"] == 881


def test_import_still_fails_when_no_feature_matches_by_name_or_design():
    inline = _inline("wanted")
    unrelated = [{"criteriaType": "CriteriaGroup", "id": 1, "name": "", "aggregate": {},
                  "expression": {"Type": "ANY", "CriteriaList": []}}]
    stored = {
        **_export("new"),
        "id": 900,
        "cohorts": [{"id": 42, "name": "t", "description": "", "expression": {"a": 1}}],
        "featureAnalyses": [{"id": 881, "name": "something else"}],
    }
    client = FakeClient(
        export={215: _export(), 900: stored},
        cohorts={42: {"id": 42, "name": "t", "description": "", "expression": {"a": 1}}},
        features={881: {"design": unrelated}},
    )
    with pytest.raises(CharacterizationSafetyError, match="no stored feature matches"):
        import_characterization_mapped(
            client, template_characterization_id=215, name="new",
            cohort_ids=[42], inline_features=[inline])


def test_an_unreadable_stored_design_is_not_a_match_for_everything():
    """design_key(None) is the empty design; treating it as equal made five
    unrelated features match one submission on 2026-08-15."""
    inline = _inline("wanted")
    stored = {
        **_export("new"),
        "id": 900,
        "cohorts": [{"id": 42, "name": "t", "description": "", "expression": {"a": 1}}],
        "featureAnalyses": [{"id": 881, "name": "a"}, {"id": 882, "name": "b"}],
    }
    client = FakeClient(
        export={215: _export(), 900: stored},
        cohorts={42: {"id": 42, "name": "t", "description": "", "expression": {"a": 1}}},
        features={881: {"design": []}, 882: {"design": []}},
    )
    with pytest.raises(CharacterizationSafetyError, match="no stored feature matches"):
        import_characterization_mapped(
            client, template_characterization_id=215, name="new",
            cohort_ids=[42], inline_features=[inline])


def _ingredient_feature(name, concept_ids):
    """Two ingredient features: same design, different concept set."""
    return {**_inline(name),
            "conceptSets": [{"id": 0, "name": "ingredient",
                             "expression": {"items": [{"concept": {"CONCEPT_ID": c}}
                                                      for c in concept_ids]}}]}


def test_identity_separates_features_that_share_a_design():
    a = _ingredient_feature("zoledronic", [1524342])
    b = _ingredient_feature("denosumab", [1307046])
    assert design_of(a) == design_of(b)
    assert feature_identity(a) != feature_identity(b)


def test_identity_ignores_concept_order_and_unreadable_designs():
    a = _ingredient_feature("x", [3, 1, 2])
    b = _ingredient_feature("y", [1, 2, 3])
    assert feature_identity(a) == feature_identity(b)
    assert feature_identity({"design": [], "conceptSets": []}) is None


def test_import_matches_a_substitution_by_concept_set_not_design_alone():
    submitted = _ingredient_feature("v1.18v derived zoledronic", [1524342])
    same = copy.deepcopy(submitted["design"])
    same[0]["id"] = 593
    other = _ingredient_feature("other", [1307046])
    stored = {
        **_export("new"),
        "id": 900,
        "cohorts": [{"id": 42, "name": "t", "description": "", "expression": {"a": 1}}],
        "featureAnalyses": [{"id": 880, "name": "denosumab-ish"},
                            {"id": 881, "name": "v1.17 zoledronic starters"}],
    }
    client = FakeClient(
        export={215: _export(), 900: stored},
        cohorts={42: {"id": 42, "name": "t", "description": "", "expression": {"a": 1}}},
        features={880: {"design": other["design"], "conceptSets": other["conceptSets"]},
                  881: {"design": same, "conceptSets": submitted["conceptSets"]}},
    )
    _, mapping = import_characterization_mapped(
        client, template_characterization_id=215, name="new",
        cohort_ids=[42], inline_features=[submitted])
    assert mapping["v1.18v derived zoledronic"] == 881
