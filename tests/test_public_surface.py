"""The guarded helpers must be reachable from the package's public surface.

The fracture-treatment knowledge base told readers to call
`atlas_auto.characterization_safety.design_of`, but the package neither imported
nor exported that module, so it was a private submodule that only someone who
had already read the source would find. A helper nobody can find is a helper
nobody uses, and the trap it closes gets rediscovered instead.
"""

import atlas_auto

GUARDS = [
    # generation_safety: COMPLETE alone is not success (AUMC 2026-08-15)
    "GenerationNotValidError",
    "assert_generation_valid",
    "finished_generation",
    "generation_status",
    "is_finished_generation",
    "is_usable_generation",
    "resolve_source_id",
    "rows_for_source",
    "usable_generation",
    # characterization_safety: WebAPI read/write contract guards
    "assert_design_present",
    "assert_membership",
    "cohort_entry",
    "counts_by_analysis",
    "design_key",
    "design_of",
    "feature_identity",
    "fetch_results",
    "import_characterization_checked",
    "import_characterization_mapped",
    "preset_name",
    # characterization: a short result list is an error, not a zero
    "CharacterizationResultCountError",
    # attrition: never chain countSatisfying
    "cumulative_attrition",
    "format_attrition",
    # study_runner: the required deploy-inspect-trigger-monitor sequence
    "STAGES",
    "StageOrderError",
    "StudyRun",
    "UncertainCreateError",
    "canonical_json",
    "digest",
    "write_evidence",
]


def test_every_guard_is_importable_from_the_package_root():
    missing = [name for name in GUARDS if not hasattr(atlas_auto, name)]
    assert missing == []


def test_every_guard_is_declared_in_all():
    undeclared = [name for name in GUARDS if name not in atlas_auto.__all__]
    assert undeclared == []


def test_all_entries_actually_resolve():
    """`__all__` must not name anything the module does not define."""
    dangling = [name for name in atlas_auto.__all__ if not hasattr(atlas_auto, name)]
    assert dangling == []
