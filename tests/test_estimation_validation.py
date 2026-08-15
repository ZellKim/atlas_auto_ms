"""Global fail-closed negative-control contracts for Estimation."""

from __future__ import annotations

import copy
import json

import pytest

from atlas_auto import (
    EstimationBuilder,
    EstimationValidationError,
    EstimationValidationResult,
    ValidatedEstimationExport,
    validate_estimation_design,
    validate_estimation_export,
)
from atlas_auto.client import FedernetClient


def _concept_set(concept_set_id: int = 7001, *, with_items: bool = True) -> dict:
    items = []
    if with_items:
        items.append(
            {
                "concept": {"CONCEPT_ID": 123456, "CONCEPT_NAME": "NC outcome"},
                "isExcluded": False,
                "includeDescendants": True,
                "includeMapped": False,
            }
        )
    return {
        "id": concept_set_id,
        "name": "Negative control outcomes",
        "expression": {"items": items},
    }


def _valid_design(*, tco_count: int = 1, with_items: bool = True) -> dict:
    tcos = [
        {
            "targetId": 100 + index,
            "comparatorId": 200 + index,
            "outcomeIds": [300 + index],
        }
        for index in range(tco_count)
    ]
    return {
        "id": 91,
        "name": "NC-required Estimation",
        "conceptSets": [_concept_set(with_items=with_items)],
        "conceptSetCrossReference": [
            {
                "conceptSetId": 7001,
                "targetName": "negativeControlOutcomes",
                "targetIndex": index,
                "propertyName": "outcomeId",
            }
            for index in range(tco_count)
        ],
        "negativeControls": [],
        "negativeControlOutcomeCohortDefinition": {
            "occurrenceType": "first",
            "detectOnDescendants": True,
            "domains": ["condition", "procedure"],
        },
        "estimationAnalysisSettings": {
            "analysisSpecification": {
                "targetComparatorOutcomes": tcos,
                "cohortMethodAnalysisList": [],
            }
        },
    }


def _valid_export(*, tco_count: int = 1, with_items: bool = False) -> dict:
    exported = _valid_design(tco_count=tco_count, with_items=with_items)
    exported["negativeControls"] = [
        {
            "targetId": 100 + index,
            "comparatorId": 200 + index,
            "outcomeId": 9000 + index,
            "outcomeName": f"NC {index}",
            "type": "Outcome",
        }
        for index in range(tco_count)
    ]
    return exported


def _issue_codes(error: EstimationValidationError) -> set[str]:
    return {issue.code for issue in error.issues}


def test_design_validation_returns_structured_proof():
    result = validate_estimation_design(_valid_design(tco_count=2))

    assert isinstance(result, EstimationValidationResult)
    assert result.stage == "design"
    assert result.estimation_id == 91
    assert result.estimation_name == "NC-required Estimation"
    assert result.referenced_concept_set_ids == (7001,)
    assert result.effective_nc_count == 0
    assert result.tco_pairs == ((100, 200), (101, 201))
    assert result.tco_nc_counts == (0, 0)


@pytest.mark.parametrize(
    ("corruption", "expected_code"),
    [
        ("missing_definition", "missing_nc_outcome_definition"),
        ("missing_xref", "missing_nc_cross_reference"),
        ("empty_placeholder", "empty_nc_concept_set"),
        ("empty_item_placeholder", "empty_nc_concept_set"),
        ("missing_negative_controls", "invalid_negative_controls"),
        ("invalid_negative_controls_type", "invalid_negative_controls"),
        ("dangling_concept_set", "unknown_nc_concept_set"),
        ("out_of_range_target", "invalid_nc_target_index"),
        ("wrong_property", "invalid_nc_property"),
        ("duplicate_xref", "duplicate_nc_cross_reference"),
        ("missing_concept_set_id", "missing_nc_concept_set_id"),
    ],
)
def test_design_validation_rejects_nc_contract_violations(
    corruption: str,
    expected_code: str,
):
    spec = _valid_design()
    if corruption == "missing_definition":
        spec.pop("negativeControlOutcomeCohortDefinition")
    elif corruption == "missing_xref":
        spec["conceptSetCrossReference"] = []
    elif corruption == "empty_placeholder":
        spec["conceptSets"][0]["expression"]["items"] = []
    elif corruption == "empty_item_placeholder":
        spec["conceptSets"][0]["expression"]["items"] = [{}]
    elif corruption == "missing_negative_controls":
        spec.pop("negativeControls")
    elif corruption == "invalid_negative_controls_type":
        spec["negativeControls"] = ()
    elif corruption == "dangling_concept_set":
        spec["conceptSetCrossReference"][0]["conceptSetId"] = 9999
    elif corruption == "out_of_range_target":
        spec["conceptSetCrossReference"][0]["targetIndex"] = 1
    elif corruption == "wrong_property":
        spec["conceptSetCrossReference"][0]["propertyName"] = "conceptId"
    elif corruption == "duplicate_xref":
        spec["conceptSetCrossReference"].append(
            copy.deepcopy(spec["conceptSetCrossReference"][0])
        )
    elif corruption == "missing_concept_set_id":
        spec["conceptSetCrossReference"][0].pop("conceptSetId")

    with pytest.raises(EstimationValidationError) as exc_info:
        validate_estimation_design(spec)

    error = exc_info.value
    assert error.stage == "design"
    assert expected_code in _issue_codes(error)
    assert "stage=design" in str(error)
    assert "effective_nc_count=" in str(error)
    assert "Action:" in str(error)


def test_design_accepts_resolved_rows_when_concept_items_are_elided():
    spec = _valid_export(with_items=False)

    result = validate_estimation_design(spec)

    assert result.effective_nc_count == 1


def test_design_does_not_treat_an_invalid_resolved_row_as_effective_nc():
    spec = _valid_export(with_items=False)
    spec["negativeControls"][0]["outcomeId"] = 0

    with pytest.raises(EstimationValidationError) as exc_info:
        validate_estimation_design(spec)

    assert "empty_nc_concept_set" in _issue_codes(exc_info.value)


@pytest.mark.parametrize(
    ("corruption", "expected_code"),
    [
        ("empty_effective_nc", "missing_effective_negative_controls"),
        ("missing_tco_xref", "missing_tco_nc_cross_reference"),
        ("wrong_pair", "invalid_nc_tco_pair"),
        ("invalid_outcome", "invalid_nc_outcome_id"),
        ("duplicate_triple", "duplicate_negative_control"),
        ("missing_tco_nc", "missing_tco_effective_negative_control"),
    ],
)
def test_export_validation_rejects_invalid_effective_negative_controls(
    corruption: str,
    expected_code: str,
):
    spec = _valid_export(tco_count=2)
    if corruption == "empty_effective_nc":
        spec["negativeControls"] = []
    elif corruption == "missing_tco_xref":
        spec["conceptSetCrossReference"] = spec["conceptSetCrossReference"][:1]
    elif corruption == "wrong_pair":
        spec["negativeControls"][0]["targetId"] = 999
    elif corruption == "invalid_outcome":
        spec["negativeControls"][0]["outcomeId"] = 0
    elif corruption == "duplicate_triple":
        spec["negativeControls"].append(copy.deepcopy(spec["negativeControls"][0]))
    elif corruption == "missing_tco_nc":
        spec["negativeControls"] = spec["negativeControls"][:1]

    with pytest.raises(EstimationValidationError) as exc_info:
        validate_estimation_export(spec)

    assert exc_info.value.stage == "export"
    assert expected_code in _issue_codes(exc_info.value)


def test_export_validation_accepts_resolved_rows_with_elided_concept_items():
    result = validate_estimation_export(_valid_export(tco_count=2, with_items=False))

    assert result.stage == "export"
    assert result.effective_nc_count == 2
    assert result.tco_nc_counts == (1, 1)
    assert result.referenced_concept_set_ids == (7001,)


def test_fracture_v19_empty_524_placeholder_shape_is_rejected():
    spec = _valid_design(with_items=False)
    spec["id"] = 291
    spec["name"] = "Fracture v1.9 P1"
    spec["conceptSets"][0]["id"] = 524
    spec["conceptSetCrossReference"][0]["conceptSetId"] = 524

    with pytest.raises(EstimationValidationError) as exc_info:
        validate_estimation_design(spec)

    error = exc_info.value
    assert "empty_nc_concept_set" in _issue_codes(error)
    assert error.referenced_concept_set_ids == (524,)
    assert error.effective_nc_count == 0


def test_builder_build_and_save_fail_closed_before_return_or_write(tmp_path):
    builder = EstimationBuilder("Invalid builder")
    builder.add_target_comparator_outcomes(100, 200, [300])
    output = tmp_path / "invalid.json"

    with pytest.raises(EstimationValidationError):
        builder.build()
    with pytest.raises(EstimationValidationError):
        builder.save(output)

    assert not output.exists()


def test_builder_build_and_save_validate_a_complete_design(tmp_path):
    builder = EstimationBuilder("Valid builder")
    builder.spec = _valid_design()
    output = tmp_path / "valid.json"

    built = builder.build()
    builder.save(output)

    assert built == _valid_design()
    assert built is not builder.spec
    assert json.loads(output.read_text(encoding="utf-8")) == _valid_design()


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return copy.deepcopy(self.payload)


class _RecordingSession:
    def __init__(self, response_payload: dict | None = None):
        self.calls: list[tuple[str, str, dict]] = []
        self.response_payload = response_payload or {"id": 777}

    def post(self, url: str, **kwargs) -> _Response:
        self.calls.append(("POST", url, kwargs))
        return _Response(self.response_payload)

    def put(self, url: str, **kwargs) -> _Response:
        self.calls.append(("PUT", url, kwargs))
        return _Response(self.response_payload)

    def get(self, url: str, **kwargs) -> _Response:
        self.calls.append(("GET", url, kwargs))
        return _Response(self.response_payload)


def _client(session: _RecordingSession) -> FedernetClient:
    client = FedernetClient("https://example.test")
    client.webapi_url = "https://example.test/api/v1/atlas/7/203"
    client.session = session
    return client


@pytest.mark.parametrize("method_name", ["create_estimation", "update_estimation"])
def test_design_mutations_reject_before_any_http(method_name: str):
    session = _RecordingSession()
    client = _client(session)
    invalid = _valid_design(with_items=False)

    with pytest.raises(EstimationValidationError):
        if method_name == "update_estimation":
            client.update_estimation(91, invalid)
        else:
            client.create_estimation(invalid)

    assert session.calls == []


def test_import_rejects_before_any_http_when_effective_nc_is_empty():
    session = _RecordingSession()
    client = _client(session)

    with pytest.raises(EstimationValidationError):
        client.import_estimation(_valid_design())

    assert session.calls == []


def test_update_validates_nested_atlas_dto_and_preserves_wire_payload():
    session = _RecordingSession({"id": 91})
    client = _client(session)
    payload = {
        "id": 91,
        "name": "NC-required Estimation",
        "specification": json.dumps(_valid_design()),
    }

    result = client.update_estimation(91, payload)

    assert result == {"id": 91}
    assert session.calls == [
        (
            "PUT",
            "https://example.test/api/v1/atlas/7/203/estimation/91",
            {"json": payload},
        )
    ]


def test_get_validated_export_returns_export_and_proof():
    exported = _valid_export(tco_count=2)
    session = _RecordingSession(exported)
    client = _client(session)

    validated = client.get_validated_estimation_export(91)

    assert isinstance(validated, ValidatedEstimationExport)
    assert validated.estimation_id == 91
    assert validated.export == exported
    assert validated.export is not exported
    assert validated.validation.stage == "export"
    assert validated.validation.effective_nc_count == 2
    assert session.calls[0][0] == "GET"
