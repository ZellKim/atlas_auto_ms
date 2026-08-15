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
from typing import Any
from urllib.parse import quote, urlparse

from atlas_auto.generation_safety import (
    finished_generation,
    generation_status,
    is_usable_generation,
    resolve_source_id,
    rows_for_source,
)

from atlas_auto.estimation_validation import (
    EstimationValidationError,
    EstimationValidationIssue,
    ValidatedEstimationExport,
    validate_estimation_design,
    validate_estimation_export,
)

logger = logging.getLogger(__name__)

_TRANSIENT_HTTP_STATUS = {429, 502, 503, 504}
_REDACT_PATTERN = re.compile(
    r'(?i)(password|authorization|cookie|token)(["\s:=]+)([^,}\s]+)'
)


class AtlasApiError(requests.RequestException):
    """A WebAPI response error that is safe to include in logs."""

    def __init__(self, method, path, message, status_code=None):
        self.method = method
        self.path = path
        self.status_code = status_code
        status = f" status={status_code}" if status_code is not None else ""
        super().__init__(f"{method.upper()} {path}{status}: {message}")


def _estimation_design_from_payload(payload):
    """Return a design JSON from either an export or an ATLAS DTO."""
    if not isinstance(payload, dict) or "specification" not in payload:
        return payload
    specification = payload.get("specification")
    if isinstance(specification, dict):
        return specification
    if isinstance(specification, str):
        try:
            parsed = json.loads(specification)
        except (TypeError, ValueError) as exc:
            issue = EstimationValidationIssue(
                "invalid_estimation_specification",
                "specification",
                "ATLAS Estimation specification must contain valid JSON",
            )
            estimation_id = payload.get("id")
            if isinstance(estimation_id, bool) or not isinstance(estimation_id, int):
                estimation_id = None
            estimation_name = payload.get("name")
            if not isinstance(estimation_name, str) or not estimation_name.strip():
                estimation_name = None
            raise EstimationValidationError(
                stage="design",
                issues=(issue,),
                estimation_id=estimation_id,
                estimation_name=estimation_name,
                referenced_concept_set_ids=(),
                effective_nc_count=0,
            ) from exc
        return parsed
    return specification


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

    def _request_webapi_json(
        self,
        method,
        path,
        *,
        params=None,
        json_body=None,
        timeout=(10, 30),
        retry_safe=False,
        allow_empty=False,
    ):
        """Send one WebAPI request using an explicit retry-safety policy."""
        if not self.webapi_url:
            raise RuntimeError("Connect to a site before calling WebAPI methods")

        normalized_path = f"/{path.lstrip('/')}"
        url = f"{self.webapi_url.rstrip('/')}{normalized_path}"
        request_kwargs = {"timeout": timeout}
        if params is not None:
            request_kwargs["params"] = params
        if json_body is not None:
            request_kwargs["json"] = json_body

        attempts = 3 if retry_safe else 1
        response = None
        for attempt in range(attempts):
            try:
                response = self.session.request(method.upper(), url, **request_kwargs)
            except (requests.ConnectionError, requests.Timeout):
                if attempt + 1 >= attempts:
                    raise
                time.sleep(0.25 * (2 ** attempt))
                continue

            if (
                retry_safe
                and response.status_code in _TRANSIENT_HTTP_STATUS
                and attempt + 1 < attempts
            ):
                time.sleep(0.25 * (2 ** attempt))
                continue
            break

        if response is None:
            raise RuntimeError("WebAPI request completed without a response")

        if not 200 <= response.status_code < 300:
            snippet = _REDACT_PATTERN.sub(r"\1\2<redacted>", response.text or "")
            snippet = snippet[:300] or "request failed"
            raise AtlasApiError(
                method,
                normalized_path,
                snippet,
                status_code=response.status_code,
            )

        if response.status_code == 204:
            return None

        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            if allow_empty and not (response.text or "").strip():
                return None
            raise AtlasApiError(method, normalized_path, "invalid JSON response") from exc

        if data is None and allow_empty:
            return None
        if data is None:
            raise AtlasApiError(method, normalized_path, "empty JSON response")
        return data

    @staticmethod
    def _normalize_page_content(data, path):
        """Normalize WebAPI list and Spring Page responses to a list."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("content"), list):
            return data["content"]
        raise AtlasApiError("GET", path, "expected a list or Page response")

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
        """코호트 Generate 완료 대기. 성공은 COMPLETE **AND** isValid.

        `status == "COMPLETE"` 단독은 성공이 아니다. AUMC 2026-08-15에서 두
        코호트가 2.2/1.7시간 실행 후 `COMPLETE` + `isValid: false` +
        `personCount: null`을 반환했다. status만 보면 아무것도 생산하지 않은
        코호트를 완료로 발행하게 된다.

        `source_key`를 주면 `id.sourceId`로 행을 좁힌다. CDM source가 여러 개인
        기관은 source마다 한 행을 반환하므로, 필터 없이 읽으면 다른 source의
        결과를 우리 것으로 오인한다. 알 수 없는 source_key는 조용히 필터를
        끄는 대신 `LookupError`를 낸다.

        판정은 `atlas_auto.generation_safety`가 소유한다.
        """
        source_id = None
        if source_key is not None:
            source_id = resolve_source_id(self.get_sources(), source_key)

        start = time.time()
        while True:
            rows = self.get_cohort_generation_info(cohort_id) or []
            if source_id is not None:
                rows = rows_for_source(rows, source_id)

            finished = finished_generation(rows)
            if finished is not None:
                status = generation_status(finished)
                if is_usable_generation(finished):
                    logger.info(
                        f"코호트 {cohort_id} Generate 완료 "
                        f"(N={finished.get('personCount')})"
                    )
                    return True
                logger.error(
                    f"코호트 {cohort_id}: {status} but unusable "
                    f"(isValid={finished.get('isValid')!r}, "
                    f"personCount={finished.get('personCount')!r}) "
                    f"{finished.get('failMessage', '')}"
                )
                return False

            for row in rows:
                logger.info(
                    f"코호트 {cohort_id}: {generation_status(row)} "
                    f"({int(time.time()-start)}s)"
                )
            if time.time() - start >= timeout:
                break
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

    # Feature Analysis / Cohort Characterization

    def list_feature_analyses(self, size: int = 200, analysis_type: str = None) -> list:
        """List Feature Analysis definitions, normalizing Page responses."""
        params = {"size": size}
        if analysis_type is not None:
            params["type"] = analysis_type
        path = "/feature-analysis/"
        data = self._request_webapi_json(
            "GET", path, params=params, retry_safe=True,
        )
        return self._normalize_page_content(data, path)

    def create_feature_analysis(self, spec: dict) -> dict:
        """Create a Feature Analysis without retrying the mutation."""
        return self._request_webapi_json(
            "POST", "/feature-analysis/", json_body=spec,
        )

    def get_feature_analysis(self, feature_analysis_id: int) -> dict:
        """Get one Feature Analysis definition."""
        return self._request_webapi_json(
            "GET", f"/feature-analysis/{feature_analysis_id}", retry_safe=True,
        )

    def copy_feature_analysis(self, feature_analysis_id: int) -> dict:
        """Copy a Feature Analysis; this mutating GET is never retried."""
        return self._request_webapi_json(
            "GET", f"/feature-analysis/{feature_analysis_id}/copy",
        )

    def update_feature_analysis(self, feature_analysis_id: int, spec: dict) -> dict:
        """Update one Feature Analysis definition."""
        return self._request_webapi_json(
            "PUT", f"/feature-analysis/{feature_analysis_id}", json_body=spec,
        )

    def delete_feature_analysis(self, feature_analysis_id: int):
        """Delete one Feature Analysis definition."""
        return self._request_webapi_json(
            "DELETE",
            f"/feature-analysis/{feature_analysis_id}",
            allow_empty=True,
        )

    def list_characterizations(self, size: int = 200) -> list:
        """List Cohort Characterization definitions."""
        path = "/cohort-characterization/"
        data = self._request_webapi_json(
            "GET", path, params={"size": size}, retry_safe=True,
        )
        return self._normalize_page_content(data, path)

    def get_characterization(self, characterization_id: int) -> dict:
        """Get one Cohort Characterization definition."""
        return self._request_webapi_json(
            "GET",
            f"/cohort-characterization/{characterization_id}",
            retry_safe=True,
        )

    def create_characterization(self, spec: dict) -> dict:
        """Create a Cohort Characterization definition."""
        return self._request_webapi_json(
            "POST", "/cohort-characterization/", json_body=spec,
        )

    def update_characterization(self, characterization_id: int, spec: dict) -> dict:
        """Update one Cohort Characterization definition."""
        return self._request_webapi_json(
            "PUT",
            f"/cohort-characterization/{characterization_id}",
            json_body=spec,
        )

    def delete_characterization(self, characterization_id: int):
        """Delete one Cohort Characterization definition."""
        return self._request_webapi_json(
            "DELETE",
            f"/cohort-characterization/{characterization_id}",
            allow_empty=True,
        )

    def export_characterization(self, characterization_id: int) -> dict:
        """Export one Cohort Characterization definition."""
        return self._request_webapi_json(
            "GET",
            f"/cohort-characterization/{characterization_id}/export",
            retry_safe=True,
        )

    def import_characterization(self, export_spec: dict) -> dict:
        """Import a Cohort Characterization export payload."""
        return self._request_webapi_json(
            "POST", "/cohort-characterization/import", json_body=export_spec,
        )

    def generate_characterization(
        self, characterization_id: int, source_key: str,
    ) -> dict:
        """Start a Characterization generation without automatic retry."""
        encoded_source_key = quote(str(source_key), safe="")
        return self._request_webapi_json(
            "POST",
            f"/cohort-characterization/{characterization_id}/generation/{encoded_source_key}",
        )

    def get_characterization_generations(self, characterization_id: int) -> list:
        """List generations for a Cohort Characterization definition."""
        path = f"/cohort-characterization/{characterization_id}/generation"
        data = self._request_webapi_json("GET", path, retry_safe=True)
        return self._normalize_page_content(data, path)

    def get_characterization_result_count(self, generation_id: int) -> int:
        """Return the WebAPI 2.12 numeric result count."""
        path = f"/cohort-characterization/generation/{generation_id}/result/count"
        data = self._request_webapi_json("GET", path, retry_safe=True)
        try:
            return int(data)
        except (TypeError, ValueError) as exc:
            raise AtlasApiError("GET", path, "expected a numeric result count") from exc

    def get_characterization_results(
        self, generation_id: int, threshold_level: float = 0,
    ) -> list:
        """Return the full WebAPI 2.12 Characterization result list.

        ``threshold_level`` defaults to 0 on purpose. WebAPI's own default of
        0.01 drops covariate rows below 1% prevalence without reporting it,
        and a row missing from the list reads as a zero downstream. Pair every
        call with ``get_characterization_result_count`` and compare, or use
        ``CharacterizationService.collect_results`` which does it for you.
        """
        path = f"/cohort-characterization/generation/{generation_id}/result"
        data = self._request_webapi_json(
            "GET",
            path,
            params={"thresholdLevel": threshold_level},
            timeout=(10, 120),
            retry_safe=True,
        )
        if not isinstance(data, list):
            raise AtlasApiError("GET", path, "expected a result list")
        return data

    def delete_characterization_generation(self, generation_id: int):
        """Delete one Characterization generation."""
        return self._request_webapi_json(
            "DELETE",
            f"/cohort-characterization/generation/{generation_id}",
            allow_empty=True,
        )

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

    def get_validated_estimation_export(
        self, estimation_id: int,
    ) -> ValidatedEstimationExport:
        """Fetch an Estimation export and return it coupled to NC proof."""
        exported = self.export_estimation(estimation_id)
        validation = validate_estimation_export(exported)
        return ValidatedEstimationExport(
            estimation_id=int(estimation_id),
            export=exported,
            validation=validation,
        )

    def create_estimation(self, spec: dict) -> dict:
        validate_estimation_design(_estimation_design_from_payload(spec))
        resp = self.session.post(f"{self.webapi_url}/estimation/", json=spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Estimation 생성: ID={result.get('id')}")
        return result

    def update_estimation(self, estimation_id: int, spec: dict) -> dict:
        """Update an Estimation only after its stored design passes NC checks.

        ``spec`` may be an ATLAS DTO with a JSON-string ``specification`` or a
        design object. For a design object, the current DTO is read only after
        validation and is then used to preserve server-owned metadata.
        """
        design = _estimation_design_from_payload(spec)
        validate_estimation_design(design)
        if isinstance(spec, dict) and "specification" in spec:
            payload = spec
            if isinstance(spec.get("specification"), dict):
                payload = dict(spec)
                payload["specification"] = json.dumps(
                    spec["specification"], ensure_ascii=False
                )
        else:
            payload = dict(self.get_estimation(estimation_id))
            payload["specification"] = json.dumps(design, ensure_ascii=False)
            if isinstance(design, dict):
                if design.get("name") is not None:
                    payload["name"] = design["name"]
                if design.get("description") is not None:
                    payload["description"] = design["description"]
        resp = self.session.put(
            f"{self.webapi_url}/estimation/{estimation_id}", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    def import_estimation(self, full_spec: dict) -> dict:
        """Estimation Import (export JSON 형식)

        ⚠️ 주의: `/estimation/import` 엔드포인트는 endpoints CSV 에서 used_in_project=N
        (프로덕션 미검증)이다. 검증된 프로덕션 등록 방식은
        `GET /estimation/{id}/copy → PUT /estimation/{id}` copy+PUT 패턴이며,
        `data/scripts/v4_phase_b_build.py` 및 KB §1.1 참조. 신규 코드는 그 패턴을 권장.
        """
        validate_estimation_export(full_spec)
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
    # Cohort Pathways (PathwayService) — base: /pathway-analysis
    # OHDSI WebAPI master 기준 + feedernet 2.12.0 live 검증(2026-06, site 7/203, read-only GET 200).
    # 주의: /{id}/generation 은 미생성 pathway에서 500(ConversionFailed) — get_pathway_generations가 []로 처리.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_pathway_analyses(self, size: int = 2000) -> list:
        """List Pathway definitions without silently truncating exact-name checks."""
        path = "/pathway-analysis/"
        data = self._request_webapi_json(
            "GET", path, params={"size": size}, retry_safe=True,
        )
        return self._normalize_page_content(data, path)

    def get_pathway_analysis(self, pathway_id: int) -> dict:
        """Pathway 분석 상세 (GET /pathway-analysis/{id})"""
        resp = self.session.get(f"{self.webapi_url}/pathway-analysis/{pathway_id}")
        resp.raise_for_status()
        return resp.json()

    def create_pathway_analysis(self, spec: dict) -> dict:
        """Pathway 생성 (POST /pathway-analysis/, body=PathwayAnalysisDTO)"""
        resp = self.session.post(f"{self.webapi_url}/pathway-analysis/", json=spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Pathway 생성: ID={result.get('id')}")
        return result

    def update_pathway_analysis(self, pathway_id: int, spec: dict) -> dict:
        """Pathway 수정 (PUT /pathway-analysis/{id})"""
        resp = self.session.put(f"{self.webapi_url}/pathway-analysis/{pathway_id}", json=spec)
        resp.raise_for_status()
        return resp.json()

    def delete_pathway_analysis(self, pathway_id: int) -> None:
        """Pathway 삭제 (DELETE /pathway-analysis/{id})"""
        resp = self.session.delete(f"{self.webapi_url}/pathway-analysis/{pathway_id}")
        resp.raise_for_status()

    def copy_pathway_analysis(self, pathway_id: int) -> dict:
        """Pathway 복사 (POST /pathway-analysis/{id})"""
        resp = self.session.post(f"{self.webapi_url}/pathway-analysis/{pathway_id}")
        resp.raise_for_status()
        return resp.json()

    def import_pathway_analysis(self, full_spec: dict) -> dict:
        """Pathway import (POST /pathway-analysis/import, export JSON 형식)"""
        resp = self.session.post(f"{self.webapi_url}/pathway-analysis/import", json=full_spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Pathway Import: ID={result.get('id')}")
        return result

    def export_pathway_analysis(self, pathway_id: int) -> dict:
        """Pathway export (GET /pathway-analysis/{id}/export). 응답은 JSON 문자열."""
        resp = self.session.get(f"{self.webapi_url}/pathway-analysis/{pathway_id}/export")
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return json.loads(resp.text)

    def get_pathway_sql(self, pathway_id: int, source_key: str) -> str:
        """Pathway 분석 SQL 생성 (GET /pathway-analysis/{id}/sql/{sourceKey})"""
        resp = self.session.get(f"{self.webapi_url}/pathway-analysis/{pathway_id}/sql/{source_key}")
        resp.raise_for_status()
        return resp.text

    def generate_pathway(self, pathway_id: int, source_key: str) -> dict:
        """Pathway 실행 시작 (POST /pathway-analysis/{id}/generation/{sourceKey} → JobExecutionResource)"""
        resp = self.session.post(
            f"{self.webapi_url}/pathway-analysis/{pathway_id}/generation/{source_key}")
        resp.raise_for_status()
        logger.info(f"Pathway 실행: ID={pathway_id}")
        return resp.json()

    def cancel_pathway_generation(self, pathway_id: int, source_key: str) -> None:
        """Pathway 실행 취소 (DELETE /pathway-analysis/{id}/generation/{sourceKey})"""
        resp = self.session.delete(
            f"{self.webapi_url}/pathway-analysis/{pathway_id}/generation/{source_key}")
        resp.raise_for_status()

    def get_pathway_generations(self, pathway_id: int) -> list:
        """Pathway 실행 목록 (GET /pathway-analysis/{id}/generation → CommonGenerationDTO[]).

        주의: 한 번도 generate 안 한 pathway는 WebAPI 2.12.0에서 500(Spring ConversionFailed)
        을 반환 → 빈 목록으로 처리(feedernet live 확인 2026-06).
        """
        resp = self.session.get(f"{self.webapi_url}/pathway-analysis/{pathway_id}/generation")
        if resp.status_code == 500 and "Conversion" in resp.text:
            return []
        resp.raise_for_status()
        return resp.json()

    def get_pathway_generation_info(self, generation_id: int) -> dict:
        """Pathway 실행 상태 상세 (GET /pathway-analysis/generation/{genId})"""
        resp = self.session.get(f"{self.webapi_url}/pathway-analysis/generation/{generation_id}")
        resp.raise_for_status()
        return resp.json()

    def get_pathway_results(self, generation_id: int) -> dict:
        """Pathway 결과 (GET /pathway-analysis/generation/{genId}/result → PathwayPopulationResultsDTO)"""
        resp = self.session.get(
            f"{self.webapi_url}/pathway-analysis/generation/{generation_id}/result")
        resp.raise_for_status()
        return resp.json()

    def wait_for_pathway_generation(self, pathway_id: int,
                                    timeout: int = 1800, poll_interval: int = 20) -> dict:
        """Pathway 실행 완료 대기 (estimation 패턴과 동일).

        주의: 완료/실패 status 문자열(GenerationStatus)은 OHDSI 표준 기준이며
        feedernet live 응답에서 확인 필요 (COMPLETE/COMPLETED 모두 허용 처리).
        """
        start = time.time()
        while time.time() - start < timeout:
            generations = self.get_pathway_generations(pathway_id)
            if generations:
                latest = generations[-1]
                status_val = latest.get("status", "UNKNOWN")
                status = status_val.get("name", status_val) if isinstance(status_val, dict) else str(status_val)
                status_u = str(status).upper()
                if status_u.startswith("COMPLET"):
                    logger.info(f"Pathway {pathway_id} 완료")
                    return latest
                elif status_u in ("FAILED", "CANCELED", "CANCELLED", "ERROR", "STOPPED"):
                    logger.error(f"Pathway {pathway_id}: {status}")
                    return latest
                else:
                    logger.info(f"Pathway {pathway_id}: {status} ({int(time.time()-start)}s)")
            time.sleep(poll_interval)
        logger.error(f"Pathway {pathway_id} 타임아웃")
        return {}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ConceptSet (ConceptSetService) — base /conceptset
    # OHDSI WebAPI master 기준 + feedernet 2.12.0 read-only live 검증(2026-06).
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_concept_sets(self) -> list:
        """Concept set 목록 (GET /conceptset/)"""
        resp = self.session.get(f"{self.webapi_url}/conceptset/")
        resp.raise_for_status()
        return resp.json()

    def get_concept_set(self, cs_id: int) -> dict:
        """Concept set 상세 (GET /conceptset/{id})"""
        resp = self.session.get(f"{self.webapi_url}/conceptset/{cs_id}")
        resp.raise_for_status()
        return resp.json()

    def create_concept_set(self, spec: dict) -> dict:
        """Concept set 생성 (POST /conceptset/, body=ConceptSetDTO)"""
        resp = self.session.post(f"{self.webapi_url}/conceptset/", json=spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"ConceptSet 생성: ID={result.get('id')}")
        return result

    def update_concept_set(self, cs_id: int, spec: dict) -> dict:
        """Concept set 수정 (PUT /conceptset/{id})"""
        resp = self.session.put(f"{self.webapi_url}/conceptset/{cs_id}", json=spec)
        resp.raise_for_status()
        return resp.json()

    def delete_concept_set(self, cs_id: int) -> None:
        """Concept set 삭제 (DELETE /conceptset/{id})"""
        resp = self.session.delete(f"{self.webapi_url}/conceptset/{cs_id}")
        resp.raise_for_status()

    def get_concept_set_items(self, cs_id: int) -> list:
        """Concept set items (GET /conceptset/{id}/items)"""
        resp = self.session.get(f"{self.webapi_url}/conceptset/{cs_id}/items")
        resp.raise_for_status()
        return resp.json()

    def set_concept_set_items(self, cs_id: int, items: list):
        """Concept set items 설정 (PUT /conceptset/{id}/items, body=ConceptSetItem[])"""
        resp = self.session.put(f"{self.webapi_url}/conceptset/{cs_id}/items", json=items)
        resp.raise_for_status()
        return resp.json()

    def get_concept_set_expression(self, cs_id: int, source_key: str = None) -> dict:
        """Concept set resolved expression (GET /conceptset/{id}/expression[/{sourceKey}])"""
        url = f"{self.webapi_url}/conceptset/{cs_id}/expression"
        if source_key:
            url += f"/{source_key}"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def export_concept_set(self, cs_id: int):
        """Concept set export (GET /conceptset/{id}/export).

        feedernet 2.12.0은 **zip(bytes)** 반환 → JSON이면 dict, 아니면 bytes(zip).
        """
        resp = self.session.get(f"{self.webapi_url}/conceptset/{cs_id}/export")
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return resp.content

    def get_concept_set_generation_info(self, cs_id: int) -> list:
        """Concept set generation info (GET /conceptset/{id}/generationinfo)"""
        resp = self.session.get(f"{self.webapi_url}/conceptset/{cs_id}/generationinfo")
        resp.raise_for_status()
        return resp.json()

    def check_concept_set(self, spec: dict) -> dict:
        """Concept set 설계 진단 (POST /conceptset/check → CheckResult)"""
        resp = self.session.post(f"{self.webapi_url}/conceptset/check", json=spec)
        resp.raise_for_status()
        return resp.json()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Incidence Rate (IRAnalysisResource) — base /ir
    # 주의: 실행은 GET /ir/{id}/execute/{sourceKey} (POST 아님).
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_incidence_rates(self) -> list:
        """IR 분석 목록 (GET /ir/)"""
        resp = self.session.get(f"{self.webapi_url}/ir/")
        resp.raise_for_status()
        return resp.json()

    def get_incidence_rate(self, ir_id: int) -> dict:
        """IR 분석 상세 (GET /ir/{id})"""
        resp = self.session.get(f"{self.webapi_url}/ir/{ir_id}")
        resp.raise_for_status()
        return resp.json()

    def get_incidence_rate_design(self, ir_id: int) -> dict:
        """IR 설계 (GET /ir/{id}/design)"""
        resp = self.session.get(f"{self.webapi_url}/ir/{ir_id}/design")
        resp.raise_for_status()
        return resp.json()

    def create_incidence_rate(self, spec: dict) -> dict:
        """IR 생성 (POST /ir/, body=IRAnalysisDTO)"""
        resp = self.session.post(f"{self.webapi_url}/ir/", json=spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"IR 생성: ID={result.get('id')}")
        return result

    def update_incidence_rate(self, ir_id: int, spec: dict) -> dict:
        """IR 수정 (PUT /ir/{id})"""
        resp = self.session.put(f"{self.webapi_url}/ir/{ir_id}", json=spec)
        resp.raise_for_status()
        return resp.json()

    def delete_incidence_rate(self, ir_id: int) -> None:
        """IR 삭제 (DELETE /ir/{id})"""
        resp = self.session.delete(f"{self.webapi_url}/ir/{ir_id}")
        resp.raise_for_status()

    def copy_incidence_rate(self, ir_id: int) -> dict:
        """IR 복사 (GET /ir/{id}/copy)"""
        resp = self.session.get(f"{self.webapi_url}/ir/{ir_id}/copy")
        resp.raise_for_status()
        return resp.json()

    def execute_incidence_rate(self, ir_id: int, source_key: str) -> dict:
        """IR 실행 시작 — 주의: GET! (GET /ir/{id}/execute/{sourceKey} → JobExecutionResource)"""
        resp = self.session.get(f"{self.webapi_url}/ir/{ir_id}/execute/{source_key}")
        resp.raise_for_status()
        logger.info(f"IR 실행: ID={ir_id}")
        return resp.json()

    def cancel_incidence_rate(self, ir_id: int, source_key: str) -> None:
        """IR 실행 취소 (DELETE /ir/{id}/execute/{sourceKey})"""
        resp = self.session.delete(f"{self.webapi_url}/ir/{ir_id}/execute/{source_key}")
        resp.raise_for_status()

    def get_incidence_rate_info(self, ir_id: int, source_key: str = None):
        """IR 실행 정보 (GET /ir/{id}/info[/{sourceKey}]). source_key 없으면 전체 목록."""
        url = f"{self.webapi_url}/ir/{ir_id}/info"
        if source_key:
            url += f"/{source_key}"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_incidence_rate_report(self, ir_id: int, source_key: str,
                                  target_id: int, outcome_id: int) -> dict:
        """IR 결과 리포트 (GET /ir/{id}/report/{sourceKey}?targetId=&outcomeId=)"""
        resp = self.session.get(f"{self.webapi_url}/ir/{ir_id}/report/{source_key}",
                                params={"targetId": target_id, "outcomeId": outcome_id})
        resp.raise_for_status()
        return resp.json()

    def export_incidence_rate(self, ir_id: int):
        """IR export (GET /ir/{id}/export). Response(zip 가능) → JSON이면 dict, 아니면 bytes."""
        resp = self.session.get(f"{self.webapi_url}/ir/{ir_id}/export")
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return resp.content

    def get_incidence_rate_sql(self, request: dict) -> Any:
        """IR SQL 생성 (POST /ir/sql, GenerateSqlRequest DTO)."""
        resp = self.session.post(f"{self.webapi_url}/ir/sql", json=request)
        resp.raise_for_status()
        return resp.json()

    def check_incidence_rate(self, spec: dict) -> dict:
        """IR 설계 진단 (POST /ir/check → CheckResult)"""
        resp = self.session.post(f"{self.webapi_url}/ir/check", json=spec)
        resp.raise_for_status()
        return resp.json()

    def wait_for_incidence_rate(self, ir_id: int, source_key: str,
                                timeout: int = 1800, poll_interval: int = 15) -> dict:
        """IR 실행 완료 대기 (GET /ir/{id}/info/{sourceKey}의 executionInfo.status 폴링).

        status 문자열은 OHDSI GenerationStatus 기준. feedernet 2.12.0 기존 완료 IR에서
        status='COMPLETE' 확인(2026-06, read-path). COMPLETE/COMPLETED 모두 허용.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                info = self.get_incidence_rate_info(ir_id, source_key)
            except Exception:  # noqa: BLE001
                info = None
            ex = info.get("executionInfo", {}) if isinstance(info, dict) else {}
            status = ex.get("status", "UNKNOWN")
            status = status.get("name") if isinstance(status, dict) else str(status)
            stu = str(status).upper()
            if stu.startswith("COMPLET"):
                logger.info(f"IR {ir_id} 완료")
                return info
            elif stu in ("FAILED", "CANCELED", "CANCELLED", "ERROR", "STOPPED"):
                logger.error(f"IR {ir_id}: {status}")
                return info
            else:
                logger.info(f"IR {ir_id}: {status} ({int(time.time()-start)}s)")
            time.sleep(poll_interval)
        logger.error(f"IR {ir_id} 타임아웃")
        return {}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Prediction / PLP (PredictionController) — base /prediction
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_predictions(self) -> list:
        """PLP 목록 (GET /prediction/)"""
        resp = self.session.get(f"{self.webapi_url}/prediction/")
        resp.raise_for_status()
        return resp.json()

    def get_prediction(self, prediction_id: int) -> dict:
        """PLP 상세 (GET /prediction/{id})"""
        resp = self.session.get(f"{self.webapi_url}/prediction/{prediction_id}")
        resp.raise_for_status()
        return resp.json()

    def create_prediction(self, spec: dict) -> dict:
        """PLP 생성 (POST /prediction/, body=PredictionAnalysis)"""
        resp = self.session.post(f"{self.webapi_url}/prediction/", json=spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Prediction 생성: ID={result.get('id')}")
        return result

    def update_prediction(self, prediction_id: int, spec: dict) -> dict:
        """PLP 수정 (PUT /prediction/{id})"""
        resp = self.session.put(f"{self.webapi_url}/prediction/{prediction_id}", json=spec)
        resp.raise_for_status()
        return resp.json()

    def delete_prediction(self, prediction_id: int) -> None:
        """PLP 삭제 (DELETE /prediction/{id})"""
        resp = self.session.delete(f"{self.webapi_url}/prediction/{prediction_id}")
        resp.raise_for_status()

    def copy_prediction(self, prediction_id: int) -> dict:
        """PLP 복사 (GET /prediction/{id}/copy)"""
        resp = self.session.get(f"{self.webapi_url}/prediction/{prediction_id}/copy")
        resp.raise_for_status()
        return resp.json()

    def import_prediction(self, full_spec: dict) -> dict:
        """PLP import (POST /prediction/import)"""
        resp = self.session.post(f"{self.webapi_url}/prediction/import", json=full_spec)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Prediction Import: ID={result.get('id')}")
        return result

    def export_prediction(self, prediction_id: int) -> dict:
        """PLP export (GET /prediction/{id}/export)"""
        resp = self.session.get(f"{self.webapi_url}/prediction/{prediction_id}/export")
        resp.raise_for_status()
        return resp.json()

    def generate_prediction(self, prediction_id: int, source_key: str) -> dict:
        """PLP 실행 시작 (POST /prediction/{id}/generation/{sourceKey} → JobExecutionResource)"""
        resp = self.session.post(
            f"{self.webapi_url}/prediction/{prediction_id}/generation/{source_key}")
        resp.raise_for_status()
        logger.info(f"Prediction 실행: ID={prediction_id}")
        return resp.json()

    def get_prediction_generations(self, prediction_id: int) -> list:
        """PLP 실행 목록 (GET /prediction/{id}/generation → ExecutionBasedGenerationDTO[])"""
        resp = self.session.get(f"{self.webapi_url}/prediction/{prediction_id}/generation")
        resp.raise_for_status()
        return resp.json()

    def get_prediction_generation_info(self, generation_id: int) -> dict:
        """PLP 실행 상태 (GET /prediction/generation/{genId})"""
        resp = self.session.get(f"{self.webapi_url}/prediction/generation/{generation_id}")
        resp.raise_for_status()
        return resp.json()

    def get_prediction_results(self, generation_id: int):
        """PLP 결과 (GET /prediction/generation/{genId}/result)"""
        resp = self.session.get(
            f"{self.webapi_url}/prediction/generation/{generation_id}/result")
        resp.raise_for_status()
        return resp.json()

    def check_prediction(self, spec: dict) -> dict:
        """PLP 설계 진단 (POST /prediction/check → CheckResult)"""
        resp = self.session.post(f"{self.webapi_url}/prediction/check", json=spec)
        resp.raise_for_status()
        return resp.json()

    def wait_for_prediction_generation(self, prediction_id: int,
                                       timeout: int = 3600, poll_interval: int = 30) -> dict:
        """PLP 실행 완료 대기 (estimation/pathway 패턴 — generation 목록 status 폴링).

        주의: PLP generation status 문자열은 feedernet live 미검증(by analogy).
        pathway/estimation과 동형 가정. COMPLETE/COMPLETED 모두 허용.
        """
        start = time.time()
        while time.time() - start < timeout:
            generations = self.get_prediction_generations(prediction_id)
            if generations:
                latest = generations[-1]
                sv = latest.get("status", "UNKNOWN")
                status = sv.get("name", sv) if isinstance(sv, dict) else str(sv)
                stu = str(status).upper()
                if stu.startswith("COMPLET"):
                    logger.info(f"Prediction {prediction_id} 완료")
                    return latest
                elif stu in ("FAILED", "CANCELED", "CANCELLED", "ERROR", "STOPPED"):
                    logger.error(f"Prediction {prediction_id}: {status}")
                    return latest
                else:
                    logger.info(f"Prediction {prediction_id}: {status} ({int(time.time()-start)}s)")
            time.sleep(poll_interval)
        logger.error(f"Prediction {prediction_id} 타임아웃")
        return {}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Job (JobService) — base /job — 범용 실행 상태
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def list_job_names(self) -> list:
        """Job 이름 목록 (GET /job/)"""
        resp = self.session.get(f"{self.webapi_url}/job/")
        resp.raise_for_status()
        return resp.json()

    def get_job_instance(self, job_id: int) -> dict:
        """Job instance 상태 (GET /job/{jobId})"""
        resp = self.session.get(f"{self.webapi_url}/job/{job_id}")
        resp.raise_for_status()
        return resp.json()

    def get_job_execution(self, execution_id: int) -> dict:
        """Job execution 상태 (GET /job/execution/{executionId})"""
        resp = self.session.get(f"{self.webapi_url}/job/execution/{execution_id}")
        resp.raise_for_status()
        return resp.json()

    def get_job_executions(self, job_name: str = None, page_index: int = 0,
                           page_size: int = 100) -> dict:
        """Job execution 페이지 (GET /job/execution?jobName=&pageIndex=&pageSize=)"""
        params = {"pageIndex": page_index, "pageSize": page_size}
        if job_name:
            params["jobName"] = job_name
        resp = self.session.get(f"{self.webapi_url}/job/execution", params=params)
        resp.raise_for_status()
        return resp.json()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Cohort / Vocabulary 보강
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def cancel_cohort_generation(self, cohort_id: int, source_key: str) -> None:
        """코호트 Generate 취소 — 주의: GET! (GET /cohortdefinition/{id}/cancel/{sourceKey})"""
        resp = self.session.get(f"{self.webapi_url}/cohortdefinition/{cohort_id}/cancel/{source_key}")
        resp.raise_for_status()

    def get_cohort_definition_sql(self, request: dict) -> str:
        """코호트 SQL 생성 (POST /cohortdefinition/sql, body={expression, options}).

        이 WebAPI에서 `/cohortdefinition/check`는 중첩 correlated 표현식에
        HTTP 500을 반환한다(2026-08-13 live 확인). 배포 전 설계 관문은 SQL 생성이다.
        """
        resp = self.session.post(f"{self.webapi_url}/cohortdefinition/sql", json=request)
        resp.raise_for_status()
        return resp.text

    def check_cohort_definition(self, spec: dict) -> dict:
        """코호트 설계 진단 (POST /cohortdefinition/check → CheckResult)"""
        resp = self.session.post(f"{self.webapi_url}/cohortdefinition/check", json=spec)
        resp.raise_for_status()
        return resp.json()

    def lookup_concept_identifiers(self, source_key: str, concept_ids: list) -> list:
        """conceptId 배치 조회 (POST /vocabulary/{sourceKey}/lookup/identifiers)"""
        resp = self.session.post(
            f"{self.webapi_url}/vocabulary/{source_key}/lookup/identifiers", json=concept_ids)
        resp.raise_for_status()
        return resp.json()

    def lookup_mapped_concepts(self, source_key: str, concept_ids: list) -> list:
        """source-to-standard 매핑 조회 (POST /vocabulary/{sourceKey}/lookup/mapped)"""
        resp = self.session.post(
            f"{self.webapi_url}/vocabulary/{source_key}/lookup/mapped", json=concept_ids)
        resp.raise_for_status()
        return resp.json()

    def lookup_recommended_concepts(self, source_key: str, concept_ids: list) -> list:
        """추천 concept (POST /vocabulary/{sourceKey}/lookup/recommended)"""
        resp = self.session.post(
            f"{self.webapi_url}/vocabulary/{source_key}/lookup/recommended", json=concept_ids)
        resp.raise_for_status()
        return resp.json()

    def compare_concept_sets(self, source_key: str, payload) -> list:
        """Concept set 비교 (POST /vocabulary/{sourceKey}/compare)"""
        resp = self.session.post(f"{self.webapi_url}/vocabulary/{source_key}/compare", json=payload)
        resp.raise_for_status()
        return resp.json()

    def optimize_concept_set(self, source_key: str, payload) -> dict:
        """Concept set 최적화 (POST /vocabulary/{sourceKey}/optimize)"""
        resp = self.session.post(f"{self.webapi_url}/vocabulary/{source_key}/optimize", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_vocabulary_info(self, source_key: str) -> dict:
        """Vocabulary 메타정보 (GET /vocabulary/{sourceKey}/info)"""
        resp = self.session.get(f"{self.webapi_url}/vocabulary/{source_key}/info")
        resp.raise_for_status()
        return resp.json()

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
        resp = self.session.post(
            f"{self.portal_url}/api/v1/project/{project_id}/analysis/{analysis_id}/execution/{execution_id}/cancel",
            timeout=15)
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
        url = f"{self.webapi_url}/vocabulary/search/{quote(query, safe='')}"
        resp = self.session.get(url)
        resp.raise_for_status()
        results = resp.json()
        if domain:
            domain_l = domain.lower()
            results = [
                r for r in results
                if str(r.get("DOMAIN_ID", "")).lower() == domain_l
            ]
        return results

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
