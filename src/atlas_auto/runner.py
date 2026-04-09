"""
Multi-site Study Runner
=======================
본원 (R 직접 실행) + 타기관 (WebAPI) 통합 실행 로직
"""

import copy
import json
import subprocess
import logging
from pathlib import Path

import yaml

from atlas_auto.client import FedernetClient
from atlas_auto.builder import EstimationBuilder

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """YAML 설정 파일 로드"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_local_r_study(config: dict, study_package_dir: str) -> int:
    """본원 CDM에서 R 패키지 직접 실행

    Args:
        config: local_site 설정이 포함된 config dict
        study_package_dir: R study 패키지 디렉토리
    Returns:
        Rscript 종료 코드 (0=성공)
    """
    local = config["local_site"]

    r_script = f"""
library(DatabaseConnector)

connectionDetails <- createConnectionDetails(
    dbms = "{local['dbms']}",
    server = "{local['server']}",
    user = "{local['user']}",
    password = "{local['password']}",
    port = {local.get('port', 5432)}
)

library(evidnet)

execute(
    connectionDetails = connectionDetails,
    cdmDatabaseSchema = "{local['cdm_schema']}",
    cohortDatabaseSchema = "{local['cohort_schema']}",
    cohortTable = "{local.get('cohort_table', 'cohort')}",
    tempEmulationSchema = {f'"{local["temp_schema"]}"' if local.get('temp_schema') else 'NULL'},
    outputFolder = "{local['output_folder']}",
    databaseId = "{local['database_id']}",
    databaseName = "{local['database_name']}",
    databaseDescription = "{local.get('database_description', '')}",
    createCohorts = TRUE,
    synthesizePositiveControls = FALSE,
    runAnalyses = TRUE,
    packageResults = TRUE,
    maxCores = {local.get('max_cores', 4)},
    minCellCount = {local.get('min_cell_count', 5)}
)
"""
    r_script_path = Path(config.get("work_dir", ".")) / "run_local.R"
    r_script_path.parent.mkdir(parents=True, exist_ok=True)
    r_script_path.write_text(r_script, encoding="utf-8")

    logger.info("본원 R 스크립트 실행 시작...")
    result = subprocess.run(
        ["Rscript", str(r_script_path)],
        capture_output=True, text=True, timeout=7200,
    )
    if result.returncode == 0:
        logger.info("본원 분석 완료")
    else:
        logger.error(f"본원 분석 실패:\n{result.stderr}")
    return result.returncode


def run_remote_site(client: FedernetClient, site_config: dict,
                    estimation_spec: dict, cohort_jsons: dict) -> dict:
    """단일 타기관에서 WebAPI를 통해 연구 실행

    Args:
        client: 포탈 로그인 완료된 FedernetClient
        site_config: 기관별 설정 (group_id, site_id 등)
        estimation_spec: Estimation JSON 스펙
        cohort_jsons: {cohort_id: json_expression} 맵
    Returns:
        실행 결과 dict
    """
    site_name = site_config.get("name", "Unknown")
    logger.info(f"=== {site_name} 원격 실행 시작 ===")

    # 1. 기관 ATLAS 연결
    group_id = site_config.get("group_id")
    site_id = site_config.get("site_id")
    atlas_url = site_config.get("atlas_url")

    if group_id and site_id:
        connected = client.connect_site(group_id, site_id)
    elif atlas_url:
        connected = client.connect_site(atlas_url=atlas_url)
    else:
        logger.error(f"{site_name}: group_id/site_id 또는 atlas_url 필요")
        return {"site": site_name, "status": "config_error"}

    if not connected:
        return {"site": site_name, "status": "connection_failed"}

    # 2. 데이터 소스 확인
    source_key = client.get_source_key(site_config.get("source_name"))
    logger.info(f"{site_name}: 데이터 소스 = {source_key}")

    # 3. 코호트 생성 또는 재사용
    cohort_id_map = {}
    if site_config.get("reuse_existing_cohorts"):
        cohort_id_map = site_config.get("cohort_id_mapping", {})
        logger.info(f"{site_name}: 기존 코호트 재사용 (매핑: {cohort_id_map})")
    else:
        for local_id, expression in cohort_jsons.items():
            cohort_name = f"[Auto] Cohort {local_id}"
            for cd in estimation_spec.get("cohortDefinitions", []):
                if cd["id"] == local_id:
                    cohort_name = cd["name"]
                    break
            try:
                result = client.create_cohort_definition(cohort_name, expression)
                cohort_id_map[local_id] = result["id"]
                logger.info(f"{site_name}: 코호트 {local_id} -> {result['id']}")
            except Exception as e:
                logger.error(f"{site_name}: 코호트 {local_id} 생성 실패: {e}")
                return {"site": site_name, "status": "cohort_creation_failed", "error": str(e)}

    # 4. 코호트 Generate
    for local_id, remote_id in cohort_id_map.items():
        try:
            client.generate_cohort(remote_id, source_key)
        except Exception as e:
            logger.error(f"{site_name}: 코호트 {remote_id} Generate 실패: {e}")

    all_generated = True
    for local_id, remote_id in cohort_id_map.items():
        if not client.wait_for_cohort_generation(remote_id, source_key, timeout=600):
            all_generated = False

    if not all_generated:
        return {"site": site_name, "status": "cohort_generation_failed"}

    # 5. Estimation 스펙 ID 매핑
    remote_spec = copy.deepcopy(estimation_spec)
    for cd in remote_spec.get("cohortDefinitions", []):
        if cd["id"] in cohort_id_map:
            cd["id"] = cohort_id_map[cd["id"]]

    for tco in remote_spec.get("estimationAnalysisSettings", {}).get(
        "analysisSpecification", {}
    ).get("targetComparatorOutcomes", []):
        if tco["targetId"] in cohort_id_map:
            tco["targetId"] = cohort_id_map[tco["targetId"]]
        if tco["comparatorId"] in cohort_id_map:
            tco["comparatorId"] = cohort_id_map[tco["comparatorId"]]
        tco["outcomeIds"] = [cohort_id_map.get(oid, oid) for oid in tco["outcomeIds"]]

    # 6. Estimation Import & 실행
    try:
        est_result = client.import_estimation(remote_spec)
        est_id = est_result["id"]
    except Exception as e:
        return {"site": site_name, "status": "estimation_import_failed", "error": str(e)}

    try:
        client.run_estimation(est_id, source_key)
    except Exception as e:
        return {"site": site_name, "status": "estimation_run_failed", "error": str(e)}

    # 7. 완료 대기 & 다운로드
    gen_info = client.wait_for_estimation(est_id, timeout=3600)
    status = gen_info.get("status", {}).get("name", "UNKNOWN") if gen_info else "TIMEOUT"

    if status == "COMPLETE":
        output_dir = Path(site_config.get("output_dir", f"./results/{site_name}"))
        output_dir.mkdir(parents=True, exist_ok=True)
        gen_id = gen_info["id"]
        try:
            client.download_estimation_results(gen_id, str(output_dir / f"estimation_results_{gen_id}.zip"))
        except Exception as e:
            logger.warning(f"{site_name}: 결과 다운로드 실패: {e}")

    logger.info(f"=== {site_name} 완료: {status} ===")
    return {
        "site": site_name,
        "status": status,
        "estimation_id": est_id,
        "cohort_id_map": cohort_id_map,
    }


def run_study(config_path: str, sites: str = "all", step: str = "all",
              estimation_spec_path: str = None) -> dict:
    """통합 실행 함수

    Args:
        config_path: config.yaml 경로
        sites: "all", "local_only", "remote_only"
        step: "all", "cohorts", "estimation", "results"
        estimation_spec_path: Estimation JSON 스펙 경로 (없으면 자동 생성)
    Returns:
        기관별 실행 결과 dict
    """
    config = load_config(config_path)
    results = {}

    # Estimation 스펙 준비
    estimation_spec = None
    cohort_jsons = {}

    if estimation_spec_path:
        with open(estimation_spec_path, "r", encoding="utf-8") as f:
            estimation_spec = json.load(f)
    elif config.get("study_package_dir"):
        pkg_dir = config["study_package_dir"]
        builder = EstimationBuilder.from_existing_package(pkg_dir)
        estimation_spec = builder.build()

        work_dir = Path(config.get("work_dir", "."))
        work_dir.mkdir(parents=True, exist_ok=True)
        builder.save(str(work_dir / "estimation_spec_generated.json"))

        cohorts_dir = Path(pkg_dir) / "inst" / "cohorts"
        if cohorts_dir.exists():
            for jf in cohorts_dir.glob("*.json"):
                cid = int(jf.stem)
                with open(jf, "r", encoding="utf-8") as f:
                    cohort_jsons[cid] = json.load(f)

    # 본원 실행
    if sites in ("all", "local_only") and config.get("local_site"):
        pkg_dir = config.get("study_package_dir")
        if pkg_dir:
            rc = run_local_r_study(config, pkg_dir)
            results["local"] = {"status": "success" if rc == 0 else "failed"}

    # 타기관 실행
    if sites in ("all", "remote_only") and config.get("remote_sites"):
        if not estimation_spec:
            raise ValueError("타기관 실행: estimation 스펙 필요")

        portal = config.get("portal", {})
        client = FedernetClient(portal.get("url"))

        if portal.get("bearer_token"):
            client.login_with_bearer_token(portal["bearer_token"])
        elif portal.get("cookie_string"):
            client.login_with_cookie_string(portal["cookie_string"])
        elif portal.get("email") and portal.get("password"):
            client.login_portal(portal["email"], portal["password"])

        for site_config in config["remote_sites"]:
            site_name = site_config.get("name", "Unknown")
            try:
                result = run_remote_site(client, site_config, estimation_spec, cohort_jsons)
                results[site_name] = result
            except Exception as e:
                logger.error(f"{site_name} 오류: {e}")
                results[site_name] = {"status": "error", "error": str(e)}

    return results
