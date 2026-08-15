"""
atlas-auto: OHDSI ATLAS/feedernet Automation Toolkit
=====================================================
feedernet 포탈 로그인 → 기관별 ATLAS WebAPI를 통한
코호트 설계, Estimation 실행, 결과 다운로드 자동화 패키지
"""

from atlas_auto.client import AtlasApiError, FedernetClient
from atlas_auto.characterization import (
    CharacterizationResultCountError,
    CharacterizationService,
    EnsureResult,
    GenerationResult,
)
from atlas_auto.attrition import cumulative_attrition, format_attrition
from atlas_auto.generation_safety import (
    GenerationNotValidError,
    assert_generation_valid,
    finished_generation,
    generation_status,
    is_finished_generation,
    is_usable_generation,
    resolve_source_id,
    rows_for_source,
    usable_generation,
)
from atlas_auto.characterization_safety import (
    assert_design_present,
    assert_membership,
    cohort_entry,
    counts_by_analysis,
    design_key,
    design_of,
    feature_identity,
    fetch_results,
    import_characterization_checked,
    import_characterization_mapped,
    membership_overlap,
    preset_name,
)
from atlas_auto.multisite_characterization import (
    DeploymentRecord,
    MultisiteCharacterizationDeployer,
    SiteTarget,
    select_latest_static_source,
    write_ledger,
)
from atlas_auto.builder import EstimationBuilder
from atlas_auto.cohort_designer import CohortDesigner
from atlas_auto.estimation_validation import (
    EstimationValidationError,
    EstimationValidationIssue,
    EstimationValidationResult,
    ValidatedEstimationExport,
    validate_estimation_design,
    validate_estimation_export,
)
from atlas_auto.protocol import StudyProtocol
from atlas_auto.study_runner import (
    STAGES,
    StageOrderError,
    StudyRun,
    UncertainCreateError,
    canonical_json,
    digest,
    write_evidence,
)
from atlas_auto.runner import run_remote_site, run_local_r_study, run_study

__version__ = "0.2.0"

__all__ = [
    "FedernetClient",
    "AtlasApiError",
    "CharacterizationResultCountError",
    "CharacterizationService",
    "EnsureResult",
    "GenerationResult",
    # attrition — never chain countSatisfying; read treemapData bit strings
    "cumulative_attrition",
    "format_attrition",
    # study_runner — build→deploy→inspect→trigger→capture→monitor→snapshot
    "STAGES",
    "StageOrderError",
    "StudyRun",
    "UncertainCreateError",
    "canonical_json",
    "digest",
    "write_evidence",
    # generation_safety — COMPLETE alone is not success (AUMC 2026-08-15)
    "GenerationNotValidError",
    "assert_generation_valid",
    "finished_generation",
    "generation_status",
    "is_finished_generation",
    "is_usable_generation",
    "resolve_source_id",
    "rows_for_source",
    "usable_generation",
    # characterization_safety — WebAPI read/write contract guards
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
    "membership_overlap",
    "preset_name",
    "MultisiteCharacterizationDeployer",
    "SiteTarget",
    "DeploymentRecord",
    "select_latest_static_source",
    "write_ledger",
    "EstimationBuilder",
    "EstimationValidationError",
    "EstimationValidationIssue",
    "EstimationValidationResult",
    "ValidatedEstimationExport",
    "validate_estimation_design",
    "validate_estimation_export",
    "CohortDesigner",
    "StudyProtocol",
    "run_remote_site",
    "run_local_r_study",
    "run_study",
]
