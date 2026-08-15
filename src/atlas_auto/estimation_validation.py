"""Pure, fail-closed validation for negative-control Estimation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple


_REMEDIATION = (
    "select and resolve a non-empty negative-control concept set, then export "
    "the Estimation again before import or execution"
)


@dataclass(frozen=True)
class EstimationValidationIssue:
    """One safe-to-log Estimation contract violation."""

    code: str
    field: str
    message: str


@dataclass(frozen=True)
class EstimationValidationResult:
    """Proof returned after a pure Estimation validation succeeds."""

    stage: str
    estimation_id: Optional[int]
    estimation_name: Optional[str]
    referenced_concept_set_ids: Tuple[int, ...]
    effective_nc_count: int
    tco_pairs: Tuple[Tuple[Optional[int], Optional[int]], ...]
    tco_nc_counts: Tuple[int, ...]


@dataclass(frozen=True)
class ValidatedEstimationExport:
    """An Estimation export coupled to the proof generated for that payload."""

    estimation_id: int
    export: dict
    validation: EstimationValidationResult


class EstimationValidationError(ValueError):
    """Structured, payload-safe failure for an Estimation NC contract."""

    def __init__(
        self,
        *,
        stage: str,
        issues: Tuple[EstimationValidationIssue, ...],
        estimation_id: Optional[int],
        estimation_name: Optional[str],
        referenced_concept_set_ids: Tuple[int, ...],
        effective_nc_count: int,
    ) -> None:
        self.stage = stage
        self.issues = issues
        self.estimation_id = estimation_id
        self.estimation_name = estimation_name
        self.referenced_concept_set_ids = referenced_concept_set_ids
        self.effective_nc_count = effective_nc_count
        self.remediation = _REMEDIATION
        identity = estimation_name or (
            str(estimation_id) if estimation_id is not None else "unknown"
        )
        fields = ",".join(sorted({issue.field for issue in issues}))
        codes = ",".join(issue.code for issue in issues)
        super().__init__(
            "Estimation validation failed "
            f"(stage={stage}, estimation={identity}, fields={fields}, "
            f"concept_set_ids={list(referenced_concept_set_ids)}, "
            f"effective_nc_count={effective_nc_count}, codes={codes}). "
            f"Action: {_REMEDIATION}."
        )


def _positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _nonnegative_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _identity(spec: Mapping[str, Any]) -> Tuple[Optional[int], Optional[str]]:
    estimation_id = _positive_int(spec.get("id"))
    name = spec.get("name")
    estimation_name = name.strip() if isinstance(name, str) and name.strip() else None
    return estimation_id, estimation_name


def _analysis_tcos(spec: Mapping[str, Any]) -> list:
    settings = spec.get("estimationAnalysisSettings")
    if not isinstance(settings, Mapping):
        return []
    analysis = settings.get("analysisSpecification")
    if not isinstance(analysis, Mapping):
        return []
    return _list(analysis.get("targetComparatorOutcomes"))


def _has_included_concept_item(items: list) -> bool:
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if item.get("isExcluded") in (True, 1, "true", "1"):
            continue
        concept = item.get("concept")
        if not isinstance(concept, Mapping):
            concept = item
        concept_id = concept.get("CONCEPT_ID", concept.get("conceptId"))
        if _positive_int(concept_id) is not None:
            return True
    return False


def _has_valid_resolved_nc(rows: list, tco_pairs: list) -> bool:
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        pair = (_positive_int(row.get("targetId")), _positive_int(row.get("comparatorId")))
        if pair in tco_pairs and _positive_int(row.get("outcomeId")) is not None:
            return True
    return False


def _validate(spec: Mapping[str, Any], *, stage: str) -> EstimationValidationResult:
    if not isinstance(spec, Mapping):
        issue = EstimationValidationIssue(
            "invalid_estimation_spec",
            "$",
            "Estimation specification must be a JSON object",
        )
        raise EstimationValidationError(
            stage=stage,
            issues=(issue,),
            estimation_id=None,
            estimation_name=None,
            referenced_concept_set_ids=(),
            effective_nc_count=0,
        )

    issues = []
    estimation_id, estimation_name = _identity(spec)
    negative_controls_value = spec.get("negativeControls")
    negative_controls = _list(negative_controls_value)
    effective_nc_count = len(negative_controls)
    if "negativeControls" not in spec or not isinstance(
        negative_controls_value, list
    ):
        issues.append(
            EstimationValidationIssue(
                "invalid_negative_controls",
                "negativeControls",
                "negativeControls must be present as a JSON array",
            )
        )

    definition = spec.get("negativeControlOutcomeCohortDefinition")
    if not isinstance(definition, Mapping) or not definition:
        issues.append(
            EstimationValidationIssue(
                "missing_nc_outcome_definition",
                "negativeControlOutcomeCohortDefinition",
                "A non-empty negative-control outcome cohort definition is required",
            )
        )

    tcos = _analysis_tcos(spec)
    if not tcos:
        issues.append(
            EstimationValidationIssue(
                "missing_target_comparator_outcomes",
                "estimationAnalysisSettings.analysisSpecification.targetComparatorOutcomes",
                "At least one target-comparator-outcome entry is required",
            )
        )
    tco_pairs = []
    for index, tco in enumerate(tcos):
        if not isinstance(tco, Mapping):
            target_id = comparator_id = None
        else:
            target_id = _positive_int(tco.get("targetId"))
            comparator_id = _positive_int(tco.get("comparatorId"))
        tco_pairs.append((target_id, comparator_id))
        if target_id is None or comparator_id is None:
            issues.append(
                EstimationValidationIssue(
                    "invalid_tco_pair",
                    (
                        "estimationAnalysisSettings.analysisSpecification."
                        f"targetComparatorOutcomes[{index}]"
                    ),
                    "TCO targetId and comparatorId must be positive integers",
                )
            )

    concept_sets = _list(spec.get("conceptSets"))
    concept_sets_by_id = {}
    duplicate_concept_set_ids = set()
    for concept_set in concept_sets:
        if not isinstance(concept_set, Mapping):
            continue
        concept_set_id = _positive_int(concept_set.get("id"))
        if concept_set_id is None:
            continue
        if concept_set_id in concept_sets_by_id:
            duplicate_concept_set_ids.add(concept_set_id)
        else:
            concept_sets_by_id[concept_set_id] = concept_set

    all_xrefs = _list(spec.get("conceptSetCrossReference"))
    nc_xrefs = [
        xref
        for xref in all_xrefs
        if isinstance(xref, Mapping)
        and xref.get("targetName") == "negativeControlOutcomes"
    ]
    if not nc_xrefs:
        issues.append(
            EstimationValidationIssue(
                "missing_nc_cross_reference",
                "conceptSetCrossReference",
                "At least one negativeControlOutcomes cross-reference is required",
            )
        )

    referenced_ids = set()
    valid_target_indices = set()
    seen_xrefs = set()
    duplicate_xrefs = set()
    for index, xref in enumerate(nc_xrefs):
        field = f"conceptSetCrossReference[{index}]"
        concept_set_id = _positive_int(xref.get("conceptSetId"))
        target_index = _nonnegative_int(xref.get("targetIndex"))
        property_name = xref.get("propertyName")

        if concept_set_id is None:
            issues.append(
                EstimationValidationIssue(
                    "missing_nc_concept_set_id",
                    f"{field}.conceptSetId",
                    "NC cross-reference conceptSetId must be a positive integer",
                )
            )
        else:
            referenced_ids.add(concept_set_id)
            if concept_set_id not in concept_sets_by_id:
                issues.append(
                    EstimationValidationIssue(
                        "unknown_nc_concept_set",
                        f"{field}.conceptSetId",
                        "NC cross-reference points to no concept set in this Estimation",
                    )
                )

        if property_name != "outcomeId":
            issues.append(
                EstimationValidationIssue(
                    "invalid_nc_property",
                    f"{field}.propertyName",
                    "NC cross-reference propertyName must be outcomeId",
                )
            )

        if target_index is None or target_index >= len(tcos):
            issues.append(
                EstimationValidationIssue(
                    "invalid_nc_target_index",
                    f"{field}.targetIndex",
                    "NC cross-reference targetIndex is outside the TCO list",
                )
            )
        else:
            valid_target_indices.add(target_index)

        key = (concept_set_id, target_index, property_name)
        if key in seen_xrefs:
            duplicate_xrefs.add(key)
        seen_xrefs.add(key)

    if duplicate_xrefs:
        issues.append(
            EstimationValidationIssue(
                "duplicate_nc_cross_reference",
                "conceptSetCrossReference",
                "Duplicate negative-control cross-references are not allowed",
            )
        )
    if duplicate_concept_set_ids.intersection(referenced_ids):
        issues.append(
            EstimationValidationIssue(
                "duplicate_nc_concept_set_id",
                "conceptSets",
                "Referenced negative-control concept set IDs must be unique",
            )
        )

    if not _has_valid_resolved_nc(negative_controls, tco_pairs):
        for concept_set_id in sorted(referenced_ids.intersection(concept_sets_by_id)):
            concept_set = concept_sets_by_id[concept_set_id]
            expression = concept_set.get("expression")
            items = _list(expression.get("items")) if isinstance(expression, Mapping) else []
            if not _has_included_concept_item(items):
                issues.append(
                    EstimationValidationIssue(
                        "empty_nc_concept_set",
                        f"conceptSets[id={concept_set_id}].expression.items",
                        "Referenced NC concept set has no expression items",
                    )
                )

    valid_rows = []
    triples = []
    for index, row in enumerate(negative_controls):
        field = f"negativeControls[{index}]"
        if not isinstance(row, Mapping):
            target_id = comparator_id = outcome_id = None
        else:
            target_id = _positive_int(row.get("targetId"))
            comparator_id = _positive_int(row.get("comparatorId"))
            outcome_id = _positive_int(row.get("outcomeId"))
        pair = (target_id, comparator_id)
        if stage == "export" and pair not in tco_pairs:
            issues.append(
                EstimationValidationIssue(
                    "invalid_nc_tco_pair",
                    field,
                    "Negative-control targetId/comparatorId does not match a TCO pair",
                )
            )
        if stage == "export" and outcome_id is None:
            issues.append(
                EstimationValidationIssue(
                    "invalid_nc_outcome_id",
                    f"{field}.outcomeId",
                    "Negative-control outcomeId must be a positive integer",
                )
            )
        if target_id is not None and comparator_id is not None and outcome_id is not None:
            triple = (target_id, comparator_id, outcome_id)
            triples.append(triple)
            valid_rows.append((target_id, comparator_id, outcome_id))

    if stage == "export":
        if not negative_controls:
            issues.append(
                EstimationValidationIssue(
                    "missing_effective_negative_controls",
                    "negativeControls",
                    "Final Estimation export must contain at least one effective NC",
                )
            )
        if len(set(triples)) != len(triples):
            issues.append(
                EstimationValidationIssue(
                    "duplicate_negative_control",
                    "negativeControls",
                    "Duplicate targetId/comparatorId/outcomeId triples are not allowed",
                )
            )
        missing_xref_indices = set(range(len(tcos))).difference(valid_target_indices)
        if missing_xref_indices:
            issues.append(
                EstimationValidationIssue(
                    "missing_tco_nc_cross_reference",
                    "conceptSetCrossReference",
                    "Every TCO index must have a negative-control cross-reference",
                )
            )

    tco_nc_counts = tuple(
        sum(1 for target_id, comparator_id, _ in valid_rows if (target_id, comparator_id) == pair)
        for pair in tco_pairs
    )
    if stage == "export" and any(count == 0 for count in tco_nc_counts):
        issues.append(
            EstimationValidationIssue(
                "missing_tco_effective_negative_control",
                "negativeControls",
                "Every TCO pair must have at least one matching effective NC",
            )
        )

    referenced_concept_set_ids = tuple(sorted(referenced_ids))
    if issues:
        raise EstimationValidationError(
            stage=stage,
            issues=tuple(issues),
            estimation_id=estimation_id,
            estimation_name=estimation_name,
            referenced_concept_set_ids=referenced_concept_set_ids,
            effective_nc_count=effective_nc_count,
        )

    return EstimationValidationResult(
        stage=stage,
        estimation_id=estimation_id,
        estimation_name=estimation_name,
        referenced_concept_set_ids=referenced_concept_set_ids,
        effective_nc_count=effective_nc_count,
        tco_pairs=tuple(tco_pairs),
        tco_nc_counts=tco_nc_counts,
    )


def validate_estimation_design(spec: Mapping[str, Any]) -> EstimationValidationResult:
    """Validate a stored/design Estimation before any mutation."""

    return _validate(spec, stage="design")


def validate_estimation_export(spec: Mapping[str, Any]) -> EstimationValidationResult:
    """Validate a final resolved Estimation export before import."""

    return _validate(spec, stage="export")


__all__ = [
    "EstimationValidationError",
    "EstimationValidationIssue",
    "EstimationValidationResult",
    "ValidatedEstimationExport",
    "validate_estimation_design",
    "validate_estimation_export",
]
