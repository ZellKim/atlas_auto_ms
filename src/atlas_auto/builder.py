"""
Estimation Study Builder
========================
ATLAS WebAPI 형식의 Estimation 스펙을 프로그래밍 방식으로 생성합니다.
기존 ATLAS에서 export한 코호트 JSON을 활용할 수 있습니다.
"""

import json
import copy
from pathlib import Path


# ─── 기본 Covariate 설정 (OHDSI 표준) ─────────────────

DEFAULT_COVARIATE_SETTINGS = {
    "attr_class": "covariateSettings",
    "temporal": False,
    "DemographicsGender": True,
    "DemographicsAge": False,
    "DemographicsAgeGroup": True,
    "DemographicsRace": False,
    "DemographicsEthnicity": False,
    "DemographicsIndexYear": False,
    "DemographicsIndexMonth": False,
    "DemographicsPriorObservationTime": False,
    "DemographicsPostObservationTime": False,
    "DemographicsTimeInCohort": False,
    "DemographicsIndexYearMonth": False,
    "ConditionOccurrenceAnyTimePrior": False,
    "ConditionOccurrenceLongTerm": True,
    "ConditionOccurrenceMediumTerm": False,
    "ConditionOccurrenceShortTerm": False,
    "ConditionOccurrencePrimaryInpatientAnyTimePrior": False,
    "ConditionOccurrencePrimaryInpatientLongTerm": True,
    "ConditionOccurrencePrimaryInpatientMediumTerm": False,
    "ConditionOccurrencePrimaryInpatientShortTerm": False,
    "ConditionEraAnyTimePrior": False,
    "ConditionEraLongTerm": True,
    "ConditionEraMediumTerm": False,
    "ConditionEraShortTerm": False,
    "ConditionEraOverlapping": False,
    "ConditionEraStartLongTerm": False,
    "ConditionEraStartMediumTerm": False,
    "ConditionEraStartShortTerm": False,
    "ConditionGroupEraAnyTimePrior": False,
    "ConditionGroupEraLongTerm": False,
    "ConditionGroupEraMediumTerm": False,
    "ConditionGroupEraShortTerm": False,
    "ConditionGroupEraOverlapping": False,
    "ConditionGroupEraStartLongTerm": False,
    "ConditionGroupEraStartMediumTerm": False,
    "ConditionGroupEraStartShortTerm": False,
    "DrugExposureAnyTimePrior": False,
    "DrugExposureLongTerm": True,
    "DrugExposureMediumTerm": False,
    "DrugExposureShortTerm": False,
    "DrugEraAnyTimePrior": False,
    "DrugEraLongTerm": True,
    "DrugEraMediumTerm": False,
    "DrugEraShortTerm": False,
    "DrugEraOverlapping": False,
    "DrugEraStartLongTerm": False,
    "DrugEraStartMediumTerm": False,
    "DrugEraStartShortTerm": False,
    "DrugGroupEraAnyTimePrior": False,
    "DrugGroupEraLongTerm": True,
    "DrugGroupEraMediumTerm": False,
    "DrugGroupEraShortTerm": False,
    "DrugGroupEraOverlapping": False,
    "DrugGroupEraStartLongTerm": False,
    "DrugGroupEraStartMediumTerm": False,
    "DrugGroupEraStartShortTerm": False,
    "ProcedureOccurrenceAnyTimePrior": False,
    "ProcedureOccurrenceLongTerm": False,
    "ProcedureOccurrenceMediumTerm": False,
    "ProcedureOccurrenceShortTerm": False,
    "DeviceExposureAnyTimePrior": False,
    "DeviceExposureLongTerm": False,
    "DeviceExposureMediumTerm": False,
    "DeviceExposureShortTerm": False,
    "MeasurementAnyTimePrior": False,
    "MeasurementLongTerm": False,
    "MeasurementMediumTerm": False,
    "MeasurementShortTerm": False,
    "MeasurementValueAnyTimePrior": False,
    "MeasurementValueLongTerm": False,
    "MeasurementValueMediumTerm": False,
    "MeasurementValueShortTerm": False,
    "MeasurementRangeGroupAnyTimePrior": False,
    "MeasurementRangeGroupLongTerm": False,
    "MeasurementRangeGroupMediumTerm": False,
    "MeasurementRangeGroupShortTerm": False,
    "ObservationAnyTimePrior": False,
    "ObservationLongTerm": False,
    "ObservationMediumTerm": False,
    "ObservationShortTerm": False,
    "CharlsonIndex": False,
    "Dcsi": False,
    "Chads2": False,
    "Chads2Vasc": False,
    "DistinctConditionCountLongTerm": False,
    "DistinctConditionCountMediumTerm": False,
    "DistinctConditionCountShortTerm": False,
    "DistinctIngredientCountLongTerm": False,
    "DistinctIngredientCountMediumTerm": False,
    "DistinctIngredientCountShortTerm": False,
    "DistinctProcedureCountLongTerm": False,
    "DistinctProcedureCountMediumTerm": False,
    "DistinctProcedureCountShortTerm": False,
    "DistinctMeasurementCountLongTerm": False,
    "DistinctMeasurementCountMediumTerm": False,
    "DistinctMeasurementCountShortTerm": False,
    "DistinctObservationCountLongTerm": False,
    "DistinctObservationCountMediumTerm": False,
    "DistinctObservationCountShortTerm": False,
    "VisitCountLongTerm": False,
    "VisitCountMediumTerm": False,
    "VisitCountShortTerm": False,
    "VisitConceptCountLongTerm": False,
    "VisitConceptCountMediumTerm": False,
    "VisitConceptCountShortTerm": False,
    "longTermStartDays": -365,
    "mediumTermStartDays": -180,
    "shortTermStartDays": -30,
    "endDays": 0,
    "includedCovariateConceptIds": [],
    "addDescendantsToInclude": False,
    "excludedCovariateConceptIds": [],
    "addDescendantsToExclude": True,
    "includedCovariateIds": [],
    "attr_fun": "getDbDefaultCovariateData",
}

DEFAULT_PRIOR = {
    "attr_class": "cyclopsPrior",
    "priorType": "laplace",
    "variance": 1,
    "exclude": 0,
    "graph": None,
    "neighborhood": None,
    "useCrossValidation": True,
    "forceIntercept": False,
}

DEFAULT_CONTROL = {
    "attr_class": "cyclopsControl",
    "maxIterations": 1000,
    "tolerance": 2e-7,
    "convergenceType": "gradient",
    "cvType": "auto",
    "fold": 10,
    "lowerLimit": 0.01,
    "upperLimit": 20,
    "gridSteps": 10,
    "cvRepetitions": 10,
    "minCVData": 100,
    "noiseLevel": "silent",
    "seed": None,
    "resetCoefficients": False,
    "startingVariance": 0.01,
    "useKKTSwindle": False,
    "tuneSwindle": 10,
    "selectorType": "auto",
    "initialBound": 2,
    "maxBoundCount": 5,
    "autoSearch": True,
    "algorithm": "ccd",
}


class EstimationBuilder:
    """Estimation 스펙을 단계적으로 구성하는 빌더"""

    def __init__(self, name: str, description: str = ""):
        self.spec = {
            "name": name,
            "description": description,
            "version": "v2.7.0",
            "skeletonType": "ComparativeEffectStudy",
            "skeletonVersion": "v0.0.1",
            "cohortDefinitions": [],
            "conceptSets": [],
            "conceptSetCrossReference": [],
            "negativeControls": [],
            "doPositiveControlSynthesis": False,
            "positiveControlSynthesisArgs": None,
            "negativeControlOutcomeCohortDefinition": {
                "occurrenceType": "first",
                "detectOnDescendants": True,
                "domains": ["condition", "procedure"],
            },
            "negativeControlExposureCohortDefinition": {},
            "estimationAnalysisSettings": {
                "estimationType": "ComparativeCohortAnalysis",
                "analysisSpecification": {
                    "targetComparatorOutcomes": [],
                    "cohortMethodAnalysisList": [],
                },
            },
        }

    # ─── 코호트 정의 추가 ─────────────────────────────

    def add_cohort_definition(self, cohort_id: int, name: str, expression: dict = None):
        """코호트 정의 추가"""
        cohort_def = {"id": cohort_id, "name": name}
        if expression:
            cohort_def["expression"] = expression
        self.spec["cohortDefinitions"].append(cohort_def)
        return self

    def add_cohort_from_json(self, cohort_id: int, name: str, json_path: str):
        """JSON 파일에서 코호트 정의 로드"""
        with open(json_path, "r", encoding="utf-8") as f:
            expression = json.load(f)
        return self.add_cohort_definition(cohort_id, name, expression)

    def load_cohorts_from_directory(self, cohort_csv_path: str, cohort_json_dir: str):
        """기존 evidnet 패키지 구조에서 코호트 로드

        Args:
            cohort_csv_path: inst/Cohorts.csv 경로
            cohort_json_dir: inst/cohorts/ 디렉토리 경로
        """
        import csv
        with open(cohort_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = int(row["cohortId"])
                name = row["cohortName"]
                json_file = Path(cohort_json_dir) / f"{cid}.json"
                if json_file.exists():
                    self.add_cohort_from_json(cid, name, str(json_file))
                else:
                    self.add_cohort_definition(cid, name)
        return self

    # ─── Target-Comparator-Outcome 설정 ───────────────

    def add_target_comparator_outcomes(
        self,
        target_id: int,
        comparator_id: int,
        outcome_ids: list,
        excluded_covariate_concept_ids: list = None,
        included_covariate_concept_ids: list = None,
    ):
        """TCO (Target-Comparator-Outcome) 추가"""
        tco = {
            "targetId": target_id,
            "comparatorId": comparator_id,
            "outcomeIds": outcome_ids,
            "excludedCovariateConceptIds": excluded_covariate_concept_ids or [],
            "includedCovariateConceptIds": included_covariate_concept_ids or [],
        }
        self.spec["estimationAnalysisSettings"]["analysisSpecification"][
            "targetComparatorOutcomes"
        ].append(tco)
        return self

    # ─── CohortMethod Analysis 설정 ───────────────────

    def add_cm_analysis(
        self,
        analysis_id: int = 1,
        description: str = "PS stratification, Cox",
        first_exposure_only: bool = False,
        washout_period: int = 0,
        remove_duplicate_subjects: str = "keep all",
        restrict_to_common_period: bool = True,
        max_cohort_size: int = 0,
        covariate_settings: dict = None,
        remove_prior_outcome: bool = True,
        prior_outcome_lookback: int = 99999,
        min_days_at_risk: int = 1,
        risk_window_start: int = 0,
        risk_window_end: int = 30,
        add_exposure_days_to_end: bool = True,
        censor_at_new_risk_window: bool = False,
        create_ps: bool = True,
        ps_max_cohort_size: int = 250000,
        ps_method: str = "stratify",
        match_max_ratio: int = 1,
        match_caliper: float = 0.2,
        stratify_num_strata: int = 5,
        trim_fraction: float = 0.05,
        trim_equipoise_bounds: list = None,
        model_type: str = "cox",
        stratified_cox: bool = True,
        use_covariates: bool = False,
        inverse_pt_weighting: bool = False,
    ):
        """CohortMethod 분석 설정 추가

        Args:
            ps_method: "match", "stratify", "trim", "iptw", "none"
            model_type: "cox", "logistic", "poisson"
        """
        cov_settings = covariate_settings or copy.deepcopy(DEFAULT_COVARIATE_SETTINGS)

        analysis = {
            "attr_class": "cmAnalysis",
            "analysisId": analysis_id,
            "description": description,
            "targetType": None,
            "comparatorType": None,
            "getDbCohortMethodDataArgs": {
                "attr_class": "args",
                "studyStartDate": None,
                "studyEndDate": None,
                "excludeDrugsFromCovariates": False,
                "firstExposureOnly": first_exposure_only,
                "removeDuplicateSubjects": remove_duplicate_subjects,
                "restrictToCommonPeriod": restrict_to_common_period,
                "washoutPeriod": washout_period,
                "maxCohortSize": max_cohort_size,
                "covariateSettings": cov_settings,
            },
            "createStudyPopArgs": {
                "attr_class": "args",
                "firstExposureOnly": False,
                "restrictToCommonPeriod": False,
                "washoutPeriod": 0,
                "removeDuplicateSubjects": "keep all",
                "removeSubjectsWithPriorOutcome": remove_prior_outcome,
                "priorOutcomeLookback": prior_outcome_lookback,
                "minDaysAtRisk": min_days_at_risk,
                "riskWindowStart": risk_window_start,
                "addExposureDaysToStart": False,
                "riskWindowEnd": risk_window_end,
                "addExposureDaysToEnd": add_exposure_days_to_end,
                "censorAtNewRiskWindow": censor_at_new_risk_window,
            },
            "createPs": create_ps,
            "createPsArgs": {
                "attr_class": "args",
                "excludeCovariateIds": [],
                "includeCovariateIds": [],
                "maxCohortSizeForFitting": ps_max_cohort_size,
                "errorOnHighCorrelation": False,
                "stopOnError": True,
                "prior": copy.deepcopy(DEFAULT_PRIOR),
                "control": copy.deepcopy(DEFAULT_CONTROL),
            },
            "trimByPs": ps_method == "trim",
            "trimByPsArgs": {"attr_class": "args", "trimFraction": trim_fraction},
            "trimByPsToEquipoise": False,
            "trimByPsToEquipoiseArgs": {
                "attr_class": "args",
                "bounds": trim_equipoise_bounds or [0.25, 0.75],
            },
            "matchOnPs": ps_method == "match",
            "matchOnPsArgs": {
                "attr_class": "args",
                "caliper": match_caliper,
                "caliperScale": "standardized logit",
                "maxRatio": match_max_ratio,
                "stratificationColumns": [],
            },
            "matchOnPsAndCovariates": False,
            "matchOnPsAndCovariatesArgs": {
                "attr_class": "args",
                "caliper": match_caliper,
                "caliperScale": "standardized logit",
                "maxRatio": match_max_ratio,
                "covariateIds": [],
            },
            "stratifyByPs": ps_method == "stratify",
            "stratifyByPsArgs": {
                "attr_class": "args",
                "numberOfStrata": stratify_num_strata,
                "baseSelection": "all",
                "stratificationColumns": [],
            },
            "stratifyByPsAndCovariates": False,
            "stratifyByPsAndCovariatesArgs": {
                "attr_class": "args",
                "numberOfStrata": stratify_num_strata,
                "baseSelection": "all",
                "covariateIds": [],
            },
            "fitOutcomeModel": True,
            "fitOutcomeModelArgs": {
                "attr_class": "args",
                "modelType": model_type,
                "stratified": stratified_cox,
                "useCovariates": use_covariates,
                "inversePtWeighting": inverse_pt_weighting or (ps_method == "iptw"),
                "interactionCovariateIds": [],
                "excludeCovariateIds": [],
                "includeCovariateIds": [],
                "prior": copy.deepcopy(DEFAULT_PRIOR),
                "control": copy.deepcopy(DEFAULT_CONTROL),
            },
        }

        self.spec["estimationAnalysisSettings"]["analysisSpecification"][
            "cohortMethodAnalysisList"
        ].append(analysis)
        return self

    # ─── Negative Controls ────────────────────────────

    def add_negative_control(self, target_id: int, comparator_id: int,
                             outcome_id: int, outcome_name: str, nc_type: str = "Outcome"):
        self.spec["negativeControls"].append({
            "targetId": target_id,
            "comparatorId": comparator_id,
            "outcomeId": outcome_id,
            "outcomeName": outcome_name,
            "type": nc_type,
        })
        return self

    # ─── 빌드 ─────────────────────────────────────────

    def build(self) -> dict:
        """최종 Estimation 스펙 반환"""
        return copy.deepcopy(self.spec)

    def save(self, path: str):
        """JSON 파일로 저장"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.spec, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "EstimationBuilder":
        """저장된 JSON에서 빌더 복원"""
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f)
        builder = cls(spec.get("name", ""), spec.get("description", ""))
        builder.spec = spec
        return builder

    @classmethod
    def from_existing_package(cls, package_dir: str) -> "EstimationBuilder":
        """기존 evidnet R 패키지에서 빌더 생성

        Args:
            package_dir: R 패키지 루트 디렉토리 (inst/ 포함)
        """
        pkg = Path(package_dir)
        cohorts_csv = pkg / "inst" / "Cohorts.csv"
        cohorts_dir = pkg / "inst" / "cohorts"
        cm_analysis = pkg / "inst" / "settings" / "cmAnalysisList.json"
        tcos_csv = pkg / "inst" / "settings" / "TcosOfInterest.csv"

        desc_file = pkg / "DESCRIPTION"
        name = "Imported Study"
        if desc_file.exists():
            for line in desc_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("Title:"):
                    name = line.split(":", 1)[1].strip()
                    break

        builder = cls(name)

        if cohorts_csv.exists() and cohorts_dir.exists():
            builder.load_cohorts_from_directory(str(cohorts_csv), str(cohorts_dir))

        if tcos_csv.exists():
            import csv
            with open(tcos_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    outcome_ids = [int(x) for x in row["outcomeIds"].split(";") if x.strip()]
                    excluded = [int(x) for x in row.get("excludedCovariateConceptIds", "").split(";") if x.strip()]
                    included = [int(x) for x in row.get("includedCovariateConceptIds", "").split(";") if x.strip()]
                    builder.add_target_comparator_outcomes(
                        target_id=int(row["targetId"]),
                        comparator_id=int(row["comparatorId"]),
                        outcome_ids=outcome_ids,
                        excluded_covariate_concept_ids=excluded,
                        included_covariate_concept_ids=included,
                    )

        if cm_analysis.exists():
            with open(cm_analysis, "r", encoding="utf-8") as f:
                analyses = json.load(f)
            builder.spec["estimationAnalysisSettings"]["analysisSpecification"][
                "cohortMethodAnalysisList"
            ] = analyses

        return builder
