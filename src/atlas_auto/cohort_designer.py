"""
Cohort Designer
===============
YAML 연구설계 프로토콜 → ATLAS CIRCE JSON 자동 변환

CIRCE JSON 구조 (분석 결과 기반):
- 90%는 고정 상수 (ExpressionLimit, QualifiedLimit, CollapseSettings 등)
- 변하는 부분: ConceptSets, PrimaryCriteria, InclusionRules, ObservationWindow

Usage:
    from atlas_auto import CohortDesigner

    designer = CohortDesigner()
    circe = designer.build_cohort({
        "name": "Appendectomy",
        "domain": "procedure",
        "concepts": [{"concept_id": 4198190, "include_descendants": True}],
        "observation_window": {"prior_days": 365},
        "inclusion_rules": [{"name": "age>=18", "type": "demographic", "age": {"op": "gte", "value": 18}}]
    })
"""

import json
import copy
from pathlib import Path
from typing import Optional


# ─── 고정 상수 (모든 코호트 공통) ─────────────────────

CIRCE_DEFAULTS = {
    "ExpressionLimit": {"Type": "First"},
    "QualifiedLimit": {"Type": "First"},
    "CollapseSettings": {"CollapseType": "ERA", "EraPad": 0},
    "CensorWindow": {"StartDate": None, "EndDate": None},
    "CensoringCriteria": [],
    "cdmVersionRange": ">=5.0.0",
}

# 방문 유형 → Concept ID
VISIT_TYPE_MAP = {
    "inpatient": {"CONCEPT_ID": 9201, "CONCEPT_NAME": "Inpatient Visit",
                  "CONCEPT_CODE": "IP", "VOCABULARY_ID": "Visit",
                  "DOMAIN_ID": "Visit", "CONCEPT_CLASS_ID": "Visit",
                  "STANDARD_CONCEPT": "S", "STANDARD_CONCEPT_CAPTION": "Standard",
                  "INVALID_REASON": "V", "INVALID_REASON_CAPTION": "Valid"},
    "outpatient": {"CONCEPT_ID": 9202, "CONCEPT_NAME": "Outpatient Visit",
                   "CONCEPT_CODE": "OP", "VOCABULARY_ID": "Visit",
                   "DOMAIN_ID": "Visit", "CONCEPT_CLASS_ID": "Visit",
                   "STANDARD_CONCEPT": "S", "STANDARD_CONCEPT_CAPTION": "Standard",
                   "INVALID_REASON": "V", "INVALID_REASON_CAPTION": "Valid"},
    "er": {"CONCEPT_ID": 9203, "CONCEPT_NAME": "Emergency Room Visit",
           "CONCEPT_CODE": "ER", "VOCABULARY_ID": "Visit",
           "DOMAIN_ID": "Visit", "CONCEPT_CLASS_ID": "Visit",
           "STANDARD_CONCEPT": "S", "STANDARD_CONCEPT_CAPTION": "Standard",
           "INVALID_REASON": "V", "INVALID_REASON_CAPTION": "Valid"},
}

# domain → PrimaryCriteria key / DOMAIN_ID / CONCEPT_CLASS_ID defaults
DOMAIN_CONFIG = {
    "condition": {
        "criteria_key": "ConditionOccurrence",
        "domain_id": "Condition",
        "concept_class_default": "Clinical Finding",
        "type_exclude_key": "ConditionTypeExclude",
        "source_concept_key": "ConditionSourceConcept",
        "extra_fields": {
            "OccurrenceEndDate": None, "ConditionType": None,
            "ConditionStatus": None, "StopReason": None,
        },
    },
    "procedure": {
        "criteria_key": "ProcedureOccurrence",
        "domain_id": "Procedure",
        "concept_class_default": "Procedure",
        "type_exclude_key": "ProcedureTypeExclude",
        "source_concept_key": "ProcedureSourceConcept",
        "extra_fields": {
            "ProcedureType": None, "Quantity": None, "Modifier": None,
        },
    },
    "drug": {
        "criteria_key": "DrugExposure",
        "domain_id": "Drug",
        "concept_class_default": "Ingredient",
        "type_exclude_key": "DrugTypeExclude",
        "source_concept_key": "DrugSourceConcept",
        "extra_fields": {
            "OccurrenceEndDate": None, "DrugType": None,
            "Refills": None, "Quantity": None, "DaysSupply": None,
            "RouteConcept": None, "EffectiveDrugDose": None,
            "DoseUnit": None, "LotNumber": None,
        },
    },
    "visit": {
        "criteria_key": "VisitOccurrence",
        "domain_id": "Visit",
        "concept_class_default": "Visit",
        "type_exclude_key": "VisitTypeExclude",
        "source_concept_key": "VisitSourceConcept",
        "extra_fields": {
            "OccurrenceEndDate": None, "VisitLength": None,
            "PlaceOfServiceLocation": None, "PlaceOfService": None,
        },
    },
    "measurement": {
        "criteria_key": "Measurement",
        "domain_id": "Measurement",
        "concept_class_default": "Lab Test",
        "type_exclude_key": "MeasurementTypeExclude",
        "source_concept_key": "MeasurementSourceConcept",
        "extra_fields": {
            "OccurrenceEndDate": None, "MeasurementType": None,
            "Operator": None, "ValueAsNumber": None, "ValueAsConcept": None,
            "Unit": None, "RangeLow": None, "RangeHigh": None,
            "RangeLowOperator": None, "RangeHighOperator": None,
            "RangeLowRatio": None, "RangeHighRatio": None,
            "Abnormal": None,
        },
    },
}


class CohortDesigner:
    """YAML 코호트 정의 → ATLAS CIRCE JSON 변환기"""

    def __init__(self):
        self._concept_set_counter = 0

    def build_cohort(self, cohort_def: dict) -> dict:
        """단일 코호트 정의를 CIRCE JSON으로 변환

        Args:
            cohort_def: YAML에서 로드한 코호트 정의 dict
                - name: 코호트명
                - domain: condition | procedure | drug | visit | measurement
                - concepts: [{concept_id, concept_name?, include_descendants?}]
                - observation_window?: {prior_days, post_days}
                - inclusion_rules?: [...]
                - visit_type?: inpatient | outpatient | er
                - end_strategy?: {type: fixed_offset | drug_era, days?, gap_days?}
        Returns:
            CIRCE JSON dict
        """
        self._concept_set_counter = 0

        domain = cohort_def["domain"]
        if domain not in DOMAIN_CONFIG:
            raise ValueError(f"지원하지 않는 domain: {domain}. 가능: {list(DOMAIN_CONFIG.keys())}")

        circe = copy.deepcopy(CIRCE_DEFAULTS)

        # 1. ConceptSets
        concept_sets = []
        primary_cs_id = self._add_concept_set(
            concept_sets, cohort_def["name"], cohort_def["concepts"], domain
        )

        # 2. PrimaryCriteria
        obs = cohort_def.get("observation_window", {})
        prior_days = obs.get("prior_days", 365 if domain in ("procedure", "visit") else 0)
        post_days = obs.get("post_days", 0)

        criteria_obj = self._build_domain_criteria(
            domain, primary_cs_id, cohort_def.get("visit_type")
        )

        circe["PrimaryCriteria"] = {
            "CriteriaList": [criteria_obj],
            "PrimaryCriteriaLimit": {"Type": "First"},
            "ObservationWindow": {
                "PriorDays": prior_days,
                "PostDays": post_days,
            },
        }

        # 3. InclusionRules
        inclusion_rules = []
        for rule_def in cohort_def.get("inclusion_rules", []):
            rule = self._build_inclusion_rule(rule_def, concept_sets, domain)
            if rule:
                inclusion_rules.append(rule)

        circe["InclusionRules"] = inclusion_rules

        # 4. EndStrategy (optional)
        end_strategy = cohort_def.get("end_strategy")
        if end_strategy:
            circe["EndStrategy"] = self._build_end_strategy(end_strategy, concept_sets)

        # 5. ConceptSets 할당
        circe["ConceptSets"] = concept_sets

        return circe

    def build_cohorts_from_protocol(self, protocol: dict) -> dict:
        """전체 프로토콜에서 모든 코호트 생성

        Args:
            protocol: YAML 프로토콜 dict (cohorts 섹션 포함)
        Returns:
            {"target": circe_json, "comparator": circe_json, "outcomes": [circe_json, ...]}
        """
        cohorts_def = protocol.get("cohorts", {})
        result = {}

        if "target" in cohorts_def:
            result["target"] = self.build_cohort(cohorts_def["target"])

        if "comparator" in cohorts_def:
            result["comparator"] = self.build_cohort(cohorts_def["comparator"])

        if "outcomes" in cohorts_def:
            result["outcomes"] = []
            for outcome_def in cohorts_def["outcomes"]:
                result["outcomes"].append(self.build_cohort(outcome_def))

        return result

    def save_cohorts(self, cohorts: dict, output_dir: str) -> dict:
        """생성된 코호트 JSON을 파일로 저장

        Returns:
            {role: file_path} 매핑
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = {}

        if "target" in cohorts:
            p = out / "target.json"
            self._save_json(cohorts["target"], p)
            paths["target"] = str(p)

        if "comparator" in cohorts:
            p = out / "comparator.json"
            self._save_json(cohorts["comparator"], p)
            paths["comparator"] = str(p)

        if "outcomes" in cohorts:
            paths["outcomes"] = []
            for i, oc in enumerate(cohorts["outcomes"]):
                p = out / f"outcome_{i+1}.json"
                self._save_json(oc, p)
                paths["outcomes"].append(str(p))

        return paths

    # ─── Internal builders ─────────────────────────────

    def _next_cs_id(self) -> int:
        cid = self._concept_set_counter
        self._concept_set_counter += 1
        return cid

    def _add_concept_set(self, concept_sets: list, name: str,
                         concepts: list, domain: str) -> int:
        """ConceptSet을 추가하고 ID를 반환"""
        cs_id = self._next_cs_id()
        items = []
        for c in concepts:
            item = self._build_concept_item(c, domain)
            items.append(item)

        concept_sets.append({
            "id": cs_id,
            "name": name,
            "expression": {"items": items},
        })
        return cs_id

    def _build_concept_item(self, concept_def: dict, domain: str) -> dict:
        """개별 concept → ConceptSet item"""
        cfg = DOMAIN_CONFIG.get(domain, DOMAIN_CONFIG["condition"])

        concept_id = concept_def.get("concept_id", 0)
        concept_name = concept_def.get("concept_name", f"Concept {concept_id}")
        vocabulary_id = concept_def.get("vocabulary_id", "SNOMED")
        concept_code = concept_def.get("concept_code", str(concept_id))
        domain_id = concept_def.get("domain_id", cfg["domain_id"])
        concept_class_id = concept_def.get("concept_class_id", cfg["concept_class_default"])

        return {
            "concept": {
                "CONCEPT_ID": concept_id,
                "CONCEPT_NAME": concept_name,
                "CONCEPT_CODE": concept_code,
                "VOCABULARY_ID": vocabulary_id,
                "DOMAIN_ID": domain_id,
                "CONCEPT_CLASS_ID": concept_class_id,
                "STANDARD_CONCEPT": "S",
                "STANDARD_CONCEPT_CAPTION": "Standard",
                "INVALID_REASON": "V",
                "INVALID_REASON_CAPTION": "Valid",
            },
            "isExcluded": concept_def.get("is_excluded", False),
            "includeDescendants": concept_def.get("include_descendants", True),
            "includeMapped": concept_def.get("include_mapped", False),
        }

    def _build_domain_criteria(self, domain: str, codeset_id: int,
                                visit_type: str = None) -> dict:
        """도메인별 PrimaryCriteria 구성"""
        cfg = DOMAIN_CONFIG[domain]
        key = cfg["criteria_key"]

        criteria = {
            "CodesetId": codeset_id,
            "CorrelatedCriteria": None,
            cfg["type_exclude_key"]: False,
            cfg["source_concept_key"]: None,
            "ProviderSpecialty": None,
            "Gender": None,
            "VisitType": None,
            "First": None,
            "OccurrenceStartDate": None,
            "Age": None,
        }
        criteria.update(cfg["extra_fields"])

        # 방문 유형 필터
        if visit_type and visit_type.lower() in VISIT_TYPE_MAP:
            criteria["VisitType"] = [VISIT_TYPE_MAP[visit_type.lower()]]

        return {key: criteria}

    def _build_inclusion_rule(self, rule_def: dict, concept_sets: list,
                               parent_domain: str) -> Optional[dict]:
        """InclusionRule 하나 생성"""
        rule_type = rule_def.get("type", "")
        name = rule_def.get("name", "Unnamed rule")

        if rule_type == "demographic":
            return self._build_demographic_rule(name, rule_def)
        elif rule_type == "exclusion":
            return self._build_exclusion_rule(name, rule_def, concept_sets)
        elif rule_type == "measurement":
            return self._build_measurement_rule(name, rule_def, concept_sets)
        elif rule_type == "occurrence":
            return self._build_occurrence_rule(name, rule_def, concept_sets)
        else:
            return None

    def _build_demographic_rule(self, name: str, rule_def: dict) -> dict:
        """연령/성별 필터"""
        demo = {}
        if "age" in rule_def:
            demo["Age"] = {
                "Op": rule_def["age"]["op"],
                "Value": rule_def["age"]["value"],
                "Extent": rule_def["age"].get("extent"),
            }
        if "gender" in rule_def:
            gender_concepts = []
            for g in (rule_def["gender"] if isinstance(rule_def["gender"], list)
                      else [rule_def["gender"]]):
                gmap = {"male": 8507, "female": 8532}
                cid = gmap.get(g.lower(), g)
                gender_concepts.append({"CONCEPT_ID": cid, "CONCEPT_CODE": "", "CONCEPT_NAME": g})
            demo["Gender"] = gender_concepts

        # 미지정 필드 null
        for k in ["Ethnicity", "OccurrenceEndDate", "Race", "OccurrenceStartDate"]:
            demo.setdefault(k, None)
        demo.setdefault("Gender", None)
        demo.setdefault("Age", None)

        return {
            "name": name,
            "description": None,
            "expression": {
                "Type": "ALL",
                "CriteriaList": [],
                "DemographicCriteriaList": [demo],
                "Groups": [],
                "Count": None,
            },
        }

    def _build_exclusion_rule(self, name: str, rule_def: dict,
                               concept_sets: list) -> dict:
        """특정 이벤트가 없어야 하는 배제 기준"""
        domain = rule_def.get("domain", "condition")
        cs_id = self._add_concept_set(
            concept_sets, f"[Excl] {name}", rule_def["concepts"], domain
        )

        window = rule_def.get("window", {"start": None, "end": 0})
        start_days = window.get("start")
        end_days = window.get("end", 0)

        start_window = {
            "Start": {
                "Days": abs(start_days) if start_days is not None else None,
                "Coeff": -1,
            },
            "End": {
                "Days": abs(end_days) if end_days is not None else 0,
                "Coeff": 1 if (end_days is not None and end_days >= 0) else -1,
            },
            "UseEventEnd": False,
            "UseIndexEnd": False,
        }

        # 배제: Occurrence Type=0 (exactly), Count=0
        criteria_key = DOMAIN_CONFIG[domain]["criteria_key"]
        criteria = {criteria_key: {"CodesetId": cs_id}}

        return {
            "name": name,
            "description": None,
            "expression": {
                "Type": "ALL",
                "CriteriaList": [{
                    "Criteria": criteria,
                    "StartWindow": start_window,
                    "EndWindow": None,
                    "RestrictVisit": rule_def.get("restrict_visit", False),
                    "IgnoreObservationPeriod": False,
                    "Occurrence": {"Type": 0, "Count": 0, "IsDistinct": False, "CountColumn": None},
                }],
                "DemographicCriteriaList": [],
                "Groups": [],
                "Count": None,
            },
        }

    def _build_measurement_rule(self, name: str, rule_def: dict,
                                 concept_sets: list) -> dict:
        """검사 값 기반 포함 기준"""
        cs_id = self._add_concept_set(
            concept_sets, f"[Meas] {name}", rule_def["concepts"], "measurement"
        )

        window = rule_def.get("window", {"start": -30, "end": 30})
        value_def = rule_def.get("value", {})

        measurement_criteria = {
            "Measurement": {
                "CodesetId": cs_id,
                "MeasurementTypeExclude": False,
                "MeasurementSourceConcept": None,
                "CorrelatedCriteria": None,
                "ProviderSpecialty": None,
                "Gender": None,
                "VisitType": None,
                "First": None,
                "OccurrenceStartDate": None,
                "OccurrenceEndDate": None,
                "MeasurementType": None,
                "Operator": None,
                "ValueAsNumber": {
                    "Op": value_def.get("op", "gte"),
                    "Value": value_def.get("value", 0),
                    "Extent": value_def.get("extent"),
                } if value_def else None,
                "ValueAsConcept": None,
                "Unit": None,
                "RangeLow": None,
                "RangeHigh": None,
                "RangeLowOperator": None,
                "RangeHighOperator": None,
                "RangeLowRatio": None,
                "RangeHighRatio": None,
                "Abnormal": None,
                "Age": None,
            }
        }

        rule_expression_type = rule_def.get("logic", "ANY")

        return {
            "name": name,
            "description": None,
            "expression": {
                "Type": rule_expression_type,
                "CriteriaList": [{
                    "Criteria": measurement_criteria,
                    "StartWindow": {
                        "Start": {"Days": abs(window["start"]), "Coeff": -1},
                        "End": {"Days": abs(window["end"]), "Coeff": 1},
                        "UseEventEnd": False,
                        "UseIndexEnd": False,
                    },
                    "EndWindow": None,
                    "RestrictVisit": False,
                    "IgnoreObservationPeriod": False,
                    "Occurrence": {"Type": 2, "Count": 1, "IsDistinct": False, "CountColumn": None},
                }],
                "DemographicCriteriaList": [],
                "Groups": [],
                "Count": None,
            },
        }

    def _build_occurrence_rule(self, name: str, rule_def: dict,
                                concept_sets: list) -> dict:
        """특정 이벤트가 있어야 하는 포함 기준 (at least N occurrences)"""
        domain = rule_def.get("domain", "condition")
        cs_id = self._add_concept_set(
            concept_sets, f"[Req] {name}", rule_def["concepts"], domain
        )

        window = rule_def.get("window", {"start": None, "end": 0})
        min_count = rule_def.get("min_count", 1)

        criteria_key = DOMAIN_CONFIG[domain]["criteria_key"]
        criteria = {criteria_key: {"CodesetId": cs_id}}

        start_days = window.get("start")
        end_days = window.get("end", 0)

        return {
            "name": name,
            "description": None,
            "expression": {
                "Type": "ALL",
                "CriteriaList": [{
                    "Criteria": criteria,
                    "StartWindow": {
                        "Start": {
                            "Days": abs(start_days) if start_days is not None else None,
                            "Coeff": -1,
                        },
                        "End": {
                            "Days": abs(end_days) if end_days is not None else 0,
                            "Coeff": 1 if (end_days is not None and end_days >= 0) else -1,
                        },
                        "UseEventEnd": False,
                        "UseIndexEnd": False,
                    },
                    "EndWindow": None,
                    "RestrictVisit": False,
                    "IgnoreObservationPeriod": False,
                    "Occurrence": {"Type": 2, "Count": min_count, "IsDistinct": False, "CountColumn": None},
                }],
                "DemographicCriteriaList": [],
                "Groups": [],
                "Count": None,
            },
        }

    def _build_end_strategy(self, end_def: dict, concept_sets: list) -> dict:
        """EndStrategy 생성"""
        strategy_type = end_def.get("type", "fixed_offset")

        if strategy_type == "fixed_offset":
            return {
                "DateOffset": {
                    "DateField": end_def.get("date_field", "StartDate"),
                    "Offset": end_def.get("days", 0),
                }
            }
        elif strategy_type == "drug_era":
            cs_id = self._add_concept_set(
                concept_sets, "[EndStrategy] Drug Era",
                end_def.get("concepts", []), "drug"
            )
            return {
                "CustomEra": {
                    "DrugCodesetId": cs_id,
                    "GapDays": end_def.get("gap_days", 30),
                    "Offset": end_def.get("offset", 0),
                }
            }
        return {}

    @staticmethod
    def _save_json(data: dict, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
