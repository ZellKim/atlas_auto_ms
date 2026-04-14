"""
Cohort Frequency Validator
===========================
연구 시작 전 코호트 정의의 다기관 frequency를 자동 확인합니다.

Usage:
    from atlas_auto.cohort_validator import validate_cohorts

    results = validate_cohorts(
        config_path="config.yaml",
        cohort_definitions=[
            {"name": "Appendectomy", "concept_id": 4198190, "domain": "procedure"},
            {"name": "WBC > 11", "concept_id": 3010813, "domain": "measurement",
             "value": {"Op": "gt", "Value": 11}},
        ],
        min_target_n=1000,
    )
"""

import json
import logging
import time

logger = logging.getLogger(__name__)


def create_simple_cohort_json(concept_id, domain="condition", include_descendants=True,
                               value_as_number=None, observation_prior=365):
    """간단한 코호트 정의 JSON 생성"""
    domain_map = {
        "condition": "ConditionOccurrence",
        "procedure": "ProcedureOccurrence",
        "drug": "DrugExposure",
        "measurement": "Measurement",
        "observation": "Observation",
    }

    criteria_key = domain_map.get(domain.lower(), "ConditionOccurrence")

    criteria = {
        criteria_key: {
            "CodesetId": 0,
            "First": None,
            "OccurrenceStartDate": None,
        }
    }

    if value_as_number and criteria_key == "Measurement":
        criteria["Measurement"]["ValueAsNumber"] = value_as_number

    expression = {
        "cdmVersionRange": ">=5.0.0",
        "PrimaryCriteria": {
            "CriteriaList": [{"Criteria": criteria}] if criteria_key != "Criteria" else [],
            "ObservationWindow": {
                "PriorDays": observation_prior,
                "PostDays": 0,
            },
            "PrimaryCriteriaLimit": {"Type": "First"},
        },
        "ConceptSets": [
            {
                "id": 0,
                "name": f"concept_{concept_id}",
                "expression": {
                    "items": [
                        {
                            "concept": {
                                "CONCEPT_ID": concept_id,
                                "STANDARD_CONCEPT": "S",
                                "STANDARD_CONCEPT_CAPTION": "Standard",
                                "INVALID_REASON": "V",
                                "INVALID_REASON_CAPTION": "Valid",
                                "DOMAIN_ID": domain.capitalize(),
                            },
                            "isExcluded": False,
                            "includeDescendants": include_descendants,
                            "includeMapped": False,
                        }
                    ]
                },
            }
        ],
        "QualifiedLimit": {"Type": "First"},
        "ExpressionLimit": {"Type": "First"},
        "InclusionRules": [],
        "CensoringCriteria": [],
        "CollapseSettings": {"CollapseType": "ERA", "EraPad": 0},
        "CensorWindow": {},
    }

    # Fix: PrimaryCriteria needs the right structure
    expression["PrimaryCriteria"]["CriteriaList"] = [criteria]

    return expression


def validate_cohorts_on_site(client, cohort_definitions, source_key=None,
                              cleanup=True, timeout=600):
    """단일 기관에서 코호트 frequency 확인

    Args:
        client: FedernetClient (connect_site 완료 상태)
        cohort_definitions: [{name, concept_id, domain, value, ...}, ...]
        source_key: CDM source key (None이면 자동)
        cleanup: 테스트 코호트 삭제 여부
        timeout: Generate 대기 시간 (초)

    Returns:
        [{name, concept_id, cohort_id, person_count, record_count, status}, ...]
    """
    if source_key is None:
        source_key = client.get_source_key()

    results = []

    for cohort_def in cohort_definitions:
        name = cohort_def["name"]
        concept_id = cohort_def["concept_id"]
        domain = cohort_def.get("domain", "condition")
        value = cohort_def.get("value", None)
        include_desc = cohort_def.get("include_descendants", True)

        # 코호트 생성
        expression = create_simple_cohort_json(
            concept_id, domain, include_desc, value
        )

        try:
            cohort = client.create_cohort_definition(
                name=f"[VALIDATE] {name}",
                expression=expression,
            )
            cohort_id = cohort["id"]
            logger.info(f"Created cohort {cohort_id}: {name}")
        except Exception as e:
            logger.error(f"Failed to create cohort {name}: {e}")
            results.append({
                "name": name, "concept_id": concept_id,
                "cohort_id": None, "person_count": 0,
                "status": f"CREATE_FAILED: {e}",
            })
            continue

        # Generate
        try:
            client.generate_cohort(cohort_id, source_key)
            success = client.wait_for_cohort_generation(
                cohort_id, source_key, timeout=timeout, poll_interval=10
            )

            if success:
                # N수 확인
                infos = client.get_cohort_generation_info(cohort_id)
                person_count = 0
                for info in infos:
                    pc = info.get("personCount", 0)
                    if pc and pc > 0:
                        person_count = pc
                        break

                results.append({
                    "name": name, "concept_id": concept_id,
                    "cohort_id": cohort_id, "person_count": person_count,
                    "status": "OK" if person_count > 0 else "EMPTY",
                })
                logger.info(f"  {name}: N={person_count}")
            else:
                results.append({
                    "name": name, "concept_id": concept_id,
                    "cohort_id": cohort_id, "person_count": 0,
                    "status": "GENERATE_FAILED",
                })
        except Exception as e:
            results.append({
                "name": name, "concept_id": concept_id,
                "cohort_id": cohort_id, "person_count": 0,
                "status": f"ERROR: {e}",
            })

        # 정리
        if cleanup and cohort_id:
            try:
                client.session.delete(
                    f"{client.webapi_url}/cohortdefinition/{cohort_id}")
            except Exception:
                pass

    return results


def validate_cohorts_multisite(client, cohort_definitions, sites,
                                cleanup=True, timeout=600):
    """다기관에서 코호트 frequency 확인

    Args:
        client: FedernetClient (portal 로그인 완료)
        cohort_definitions: [{name, concept_id, domain, ...}, ...]
        sites: [(group_id, site_id, site_name), ...]
        cleanup: 테스트 코호트 삭제
        timeout: 기관당 Generate 대기 시간

    Returns:
        {site_name: [{name, concept_id, person_count, status}, ...]}
    """
    all_results = {}

    for group_id, site_id, site_name in sites:
        logger.info(f"\n=== {site_name} (group={group_id}, site={site_id}) ===")
        try:
            client.connect_site(group_id, site_id)
            results = validate_cohorts_on_site(
                client, cohort_definitions,
                cleanup=cleanup, timeout=timeout,
            )
            all_results[site_name] = results
        except Exception as e:
            logger.error(f"  {site_name}: {e}")
            all_results[site_name] = [{"status": f"SITE_ERROR: {e}"}]

    return all_results


def print_validation_report(all_results, min_n=100):
    """검증 결과 리포트 출력"""
    # 코호트별 × 기관별 매트릭스
    sites = list(all_results.keys())
    if not sites:
        print("No results")
        return

    cohort_names = []
    for results in all_results.values():
        for r in results:
            if r.get("name") and r["name"] not in cohort_names:
                cohort_names.append(r["name"])

    # Header
    header = f"{'Cohort':<25}"
    for site in sites:
        header += f" {site[:10]:>10}"
    header += "  Status"
    print(header)
    print("-" * len(header))

    # Rows
    for cname in cohort_names:
        row = f"{cname:<25}"
        counts = []
        for site in sites:
            n = 0
            for r in all_results[site]:
                if r.get("name") == cname:
                    n = r.get("person_count", 0)
                    break
            counts.append(n)
            row += f" {n:>10,}"

        # 판정
        all_ok = all(c >= min_n for c in counts if c > 0)
        any_zero = any(c == 0 for c in counts)
        if any_zero:
            row += "  ⚠️ 일부 기관 0"
        elif not all_ok:
            row += f"  ⚠️ min_n({min_n}) 미달"
        else:
            row += "  ✅"

        print(row)
