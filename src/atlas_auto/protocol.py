"""
Study Protocol Orchestrator
============================
연구설계 YAML 하나로 전체 파이프라인 실행:
  프로토콜 로드 → 코호트 JSON 생성 → ATLAS 업로드 → Generate
  → Estimation 설계 → Import → 실행 → 결과 다운로드

Usage:
    from atlas_auto import StudyProtocol
    protocol = StudyProtocol.from_yaml("my_study.yaml")
    protocol.run(config_path="config.yaml")
"""

import json
import logging
from pathlib import Path

import yaml

from atlas_auto.client import FedernetClient
from atlas_auto.builder import EstimationBuilder
from atlas_auto.cohort_designer import CohortDesigner

logger = logging.getLogger(__name__)


class StudyProtocol:
    """연구설계 프로토콜 → 전체 파이프라인 오케스트레이터"""

    def __init__(self, protocol: dict):
        self.protocol = protocol
        self.study = protocol.get("study", {})
        self.cohorts_def = protocol.get("cohorts", {})
        self.analysis_def = protocol.get("analysis", {})
        self.execution_def = protocol.get("execution", {})

        self.designer = CohortDesigner()
        self._cohort_jsons = {}     # role -> CIRCE JSON
        self._cohort_files = {}     # role -> file path
        self._cohort_id_map = {}    # local_idx -> remote ATLAS ID

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "StudyProtocol":
        with open(yaml_path, "r", encoding="utf-8") as f:
            protocol = yaml.safe_load(f)
        return cls(protocol)

    @classmethod
    def from_dict(cls, protocol: dict) -> "StudyProtocol":
        return cls(protocol)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 1: 코호트 JSON 생성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def generate_cohort_jsons(self, output_dir: str = None) -> dict:
        """프로토콜에서 CIRCE JSON 생성

        Returns:
            {"target": circe_dict, "comparator": circe_dict, "outcomes": [circe_dict, ...]}
        """
        logger.info("=== Step 1: 코호트 JSON 생성 ===")
        self._cohort_jsons = self.designer.build_cohorts_from_protocol(self.protocol)

        if output_dir:
            self._cohort_files = self.designer.save_cohorts(self._cohort_jsons, output_dir)
            logger.info(f"코호트 JSON 저장: {output_dir}")
            for role, path in self._cohort_files.items():
                if isinstance(path, list):
                    for p in path:
                        logger.info(f"  {p}")
                else:
                    logger.info(f"  {role}: {path}")

        count = 1 + (1 if "comparator" in self._cohort_jsons else 0) + \
                len(self._cohort_jsons.get("outcomes", []))
        logger.info(f"총 {count}개 코호트 JSON 생성 완료")
        return self._cohort_jsons

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 2: Estimation 스펙 생성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def build_estimation_spec(self) -> dict:
        """코호트 + 분석 설정으로 Estimation 스펙 생성"""
        logger.info("=== Step 2: Estimation 스펙 생성 ===")

        if not self._cohort_jsons:
            self.generate_cohort_jsons()

        name = self.study.get("name", "Auto Study")
        desc = self.study.get("description", "")
        builder = EstimationBuilder(name, desc)

        # 코호트 등록 (임시 ID 부여)
        idx = 1
        cohort_roles = {}  # role_key -> temp_id

        if "target" in self._cohort_jsons:
            target_name = self.cohorts_def.get("target", {}).get("name", "Target")
            builder.add_cohort_definition(idx, target_name, self._cohort_jsons["target"])
            cohort_roles["target"] = idx
            idx += 1

        if "comparator" in self._cohort_jsons:
            comp_name = self.cohorts_def.get("comparator", {}).get("name", "Comparator")
            builder.add_cohort_definition(idx, comp_name, self._cohort_jsons["comparator"])
            cohort_roles["comparator"] = idx
            idx += 1

        outcome_ids = []
        for i, oc_json in enumerate(self._cohort_jsons.get("outcomes", [])):
            oc_defs = self.cohorts_def.get("outcomes", [])
            oc_name = oc_defs[i].get("name", f"Outcome {i+1}") if i < len(oc_defs) else f"Outcome {i+1}"
            builder.add_cohort_definition(idx, oc_name, oc_json)
            outcome_ids.append(idx)
            idx += 1

        # TCO 설정
        if "target" in cohort_roles and "comparator" in cohort_roles and outcome_ids:
            builder.add_target_comparator_outcomes(
                target_id=cohort_roles["target"],
                comparator_id=cohort_roles["comparator"],
                outcome_ids=outcome_ids,
            )
        else:
            # TCO 없이 진행하면 빈 estimation 스펙이 조용히 생성됨 → 명시적 경고.
            missing = [k for k in ("target", "comparator") if k not in cohort_roles]
            if not outcome_ids:
                missing.append("outcomes")
            logger.warning(
                f"TCO 미생성 — 코호트 역할 누락: {missing}. "
                f"estimation 스펙에 targetComparatorOutcomes가 비게 됩니다(실행 시 무의미)."
            )

        # 분석 메서드 설정
        for method_def in self.analysis_def.get("methods", []):
            rw = method_def.get("risk_window", {})
            builder.add_cm_analysis(
                analysis_id=method_def.get("id", 1),
                description=method_def.get("description", ""),
                ps_method=method_def.get("ps_method", "stratify"),
                stratify_num_strata=method_def.get("ps_strata", 5),
                match_max_ratio=method_def.get("match_ratio", 1),
                match_caliper=method_def.get("match_caliper", 0.2),
                model_type=method_def.get("model", "cox"),
                stratified_cox=method_def.get("stratified_cox", True),
                risk_window_start=rw.get("start", 1),
                risk_window_end=rw.get("end", 0),
                add_exposure_days_to_end=rw.get("add_exposure_days", True),
                remove_prior_outcome=method_def.get("remove_prior_outcome", True),
                restrict_to_common_period=method_def.get("restrict_to_common_period", True),
            )

        spec = builder.build()
        logger.info(f"Estimation 스펙: TCO {len(spec['estimationAnalysisSettings']['analysisSpecification']['targetComparatorOutcomes'])}개, "
                     f"Analysis {len(spec['estimationAnalysisSettings']['analysisSpecification']['cohortMethodAnalysisList'])}개")
        return spec

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Step 3-6: ATLAS 업로드 → 실행 → 다운로드
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def run(self, config_path: str = None, client: FedernetClient = None,
            output_dir: str = None, dry_run: bool = False) -> dict:
        """전체 파이프라인 실행

        Args:
            config_path: config.yaml 경로 (client 미제공 시 사용)
            client: 이미 로그인된 FedernetClient (제공 시 config 무시)
            output_dir: 결과 저장 디렉토리
            dry_run: True이면 JSON 생성만 하고 ATLAS 실행은 건너뜀
        Returns:
            실행 결과 dict
        """
        output_dir = output_dir or self.execution_def.get("output_dir", "./output")
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Step 1: 코호트 JSON 생성
        self.generate_cohort_jsons(str(out / "cohorts"))

        # Step 2: Estimation 스펙 생성
        estimation_spec = self.build_estimation_spec()

        # 스펙 저장
        spec_path = out / "estimation_spec.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(estimation_spec, f, indent=2, ensure_ascii=False)
        logger.info(f"Estimation 스펙 저장: {spec_path}")

        if dry_run:
            logger.info("=== Dry run 완료 (ATLAS 실행 건너뜀) ===")
            return {
                "status": "dry_run",
                "cohort_jsons": str(out / "cohorts"),
                "estimation_spec": str(spec_path),
            }

        # Step 3: ATLAS 로그인
        if not client:
            if not config_path:
                config_path = self.execution_def.get("config", "config.yaml")
            client = self._create_client(config_path)

        # Step 4: 코호트 업로드 & Generate
        logger.info("=== Step 3: 코호트 업로드 & Generate ===")
        source_key = client.get_source_key()
        cohort_id_map = {}
        idx = 1

        for role in ["target", "comparator"]:
            if role in self._cohort_jsons:
                name = self.cohorts_def.get(role, {}).get("name", role)
                result = client.create_cohort_definition(f"[Auto] {name}", self._cohort_jsons[role])
                remote_id = result["id"]
                cohort_id_map[idx] = remote_id
                logger.info(f"  {role}: local_id={idx} → remote_id={remote_id}")
                client.generate_cohort(remote_id, source_key)
                idx += 1

        for i, oc_json in enumerate(self._cohort_jsons.get("outcomes", [])):
            oc_name = self.cohorts_def.get("outcomes", [{}])[i].get("name", f"Outcome {i+1}") \
                      if i < len(self.cohorts_def.get("outcomes", [])) else f"Outcome {i+1}"
            result = client.create_cohort_definition(f"[Auto] {oc_name}", oc_json)
            remote_id = result["id"]
            cohort_id_map[idx] = remote_id
            logger.info(f"  outcome_{i+1}: local_id={idx} → remote_id={remote_id}")
            client.generate_cohort(remote_id, source_key)
            idx += 1

        # Generate 완료 대기
        logger.info("코호트 Generate 완료 대기...")
        for local_id, remote_id in cohort_id_map.items():
            ok = client.wait_for_cohort_generation(remote_id, source_key, timeout=600)
            if not ok:
                logger.error(f"코호트 {remote_id} Generate 실패")
                return {"status": "cohort_generation_failed", "cohort_id": remote_id}

        # Step 5: Estimation ID 매핑 → Import → 실행
        logger.info("=== Step 4: Estimation 실행 ===")
        import copy
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

        est_result = client.import_estimation(remote_spec)
        est_id = est_result["id"]
        logger.info(f"Estimation Import: ID={est_id}")

        client.run_estimation(est_id, source_key)

        # Step 6: 완료 대기 & 결과 다운로드
        logger.info("=== Step 5: 실행 완료 대기 ===")
        gen_info = client.wait_for_estimation(est_id, timeout=3600)
        status = gen_info.get("status", {}).get("name", "UNKNOWN") if gen_info else "TIMEOUT"

        result = {
            "status": status,
            "estimation_id": est_id,
            "cohort_id_map": cohort_id_map,
            "output_dir": str(out),
        }

        if status == "COMPLETE" and self.execution_def.get("auto_download", True):
            logger.info("=== Step 6: 결과 다운로드 ===")
            gen_id = gen_info["id"]
            dl_path = str(out / f"estimation_results_{gen_id}.zip")
            try:
                client.download_estimation_results(gen_id, dl_path)
                result["result_file"] = dl_path
            except Exception as e:
                logger.warning(f"결과 다운로드 실패: {e}")

        logger.info(f"=== 파이프라인 완료: {status} ===")
        return result

    def _create_client(self, config_path: str) -> FedernetClient:
        """config.yaml에서 클라이언트 생성 & 로그인"""
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        portal = config.get("portal", {})
        client = FedernetClient(portal.get("url"))

        if portal.get("bearer_token"):
            client.login_with_bearer_token(portal["bearer_token"])
        elif portal.get("cookie_string"):
            client.login_with_cookie_string(portal["cookie_string"])
        elif portal.get("email") and portal.get("password"):
            client.login_portal(portal["email"], portal["password"])

        # 첫 번째 remote_site에 연결
        # ⚠️ StudyProtocol.run() 은 단일 site 파이프라인이다. 다기관 fan-out(본원 R +
        # 여러 타기관)은 runner.run_study() / `atlas-auto run` 을 사용할 것.
        sites = config.get("remote_sites", [])
        if len(sites) > 1:
            logger.warning(
                f"remote_sites {len(sites)}개가 설정됐으나 StudyProtocol.run()은 "
                f"첫 번째({sites[0].get('name', sites[0].get('group_id'))})만 실행합니다. "
                f"다기관 실행은 runner.run_study() 또는 `atlas-auto run` 사용."
            )
        if sites:
            site = sites[0]
            client.connect_site(site.get("group_id"), site.get("site_id"))

        return client

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 유틸리티
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def summary(self) -> str:
        """프로토콜 요약 출력"""
        lines = []
        lines.append(f"Study: {self.study.get('name', '?')}")
        lines.append(f"Description: {self.study.get('description', '')}")
        lines.append(f"Type: {self.study.get('type', '?')}")
        lines.append("")

        if "target" in self.cohorts_def:
            t = self.cohorts_def["target"]
            concepts = t.get("concepts", [])
            lines.append(f"Target: {t.get('name', '?')} ({t.get('domain', '?')}, "
                         f"concepts: {[c.get('concept_id') for c in concepts]})")

        if "comparator" in self.cohorts_def:
            c = self.cohorts_def["comparator"]
            concepts = c.get("concepts", [])
            lines.append(f"Comparator: {c.get('name', '?')} ({c.get('domain', '?')}, "
                         f"concepts: {[c2.get('concept_id') for c2 in concepts]})")

        outcomes = self.cohorts_def.get("outcomes", [])
        for i, o in enumerate(outcomes):
            concepts = o.get("concepts", [])
            lines.append(f"Outcome {i+1}: {o.get('name', '?')} ({o.get('domain', '?')}, "
                         f"concepts: {[c.get('concept_id') for c in concepts]})")

        lines.append("")
        methods = self.analysis_def.get("methods", [])
        for m in methods:
            lines.append(f"Analysis {m.get('id', '?')}: {m.get('description', '?')} "
                         f"(ps={m.get('ps_method', '?')}, model={m.get('model', '?')})")

        return "\n".join(lines)
