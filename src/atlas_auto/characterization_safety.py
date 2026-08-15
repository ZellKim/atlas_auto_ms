"""Guarded helpers for Cohort Characterization and Feature Analysis work.

Every rule here was established by a live failure against feedernet WebAPI 2.12
during the fracture-treatment study on 2026-08-13 and 2026-08-14. They are kept
in code, not only in prose, because the same traps were hit more than once when
each analysis script re-derived the contract by trial and error.

The traps, and what this module does about them.

Silent wrong answers
    `GET /cohort-characterization/generation/{id}/result` defaults to
    `thresholdLevel=0.01` and drops covariates below 1% prevalence. A trimmed
    result still renders as a plausible table; only the totals betray it. And a
    feature that produced no row is *missing*, not zero, so `dict.get(id, 0)`
    turns an absent analysis into a reported 0%.
    -> `fetch_results` forces `threshold_level=0`, checks the count endpoint, and
       refuses to return when a requested analysis id has no row.

Readback shape
    Member order is not preserved on readback, so list equality fails on designs
    that are in fact identical.
    -> `assert_membership` compares sets and reports the difference.

Unreliable `design` reads
    `GET /feature-analysis/{id}` and the characterization export both return an
    **empty `design`** for CRITERIA_SET features that demonstrably work: v1.15
    features `#851`-`#858` reported an empty design while their generation
    reproduced an independent Pathway's per-ingredient counts to within the
    cohort ratio. Treat an empty design as *unknown*, never as *broken*, and
    never branch analysis logic on it.
    -> `design_of` returns `None` for "not reported" and a parsed list otherwise,
       so callers must handle the difference explicitly.
    -> `assert_design_present` exists only for features this process just created,
       where an empty design does mean the write was dropped.

Two kinds of `design`
    A PRESET feature's `design` is the built-in analysis's *name*, a bare string
    such as `DemographicsGender`, not a criteria list. Reading it as JSON fails,
    which is not a defect and not a missing definition.
    -> `preset_name` reads that case; `design_of` covers CRITERIA_SET only.

Write shapes differ from read shapes
    `POST /feature-analysis/` stores the record but drops a `design` passed as a
    parsed object (HTTP 500) or as a JSON string (HTTP 200, empty design). The
    working path is the characterization import endpoint with complete inline
    feature definitions; passing an existing feature by id alone, or a cohort
    entry without `description` and `expression`, fails with a
    NullPointerException.
    -> `import_characterization_checked` builds from a real export template and
       verifies the result before returning.

Imports do not always create what you submitted
    An import whose feature design already exists **reuses the existing feature**
    and ignores the submitted name. On 2026-08-15 a derived zoledronic feature came
    back as `#881`, a v1.17 feature whose design differed only in a surrogate
    CriteriaGroup id. Code that matches results back by name loses that row.
    -> `import_characterization_mapped` returns submitted name -> stored id, falling
       back to `design_key` equality when the name is absent.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping

__all__ = [
    "CharacterizationSafetyError",
    "assert_membership",
    "design_of",
    "preset_name",
    "assert_design_present",
    "fetch_results",
    "counts_by_analysis",
    "cohort_entry",
    "import_characterization_checked",
    "import_characterization_mapped",
    "feature_identity",
]


class CharacterizationSafetyError(RuntimeError):
    """A guarded WebAPI contract was violated."""


def assert_membership(actual: Any, expected: Any, label: str) -> None:
    """Compare membership, not order. Readback never preserves member order."""
    actual_set, expected_set = set(actual), set(expected)
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        unexpected = sorted(actual_set - expected_set)
        raise CharacterizationSafetyError(
            f"{label} membership mismatch; missing={missing} unexpected={unexpected}"
        )


def design_of(feature: dict) -> list | None:
    """Parse a feature `design`, distinguishing "not reported" from "empty".

    Returns `None` when the API reported nothing, which happens intermittently
    for features that work. Returns a list otherwise.
    """
    design = feature.get("design")
    if isinstance(design, str):
        # A design that is not parseable JSON is unreadable, which is the same
        # situation as not being reported. Raising here would abort a caller that
        # is merely surveying many features.
        try:
            design = json.loads(design) if design.strip() else []
        except json.JSONDecodeError:
            return None
    if not isinstance(design, list):
        return None
    return design or None


def preset_name(feature: dict) -> str | None:
    """The preset a PRESET feature names in its `design`.

    A PRESET feature does not carry a criteria list at all: its `design` is the
    built-in analysis's name, e.g. `DemographicsGender`. That is a complete,
    portable definition, so it must not be read through `design_of` and mistaken
    for a dropped write.
    """
    if str(feature.get("type") or "").upper() != "PRESET":
        return None
    design = feature.get("design")
    if isinstance(design, str) and design.strip():
        return design.strip()
    return None


def assert_design_present(client: Any, feature_id: int, label: str = "") -> list | str:
    """Require a design. Use only for features this process just created.

    A newly written feature with no design means the write was dropped. For
    pre-existing features an empty read is not evidence of damage; see the module
    docstring.
    """
    feature = client.get_feature_analysis(feature_id)
    design = preset_name(feature) or design_of(feature)
    if design is None:
        raise CharacterizationSafetyError(
            f"feature {feature_id} {label} stored no design; the write was dropped"
        )
    return design


def fetch_results(
    client: Any,
    generation_id: int,
    *,
    required_analysis_ids: list[int] | None = None,
    cohort_id: int | None = None,
) -> list[dict]:
    """Fetch every result row, with the trimming and absence traps closed."""
    reported = client.get_characterization_result_count(generation_id)
    results = client.get_characterization_results(generation_id, threshold_level=0)
    if not isinstance(results, list):
        raise CharacterizationSafetyError("characterization results must be a list")
    if reported != len(results):
        raise CharacterizationSafetyError(
            f"result count endpoint reports {reported} rows but {len(results)} were "
            "returned; a thresholdLevel above 0 silently drops low-prevalence rows"
        )
    if required_analysis_ids:
        rows = results if cohort_id is None else [
            row for row in results if row.get("cohortId") == cohort_id
        ]
        present = {row.get("analysisId") for row in rows}
        missing = [aid for aid in required_analysis_ids if aid not in present]
        if missing:
            raise CharacterizationSafetyError(
                f"no result row for analysis ids {missing}; absence is not a zero count"
            )
    return results


def counts_by_analysis(results: list[dict], cohort_id: int) -> dict[int, int]:
    """Map analysis id to count for one cohort, refusing duplicate rows."""
    counts: dict[int, int] = {}
    for row in results:
        if row.get("cohortId") != cohort_id:
            continue
        analysis_id = row.get("analysisId")
        if analysis_id in counts:
            raise CharacterizationSafetyError(
                f"duplicate result row for analysis {analysis_id} in cohort {cohort_id}"
            )
        counts[analysis_id] = row.get("count")
    return counts


def membership_overlap(
    counts: Mapping[Any, int], denominator: int, *, label: Any = None,
) -> int:
    """How many memberships the feature rows carry beyond the cohort's N.

    **A characterization's rows do not partition its cohort.** A subject can
    satisfy several CRITERIA_SET features at once, so the counts sum to at least
    the cohort N and usually to more. Asserting equality fails on correct data;
    asserting nothing lets a growing overlap pass unnoticed and lets a reader
    reconcile a column that was never meant to add up.

    Established twice in the fracture-treatment study. Fracture-site membership
    at KHNMC summed to 1,979 against a cohort of 1,864. Then initial-ingredient
    membership, where a patient starting two agents on the same day is counted
    under both: KHNMC totalled 2 duplicated memberships across the two P2 arms,
    AUMC 24 — twelve times as many, tracking that site's 27-versus-3 same-day
    cross-class ties. The guard existed in one version's build script and the
    later multi-site path did not run it, which is why it lives here now.

    Returns the overlap. Raises when the sum falls **below** the denominator,
    which is a different defect: some subject matched no feature at all.
    """
    if denominator < 0:
        raise ValueError(f"denominator must not be negative, got {denominator}")
    total = sum(counts.values())
    if total < denominator:
        where = f" for {label}" if label is not None else ""
        raise ValueError(
            f"feature counts{where} sum to {total}, below the cohort denominator "
            f"{denominator}; some subjects matched no feature, which is a hole in "
            f"the definitions rather than an overlap"
        )
    return total - denominator


def cohort_entry(client: Any, template_entry: dict, cohort_id: int) -> dict[str, Any]:
    """A cohort element in import shape, taken from a real export element.

    The import DTO needs `description` and `expression`, not just id and name.
    """
    dto = client.get_cohort_definition(cohort_id)
    entry = {key: copy.deepcopy(template_entry[key]) for key in template_entry}
    entry["id"] = dto["id"]
    entry["name"] = dto["name"]
    entry["description"] = dto.get("description") or ""
    raw = dto["expression"]
    entry["expression"] = (
        json.loads(raw)
        if isinstance(template_entry.get("expression"), dict) and isinstance(raw, str)
        else raw
    )
    return entry


def design_key(design: list | None) -> str:
    """A design's meaning, with server-assigned surrogate ids removed.

    `id` on a CriteriaGroup or an aggregate is minted by the server and differs
    between two records that mean exactly the same thing. `CodesetId` and the rest
    of the criteria survive, so this is an identity for the definition itself.
    """
    def strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {key: strip(value) for key, value in sorted(node.items()) if key != "id"}
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    return json.dumps(strip(design or []), sort_keys=True, ensure_ascii=False)


def feature_identity(feature: dict) -> str | None:
    """What makes one CRITERIA_SET feature different from another.

    The `design` alone does **not** identify a feature. The eight initial-ingredient
    features all share the same design — one DrugExposure on `CodesetId 0` in window
    `[0, 0]` — and differ only in which concept set that codeset points at. Matching
    on design alone made five features match one submission.

    Returns `None` when the design cannot be read, so an unknown feature is never
    reported as equal to anything.
    """
    design = design_of(feature)
    if design is None:
        return None
    raw = feature.get("conceptSets")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else []
        except json.JSONDecodeError:
            raw = []
    concept_sets = []
    for entry in raw or []:
        items = (entry.get("expression") or {}).get("items") or []
        concepts = sorted(
            (item.get("concept") or {}).get("CONCEPT_ID")
            for item in items
        )
        concept_sets.append({
            "id": entry.get("id"),
            "concepts": [c for c in concepts if c is not None],
        })
    concept_sets.sort(key=lambda entry: (entry["id"] is None, entry["id"]))
    return json.dumps(
        {"design": design_key(design), "conceptSets": concept_sets},
        sort_keys=True, ensure_ascii=False,
    )


def _stored_design(client: Any, feature: dict) -> list | None:
    """A stored feature's design, falling back to the feature endpoint.

    A characterization export reports CRITERIA_SET designs as empty.
    """
    design = design_of(feature)
    if design is not None:
        return design
    try:
        return design_of(client.get_feature_analysis(feature["id"]))
    except Exception:
        return None


def import_characterization_mapped(
    client: Any,
    *,
    template_characterization_id: int,
    name: str,
    cohort_ids: list[int],
    inline_features: list[dict],
) -> tuple[int, dict[str, int]]:
    """Import a characterization built from a real export, then verify it.

    `POST /feature-analysis/` cannot be used to create a working CRITERIA_SET
    feature. This endpoint can, provided every feature is a complete inline
    definition and every cohort entry is complete.

    Returns the new characterization id and a map from each submitted feature name
    to the feature id actually stored. **The server does not always create a new
    feature.** When an existing feature already carries the same design it is
    reused and the submitted name is ignored, so the mapping is not the identity
    and callers that match results by name will lose a row.
    """
    if not inline_features:
        raise CharacterizationSafetyError("inline_features must not be empty")
    for feature in inline_features:
        if "id" in feature:
            raise CharacterizationSafetyError(
                "an inline feature must not carry an id; the import DTO rejects "
                "features passed by reference"
            )
        if preset_name(feature) is None and design_of(feature) is None:
            raise CharacterizationSafetyError(
                f"inline feature {feature.get('name')!r} has no design to import"
            )

    template = client.export_characterization(template_characterization_id)
    body = {
        **{key: copy.deepcopy(value) for key, value in template.items() if key != "id"},
        "name": name,
        "cohorts": [cohort_entry(client, template["cohorts"][0], cid) for cid in cohort_ids],
        "featureAnalyses": [copy.deepcopy(f) for f in inline_features],
    }
    created = client.import_characterization(body)
    characterization_id = created["id"]

    saved = client.export_characterization(characterization_id)
    assert_membership([c["id"] for c in saved["cohorts"]], cohort_ids, "imported cohorts")

    stored_by_name = {f["name"]: f for f in saved["featureAnalyses"]}
    mapping: dict[str, int] = {}
    claimed: set[int] = set()
    for feature in inline_features:
        submitted_name = feature["name"]
        stored = stored_by_name.get(submitted_name)
        if stored is None:
            wanted = feature_identity(feature)
            # A candidate whose design cannot be read is *unknown*, not equal.
            candidates = []
            for candidate in saved["featureAnalyses"]:
                if candidate["id"] in claimed:
                    continue
                record = candidate
                if design_of(candidate) is None:
                    try:
                        record = client.get_feature_analysis(candidate["id"])
                    except Exception:
                        continue
                identity = feature_identity(record)
                if identity is not None and identity == wanted:
                    candidates.append(candidate)
            if not candidates:
                raise CharacterizationSafetyError(
                    f"no stored feature matches {submitted_name!r} by name or by design; "
                    "the write was dropped"
                )
            if len(candidates) > 1:
                raise CharacterizationSafetyError(
                    f"{len(candidates)} stored features match {submitted_name!r} by design; "
                    "the mapping is ambiguous"
                )
            stored = candidates[0]
        mapping[submitted_name] = stored["id"]
        claimed.add(stored["id"])
        assert_design_present(client, stored["id"], submitted_name)
    return characterization_id, mapping


def import_characterization_checked(
    client: Any,
    *,
    template_characterization_id: int,
    name: str,
    cohort_ids: list[int],
    inline_features: list[dict],
) -> int:
    """`import_characterization_mapped`, discarding the feature mapping.

    Prefer the mapped form whenever results are matched back to a feature: the
    server may substitute an existing feature and the names will not line up.
    """
    characterization_id, _ = import_characterization_mapped(
        client,
        template_characterization_id=template_characterization_id,
        name=name,
        cohort_ids=cohort_ids,
        inline_features=inline_features,
    )
    return characterization_id
