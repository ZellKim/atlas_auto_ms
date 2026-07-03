"""
FEDERnet ATLAS WebAPI Client
=============================
feedernet 포탈 로그인 → 기관별 ATLAS WebAPI 접근을 자동화합니다.

feedernet API 구조:
  포탈 API:    https://www.feedernet.com/api/v1/dashboard/organizations
  기관 WebAPI: https://www.feedernet.com/api/v1/atlas/{group_id}/{site_id}/{endpoint}

  예: ATLAS URL  = /atlas-resolve/v2.12.0/7/203/main#/home
      WebAPI URL = /api/v1/atlas/7/203

Usage:
    from atlas_auto import FedernetClient

    client = FedernetClient()
    client.login_portal("my_id", "my_pw")
    client.connect_site(7, 203)
    sources = client.get_sources()
"""

import re
import json
import time
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# feedernet 포탈 execution 상태 → 요약 버킷 매핑 (캐노니컬).
# data/scripts/v4_phase_e_monitor.py:classify() 및 cloud_monitor/main.py 와 동일 규칙.
# 주의: EXECUTING_PREPARING / SAVING_RESULT_FILES 는 정상 활성 상태이므로 RUNNING 이다.
# (2026-06-21 KB §2.3: 이 두 상태를 FAILED 로 오분류한 버그가 monitor 에서 수정된 이력)
_RUNNING_STATUSES = ("EXECUTING_PREPARING", "EXECUTING_DOCKER", "SAVING_RESULT_FILES", "RUNNING")


def classify_execution_status(status: str) -> str:
    """executionStatus 문자열을 COMPLETE/RUNNING/WAITING/CANCELED/FAILED 로 분류."""
    if status == "FINISHED_SUCCESSFULLY":
        return "COMPLETE"
    if status in _RUNNING_STATUSES:
        return "RUNNING"
    if status == "WAITING":
        return "WAITING"
    if status == "CANCELED":
        return "CANCELED"
    return "FAILED"


class FedernetClient:
    """FEDERnet 포탈 + 기관별 ATLAS WebAPI 클라이언트"""

    PORTAL_URL = "https://www.feedernet.com"

    def __init__(self, portal_url: str = None):
        self.portal_url = (portal_url or self.PORTAL_URL).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FedernetAutomation/1.0",
            "Accept": "application/json, text/html, */*",
        })
        self.webapi_url = None
        self.group_id = None
        self.site_id = None
        self._logged_in = False

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 포탈 로그인
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def login_portal(self, email: str, password: str) -> bool:
        """feedernet 포탈 로그인 (POST /api/v1/auth/login)"""
        logger.info("feedernet 포탈 로그인 시도...")
        url = f"{self.portal_url}/api/v1/auth/login"
        try:
            resp = self.session.post(
                url, json={"email": email, "password": password}, timeout=30,
            )
            if resp.status_code == 200:
                body = resp.json()
                if body.get("result") is True:
                    content = body.get("content", {})
                    self._logged_in = True
                    logger.info(f"포탈 로그인 성공 (user: {content.get('name')}, priv: {content.get('priv')})")
                    return True
                else:
                    logger.error(f"로그인 실패: {body.get('message', 'unknown error')}")
                    return False
            else:
                logger.error(f"로그인 실패 (status={resp.status_code})")
                return False
        except requests.RequestException as e:
            logger.error(f"로그인 요청 실패: {e}")
            return False

    def login_with_cookies(self, cookies: dict) -> bool:
        """브라우저에서 복사한 쿠키로 인증"""
        for name, value in cookies.items():
            self.session.cookies.set(name, value)
        self._logged_in = True
        logger.info(f"쿠키 인증 설정 ({len(cookies)}개)")
        return True

    def login_with_cookie_string(self, cookie_string: str) -> bool:
        """브라우저 Cookie 헤더 문자열로 인증 ("name1=value1; name2=value2; ...")"""
        cookies = {}
        for pair in cookie_string.split(";"):
            pair = pair.strip()
            if "=" in pair:
                name, value = pair.split("=", 1)
                cookies[name.strip()] = value.strip()
        return self.login_with_cookies(cookies)

    def login_with_bearer_token(self, token: str) -> bool:
        """Bearer 토큰 직접 설정"""
        token = token.replace("Bearer ", "").strip()
        self.session.headers["Authorization"] = f"Bearer {token}"
        self._logged_in = True
        logger.info("Bearer 토큰 인증 설정")
        return True

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 기관 사이트 연결
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def connect_site(self, group_id: int = None, site_id: int = None,
                     atlas_url: str = None) -> bool:
        """특정 기관의 ATLAS WebAPI에 연결

        사용법 1: client.connect_site(7, 203)
        사용법 2: client.connect_site(atlas_url="https://www.feedernet.com/atlas-resolve/v2.12.0/7/203/main")
        """
        if atlas_url:
            ids = self.parse_atlas_url(atlas_url)
            if ids:
                group_id = ids["group_id"]
                site_id = ids["site_id"]
            else:
                logger.error(f"ATLAS URL에서 기관 ID를 추출할 수 없습니다: {atlas_url}")
                return False

        if not group_id or not site_id:
            logger.error("group_id와 site_id가 필요합니다")
            return False

        self.group_id = group_id
        self.site_id = site_id
        self.webapi_url = f"{self.portal_url}/api/v1/atlas/{group_id}/{site_id}"

        logger.info(f"기관 연결: group={group_id}, site={site_id}")
        logger.info(f"WebAPI URL: {self.webapi_url}")

        return self.check_connection()

    def list_organizations(self) -> list:
        """feedernet에 등록된 기관 목록 조회"""
        resp = self.session.get(f"{self.portal_url}/api/v1/dashboard/organizations")
        resp.raise_for_status()
        data = resp.json()
        # 포탈 API 는 응답을 {"content": [...]} 로 감싸는 경우가 있어 방어적으로 언랩.
        orgs = data.get("content", data) if isinstance(data, dict) else data
        logger.info(f"기관 목록: {len(orgs)}개")
        return orgs

    @staticmethod
    def parse_atlas_url(atlas_url: str) -> dict:
        """ATLAS URL에서 group_id, site_id 추출"""
        match = re.search(r'/atlas-resolve/(v[\d.]+)/(\d+)/(\d+)', atlas_url)
        if match:
            return {
                "version": match.group(1),
                "group_id": int(match.group(2)),
                "site_id": int(match.group(3)),
            }
        match = re.search(r'/api/v1/atlas/(\d+)/(\d+)', atlas_url)
        if match:
            return {
                "version": None,
                "group_id": int(match.group(1)),
                "site_id": int(match.group(2)),
            }
        return {}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 데이터 소스
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_sources(self) -> list:
        """CDM 데이터 소스 목록"""
        resp = self.session.get(f"{self.webapi_url}/source/sources")
        resp.raise_for_status()
        return resp.json()

    def get_source_key(self, source_name: str = None) -> str:
        """데이터 소스 sourceKey 조회 (None이면 첫 번째 소스)"""
        sources = self.get_sources()
        if not sources:
            raise ValueError("사용 가능한 데이터 소스 없음")
        if source_name:
            for s in sources:
                if s.get("sourceName", "").lower() == source_name.lower() or \
                   s.get("sourceKey", "") == source_name:
                    return s["sourceKey"]
            available = [s.get("sourceName", "?") for s in sources]
            raise ValueError(f"'{source_name}' 소스 없음. 가능: {available}")
        return sources[0]["sourceKey"]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 코호트 정의
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_cohort_definitions(self) -> list:
        """코호트 정의 목록"""
        resp = self.session.get(f"{self.webapi_url}/cohortdefinition")
        resp.raise_for_status()
        return resp.json()

    def get_cohort_definition(self, cohort_id: int) -> dict:
        """코호트 정의 상세"""
        resp = self.session.get(f"{self.webapi_url}/cohortdefinition/{cohort_id}")
        resp.raise_for_status()
        return resp.json()

    def create_cohort_definition(self, name: str, expression: dict, description: str = "") -> dict:
        """코호트 정의 생성"""
        payload = {
            "name": name,
            "description": description,
            "expressionType": "SIMPLE_EXPRESSION",
            "expression": expression,
        }
        resp = self.session.post(f"{self.webapi_url}/cohortdefinition", json=payload)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"코호트 생성: '{name}' (ID: {result.get('id')})")
        return result

    def create_cohort_from_json_file(self, name: str, json_path: str) -> dict:
        """JSON 파일에서 코호트 생성"""
        with open(json_path, "r", encoding="utf-8") as f:
            expression = json.load(f)
        return self.create_cohort_definition(name, expression)

    def generate_cohort(self, cohort_id: int, source_key: str) -> dict:
        """코호트 Generate 시작"""
        url = f"{self.webapi_url}/cohortdefinition/{cohort_id}/generate/{source_key}"
        resp = self.session.get(url)
        resp.raise_for_status()
        logger.info(f"코호트 Generate 시작: ID={cohort_id}")
        return resp.json()

    def get_cohort_generation_info(self, cohort_id: int) -> list:
        """코호트 Generate 상태"""
        resp = self.session.get(f"{self.webapi_url}/cohortdefinition/{cohort_id}/info")
        resp.raise_for_status()
        return resp.json()

    def wait_for_cohort_generation(self, cohort_id: int, source_key: str = None,
                                    timeout: int = 600, poll_interval: int = 10) -> bool:
        """코호트 Generate 완료 대기"""
        start = time.time()
        while time.time() - start < timeout:
            infos = self.get_cohort_generation_info(cohort_id)
            for info in infos:
                status_val = info.get("status", "UNKNOWN")
                if isinstance(status_val, dict):
                    status = status_val.get("name", "UNKNOWN")
                else:
                    status = str(status_val)

                if status == "COMPLETE":
                    person_count = info.get("personCount", "?")
                    logger.info(f"코호트 {cohort_id} Generate 완료 (N={person_count})")
                    return True
                elif status in ("FAILED", "CANCELED"):
                    fail_msg = info.get("failMessage", "")
                    logger.error(f"코호트 {cohort_id}: {status} - {fail_msg}")
                    return False
                else:
                    logger.info(f"코호트 {cohort_id}: {status} ({int(time.time()-start)}s)")
            time.sleep(poll_interval)
        logger.error(f"코호트 {cohort_id} 타임아웃")
        return False

    def get_cohort_report(self, cohort_id: int, source_key: str) -> dict:
        """코호트 Generate 리포트"""
        resp = self.session.get(f"{self.webapi_url}/cohortdefinition/{cohort_id}/report/{source_key}")
        resp.raise_for_status()
        return resp.json()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Estimation
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_estimations(self) -> list:
        resp = self.session.get(f"{self.webapi_url}/estimation/")
        resp.raise_for_status()
        return resp.json()

    def get_estimation(self, estimation_id: int) -> dict:
        resp = self.session.get(f"{self.webapi_url}/estimation/{estimation_id}")
        resp.raise_for_status()
        return resp.json()

    def export_estimation(self, estimation_id: int) -> dict:
        """Estimation 전체 Export"""
        resp = self.session.get(f"{self.webapi_url}/estimation/{estimation_id}/export")
        resp.raise_for_status()
        return resp.json()

    def create_estimation(self, spec: dict) -> dict:
        resp = self.session.post(f"{self.webapi_url}/estimation/", json=spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Estimation 생성: ID={result.get('id')}")
        return result

    def import_estimation(self, full_spec: dict) -> dict:
        """Estimation Import (export JSON 형식)

        ⚠️ 주의: `/estimation/import` 엔드포인트는 endpoints CSV 에서 used_in_project=N
        (프로덕션 미검증)이다. 검증된 프로덕션 등록 방식은
        `GET /estimation/{id}/copy → PUT /estimation/{id}` copy+PUT 패턴이며,
        `data/scripts/v4_phase_b_build.py` 및 KB §1.1 참조. 신규 코드는 그 패턴을 권장.
        """
        resp = self.session.post(f"{self.webapi_url}/estimation/import", json=full_spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Estimation Import: ID={result.get('id')}")
        return result

    def run_estimation(self, estimation_id: int, source_key: str) -> dict:
        """Estimation 실행"""
        url = f"{self.webapi_url}/estimation/{estimation_id}/generation/{source_key}"
        resp = self.session.post(url)
        resp.raise_for_status()
        logger.info(f"Estimation 실행: ID={estimation_id}")
        return resp.json()

    def get_estimation_generations(self, estimation_id: int) -> list:
        resp = self.session.get(f"{self.webapi_url}/estimation/{estimation_id}/generation")
        resp.raise_for_status()
        return resp.json()

    def get_estimation_generation_info(self, generation_id: int) -> dict:
        resp = self.session.get(f"{self.webapi_url}/estimation/generation/{generation_id}")
        resp.raise_for_status()
        return resp.json()

    def download_estimation_results(self, generation_id: int, output_path: str) -> str:
        """결과 다운로드"""
        resp = self.session.get(
            f"{self.webapi_url}/estimation/generation/{generation_id}/result",
            stream=True,
        )
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"결과 다운로드: {output_path}")
        return output_path

    def download_estimation_r_package(self, estimation_id: int, output_path: str) -> str:
        """Estimation R 패키지 다운로드"""
        resp = self.session.get(
            f"{self.webapi_url}/estimation/{estimation_id}/download",
            stream=True,
        )
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"R 패키지 다운로드: {output_path}")
        return output_path

    def wait_for_estimation(self, estimation_id: int,
                            timeout: int = 3600, poll_interval: int = 30) -> dict:
        """Estimation 완료 대기"""
        start = time.time()
        while time.time() - start < timeout:
            generations = self.get_estimation_generations(estimation_id)
            if generations:
                latest = generations[-1]
                gen_id = latest.get("id")
                info = self.get_estimation_generation_info(gen_id)
                status = info.get("status", {}).get("name", "UNKNOWN")

                if status.startswith("COMPLET"):  # COMPLETE / COMPLETED 모두 허용
                    logger.info(f"Estimation {estimation_id} 완료")
                    return info
                elif status in ("FAILED", "CANCELED"):
                    logger.error(f"Estimation {estimation_id}: {status}")
                    return info
                else:
                    logger.info(f"Estimation {estimation_id}: {status} ({int(time.time()-start)}s)")
            time.sleep(poll_interval)

        logger.error(f"Estimation {estimation_id} 타임아웃")
        return {}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 포탈 프로젝트 / Analysis
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_projects(self) -> list:
        """내 프로젝트 목록 조회"""
        resp = self.session.get(f"{self.portal_url}/api/v1/projects", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [])

    def get_project_analyses(self, project_id: int) -> list:
        """프로젝트 내 analysis 목록"""
        resp = self.session.get(
            f"{self.portal_url}/api/v1/projects/{project_id}/analysis", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [])

    def get_analysis_detail(self, project_id: int, analysis_id: int) -> dict:
        """analysis 상세 정보"""
        resp = self.session.get(
            f"{self.portal_url}/api/v1/projects/{project_id}/analysis/{analysis_id}",
            timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", {})

    def get_analysis_executions(self, project_id: int, analysis_id: int) -> list:
        """analysis 기관별 실행 상태 조회 (주의: 'project' 단수형)"""
        resp = self.session.get(
            f"{self.portal_url}/api/v1/project/{project_id}/analysis/{analysis_id}/execution",
            timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [])

    def get_analysis_execution_summary(self, project_id: int, analysis_id: int) -> dict:
        """기관별 최신 실행 상태 요약

        Returns:
            {"by_cdm": {cdmName: info}, "counts": {...}, "total": n}
        """
        groups = self.get_analysis_executions(project_id, analysis_id)

        # cdm별 전체 execution 수집 → id 순 정렬 후 '최신'을 채택.
        # (기존 버그: content[] 첫 execution 을 채택 → 재실행 시 구버전 상태 보고)
        by_cdm = {}
        for group in groups:
            for ex in group.get("executionList", []):
                cdm = ex.get("cdmName", "?")
                by_cdm.setdefault(cdm, []).append(ex)

        latest_by_cdm = {}
        for cdm, execs in by_cdm.items():
            execs_sorted = sorted(execs, key=lambda e: (e.get("id") or 0))
            chosen = execs_sorted[-1]
            # preempted-duplicate CANCELED walk-back (KB §2.4a):
            # bulk POST 안전검증 시 생성된 즉시 CANCELED(startedAt/completedAt 모두 None)
            # execution 이 최신이면, 그 직전의 실제 execution 을 라이브 상태로 채택.
            if (len(execs_sorted) >= 2
                    and chosen.get("executionStatus") == "CANCELED"
                    and chosen.get("startedAt") is None
                    and chosen.get("completedAt") is None):
                for ex in reversed(execs_sorted[:-1]):
                    if not (ex.get("executionStatus") == "CANCELED"
                            and ex.get("startedAt") is None
                            and ex.get("completedAt") is None):
                        chosen = ex
                        break
            latest_by_cdm[cdm] = chosen

        counts = {"COMPLETE": 0, "RUNNING": 0, "FAILED": 0, "WAITING": 0, "CANCELED": 0}
        for ex in latest_by_cdm.values():
            counts[classify_execution_status(ex.get("executionStatus", ""))] += 1

        return {"by_cdm": latest_by_cdm, "counts": counts, "total": len(latest_by_cdm)}

    def get_project_members(self, project_id: int) -> list:
        """프로젝트 멤버 목록"""
        resp = self.session.get(
            f"{self.portal_url}/api/v1/projects/{project_id}/members", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [])

    def run_analysis_execution(self, project_id: int, analysis_id: int,
                               research_name: str, cdm_ids: list,
                               execution_type: str = "ESTIMATION") -> dict:
        """analysis 실행 트리거 (주의: 'project' 단수형)"""
        payload = {
            "researchName": research_name,
            "executionType": execution_type,
            "cdmIds": cdm_ids,
        }
        resp = self.session.post(
            f"{self.portal_url}/api/v1/project/{project_id}/analysis/{analysis_id}/execution",
            json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        success = result.get("result", False)
        logger.info(f"Execution 트리거: analysis={analysis_id}, cdmIds={cdm_ids}, success={success}")
        return result

    def cancel_analysis_execution(self, project_id: int, analysis_id: int,
                                   execution_id: int) -> dict:
        """실행 취소"""
        resp = self.session.delete(
            f"{self.portal_url}/api/v1/project/{project_id}/analysis/{analysis_id}/execution",
            json={"executionId": execution_id}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_execution_files(self, project_id: int, analysis_id: int,
                             execution_id: int) -> list:
        """execution의 파일 목록"""
        resp = self.session.get(
            f"{self.portal_url}/api/v1/project/{project_id}/analysis/{analysis_id}/execution/{execution_id}/files",
            timeout=30)
        resp.raise_for_status()
        return resp.json().get("content", [])

    def download_execution_file(self, project_id: int, analysis_id: int,
                                 execution_id: int, file_id: int,
                                 output_path: str) -> str:
        """execution 파일 다운로드"""
        url = (f"{self.portal_url}/api/v1/project/{project_id}/analysis/{analysis_id}"
               f"/execution/{execution_id}/files/{file_id}/download")
        resp = self.session.get(url, timeout=600, stream=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        logger.info(f"다운로드 완료: {output_path}")
        return output_path

    def download_execution_result(self, project_id: int, analysis_id: int,
                                   execution_id: int, output_path: str) -> str:
        """execution의 result.zip 자동 검색 후 다운로드"""
        files = self.get_execution_files(project_id, analysis_id, execution_id)
        target = None
        for f in files:
            if f.get("fileName") == "result.zip":
                target = f
                break
        if not target:
            raise FileNotFoundError(f"execution {execution_id}에 result.zip 없음")
        return self.download_execution_file(
            project_id, analysis_id, execution_id, target["id"], output_path)

    def get_execution_logs(self, project_id: int, analysis_id: int,
                            execution_id: int) -> str:
        """execution 실행 로그"""
        resp = self.session.get(
            f"{self.portal_url}/api/v1/project/{project_id}/analysis/{analysis_id}/execution/{execution_id}/logs",
            timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", "")

    def get_available_cdms(self) -> list:
        """실행 가능한 기관 CDM 목록"""
        resp = self.session.get(
            f"{self.portal_url}/api/v1/dashboard/organizations", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", {})
        orgs_raw = content.get("totalOrgs", []) if isinstance(content, dict) else []

        cdm_list = []
        for org in orgs_raw:
            org_id = org.get("id")
            org_name = org.get("name", "?")
            cdm = org.get("cdm") or {}
            atlas_infos = org.get("atlasInfos", [])
            access = org.get("accessAtlas", False)
            if not cdm:
                continue
            cdm_list.append({
                "orgId": org_id,
                "orgName": org_name,
                "cdmId": cdm.get("id"),
                "cdmName": cdm.get("name", "?"),
                "cdmVersion": cdm.get("version", "?"),
                "patientCount": cdm.get("patientCount"),
                "period": cdm.get("period", "?"),
                "atlasInfos": atlas_infos,
                "accessAtlas": access,
            })
        return cdm_list

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Vocabulary / Concept
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def search_concepts(self, query: str, domain: str = None) -> list:
        url = f"{self.webapi_url}/vocabulary/search"
        params = {"query": query}
        if domain:
            params["domain"] = domain
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Vocabulary & Achilles — concept 검증
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_concept(self, concept_id: int) -> dict:
        """Concept 상세 조회"""
        resp = self.session.get(f"{self.webapi_url}/vocabulary/concept/{concept_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_descendants(self, concept_id: int) -> list:
        """Concept의 하위(descendant) concept 목록 조회"""
        resp = self.session.get(
            f"{self.webapi_url}/vocabulary/concept/{concept_id}/descendants", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_achilles_frequency(self, source_key: str, domain: str) -> list:
        """Achilles concept frequency 조회 (condition/drug/measurement/procedure/observation)"""
        resp = self.session.get(
            f"{self.webapi_url}/cdmresults/{source_key}/{domain}", timeout=120)
        resp.raise_for_status()
        return resp.json()

    def get_achilles_drilldown(self, source_key: str, domain: str, concept_id: int) -> list:
        """Achilles concept drilldown (unit, distribution 등)"""
        resp = self.session.get(
            f"{self.webapi_url}/cdmresults/{source_key}/{domain}/{concept_id}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def check_concept_availability(self, concept_id: int, source_key: str, domain: str = "condition",
                                   include_descendants: bool = True) -> dict:
        """기관에서 concept이 존재하는지 확인 (descendant 포함).

        Returns:
            {
                "concept_id": int,
                "direct_count": int,         # 해당 concept 직접 빈도
                "descendant_count": int,      # descendant들의 합산 빈도
                "total_count": int,           # direct + descendant
                "descendant_concepts": [...], # 빈도 있는 descendant 목록
            }
        """
        # Achilles frequency 가져오기
        try:
            achilles = self.get_achilles_frequency(source_key, domain)
        except Exception:
            return {"concept_id": concept_id, "direct_count": 0,
                    "descendant_count": 0, "total_count": 0, "descendant_concepts": []}

        freq_map = {int(r.get("conceptId", 0)): int(r.get("numPersons", 0)) for r in achilles}

        direct = freq_map.get(concept_id, 0)

        desc_total = 0
        desc_list = []
        if include_descendants:
            try:
                descendants = self.get_descendants(concept_id)
                for d in descendants:
                    did = d.get("CONCEPT_ID", 0)
                    n = freq_map.get(did, 0)
                    if n > 0:
                        desc_total += n
                        desc_list.append({"concept_id": did,
                                          "concept_name": d.get("CONCEPT_NAME", ""),
                                          "count": n})
            except Exception:
                pass

        return {
            "concept_id": concept_id,
            "direct_count": direct,
            "descendant_count": desc_total,
            "total_count": direct + desc_total,
            "descendant_concepts": sorted(desc_list, key=lambda x: -x["count"]),
        }

    def check_concept_across_sites(self, concept_id: int, sites: list, domain: str = "condition",
                                   include_descendants: bool = True) -> dict:
        """여러 기관에서 concept 가용성 한번에 확인.

        Args:
            concept_id: 확인할 concept ID
            sites: [(group_id, site_id, code), ...] 리스트
            domain: condition/drug/measurement/procedure/observation
            include_descendants: descendant 포함 여부

        Returns:
            {code: {"total_count": N, "direct_count": N, ...}, ...}
        """
        results = {}
        for gid, sid, code in sites:
            try:
                self.connect_site(gid, sid)
                sources = self.get_sources()
                # 최신 static source 선택
                import re as _re
                static = []
                for s in sources:
                    sn = s["sourceName"]
                    if "monthly" in sn.lower() or "weekly" in sn.lower():
                        continue
                    m = _re.search(r"_(\d+)$", sn)
                    if m:
                        static.append((int(m.group(1)), s))
                latest = sorted(static, key=lambda x: x[0])[-1][1] if static else (
                    sources[-1] if sources else None)
                if not latest:
                    results[code] = {"total_count": 0, "error": "NO SOURCE"}
                    continue

                sk = latest["sourceKey"]
                result = self.check_concept_availability(concept_id, sk, domain, include_descendants)
                results[code] = result
                logger.info(f"{code}: concept {concept_id} total={result['total_count']}")
            except Exception as e:
                results[code] = {"total_count": 0, "error": str(e)[:60]}

        return results

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 유틸리티
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_webapi_info(self) -> dict:
        resp = self.session.get(f"{self.webapi_url}/info", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def check_connection(self) -> bool:
        """WebAPI 연결 확인"""
        try:
            info = self.get_webapi_info()
            logger.info(f"WebAPI OK (version: {info.get('version', '?')})")
            return True
        except Exception:
            try:
                resp = self.session.get(f"{self.webapi_url}/source/sources", timeout=10)
                if resp.status_code == 200:
                    logger.info("WebAPI OK (sources 확인)")
                    return True
            except Exception:
                pass
            logger.error("WebAPI 연결 실패")
            return False

    def refresh_token(self):
        """토큰 갱신

        ⚠️ 미사용(dead) + 미검증 엔드포인트. `/user/refresh` 는 endpoints CSV/KB 에
        문서화되어 있지 않다. 세션 만료 대응이 필요하면 login_portal 재호출을 사용할 것.
        """
        try:
            resp = self.session.get(f"{self.webapi_url}/user/refresh", timeout=10)
            if resp.status_code == 200:
                token = resp.text.strip().strip('"')
                if token and len(token) > 20:
                    self.session.headers["Authorization"] = f"Bearer {token}"
        except requests.RequestException:
            pass
