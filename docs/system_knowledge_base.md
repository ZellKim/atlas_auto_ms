# atlas-auto 시스템 지식 베이스

## 목적

이 문서는 feedernet/ATLAS API 활용법, 기관 매핑, 분석 방법론, 이슈 해결, 실행 기록을 **한 곳에** 정리하여 향후 새로운 연구에 재사용 가능한 중앙 지식 저장소입니다.

> **문서 구조 원칙**: 변동사항, 새로 발견한 사항, 이슈 해결은 모두 이 문서에 기록합니다.
> - `PROGRESS.md` — 현재 상태 + TODO만 (간결한 스냅샷)
> - `concept_selection_guide.md` — Concept ID 선정 전용 가이드
> - `paper_draft.md` — 논문 본문
> - `paper_ijs_checklist.md` — 투고 체크리스트

---

## 1. API 엔드포인트 치트시트

> **★ API 호출 전 반드시 이 치트시트를 참조할 것.** 엔드포인트를 기억에 의존하면 하이픈 유무, 단수/복수 등으로 오류 발생함. 전체 목록: `atlas_auto_cmdata/atlas_webapi_endpoints_full.csv`

### 포탈 API (`https://www.feedernet.com/api/v1/`)

| Method | Endpoint | 용도 |
|--------|----------|------|
| POST | `/auth/login` | 로그인 (email/password → cookie) |
| GET | `/dashboard/organizations` | 기관 목록 |
| POST | `/projects/{pid}/analysis` | analysis 생성 |
| GET | `/projects/{pid}/analysis` | analysis 목록 (**복수** projects) |
| GET | `/projects/{pid}/analysis/{aid}/atlas` | ATLAS 기관 목록 |
| GET | `/projects/{pid}/analysis/{aid}/atlas/{atlasId}` | 해당 ATLAS estimation 목록 |
| POST | `/projects/{pid}/analysis/{aid}/atlas/{atlasId}` | estimation import (body: atlasResearchId, researchType) |
| POST | `/project/{pid}/analysis/{aid}/execution` | 실행 트리거 (**단수** project, body: cdmIds) |
| GET | `/project/{pid}/analysis/{aid}/execution` | 실행 상태 조회 |
| DELETE | `/project/{pid}/analysis/{aid}/execution` | 실행 취소 (body: executionId) |
| GET | `.../execution/{eid}/files` | 결과 파일 목록 |
| GET | `.../execution/{eid}/files/{fid}/download` | result.zip 다운로드 |

### ATLAS WebAPI (`/api/v1/atlas/{group_id}/{site_id}/`)

| Method | Endpoint | 용도 |
|--------|----------|------|
| GET | `/info` | ATLAS 버전 확인 |
| GET | `/source/sources` | CDM source 목록 |
| **코호트** | | |
| GET | `/cohortdefinition` | 코호트 목록 |
| GET | `/cohortdefinition/{id}` | 코호트 상세 |
| POST | `/cohortdefinition` | 코호트 생성 |
| POST | `/cohortdefinition/{id}/generate/{sourceKey}` | 코호트 Generate |
| GET | `/cohortdefinition/{id}/info` | Generate 상태/결과 |
| GET | `/cohortdefinition/{id}/report/{sourceKey}` | 코호트 리포트 (N수 등) |
| **Estimation** | | |
| GET | `/estimation/` | estimation 목록 |
| GET | `/estimation/{id}` | estimation 상세 (specification 포함) |
| GET | `/estimation/{id}/copy` | estimation 복사 |
| PUT | `/estimation/{id}` | estimation 수정 |
| GET | `/estimation/{id}/export` | estimation export (zip용 JSON) |
| POST | `/estimation/import` | estimation import |
| GET | `/estimation/{id}/generation` | 실행 상태 |
| **Characterization** | | |
| GET | `/cohort-characterization?size=200` | characterization 목록 |
| POST | `/cohort-characterization` | characterization 생성 (FA 비어있을 수 있음) |
| GET | `/cohort-characterization/{id}/export` | export (FA 포함) |
| POST | `/cohort-characterization/import` | import (**FA 정상 등록됨, 권장**) |
| POST | `/cohort-characterization/{id}/generation/{sourceKey}` | 실행 |
| GET | `/cohort-characterization/{id}/generation` | 실행 상태 |
| GET | `/cohort-characterization/generation/{genId}/result?size=500` | 결과 조회 |
| **Feature Analysis** | | |
| GET | `/feature-analysis?size=200&type=PRESET` | PRESET FA 목록 |
| GET | `/feature-analysis/{id}/copy` | FA 복사 |
| PUT | `/feature-analysis/{id}` | FA 수정 (2단계 PUT 필요) |
| **Vocabulary** | | |
| GET | `/vocabulary/concept/{id}` | concept 상세 |
| GET | `/vocabulary/search/{query}` | concept 검색 |
| **Achilles** | | |
| GET | `/cdmresults/{sourceKey}/{domain}` | concept frequency (condition/measurement/drug 등) |
| GET | `/cdmresults/{sourceKey}/measurement/{conceptId}` | measurement drilldown (unit, distribution) |

### 추가 유용 엔드포인트

| Method | Endpoint | 용도 |
|--------|----------|------|
| GET | `/estimation/{id}/download` | R 패키지 zip 직접 다운로드 |
| GET | `/vocabulary/concept/{id}/descendants` | 하위 concept 조회 |
| POST | `/vocabulary/{sourceKey}/resolveConceptSetExpression` | concept set → 실제 concept 해석 |
| GET | `/cdmresults/{sourceKey}/dashboard` | CDM 대시보드 (전체 요약) |
| GET | `/cdmresults/{sourceKey}/person` | 인구통계 |
| GET | `/cdmresults/{sourceKey}/observationPeriod` | 관찰 기간 |
| GET | `/cohortdefinition/{id}/copy` | 코호트 복사 |
| GET | `/feature-analysis/aggregates` | 집계 방식 목록 |

전체 엔드포인트 (70+): `atlas_auto_cmdata/atlas_webapi_endpoints_full.csv`
원본 소스: `tool_package/WebAPI-master/` (Java JAX-RS), `tool_package/evidnet/` (R 패키지, REST API 아님)

### 주의사항

- 포탈 API: `project`(단수) vs `projects`(복수) 혼용
- Characterization 직접 POST는 FA가 비어있을 수 있음 → **export/import 방식 권장**
- Estimation 직접 POST 500 에러 → **copy + PUT 방식 사용**
- Estimation copy+PUT으로 outcomeIds 변경 시 → **cohortDefinitions 배열에 새 코호트 정의도 추가 필수** (안 하면 zip에 포함 안 되어 실행해도 결과 없음)
- **Multi-concept OR 코호트의 InclusionRules**: Prior normal = **ANY** (어느 concept이든 정상값 1개 있으면 OK), No prior abnormal = **ALL** (모든 concept에서 이상값 0개). ALL로 하면 한 concept만 있는 기관에서 환자 0명
- Achilles는 해당 concept 직접 빈도만 반환 (descendant 미포함)
- evidnet은 R 패키지 (REST API 아님) — execute(), createCohorts() 등 R 함수
- **cohortdefinition vs cohort-definition**: 하이픈 없는 `/cohortdefinition/`이 정확. 하이픈 있으면 404. 같은 패턴: `/cohort-characterization/`은 하이픈 있음, `/feature-analysis/`도 하이픈 있음 — 일관성 없으므로 항상 확인
- **DQM 환경**: feedernet 내부 전용 인프라. 외부 접근 불가 (DNS NXDOMAIN).
  - DQM ATLAS: `api.feedernet.co.kr/atlas/v2.7.6/...`
  - Docker 관리: `proxy.feedernet.kr/...`
  - 각 기관 CDM: PostgreSQL (db=omop)
  - 37개 기관 DQM 존재 (우리 연구 참여 기관보다 많음)
  - 커스텀 쿼리 실행하려면 에비드넷 관리자 협조 필요
  - 상세 정보: `atlas_auto_cmdata/SENSITIVE_DO_NOT_COMMIT/` (git 미포함)

---

## 2. feedernet API 구조

### 2.1 인증

```python
client.login_portal(email, password)
# → POST /api/v1/auth/login → session cookie 자동 관리
```

### 1.2 기관 ATLAS 접속

```python
client.connect_site(group_id, site_id)
# WebAPI URL: /api/v1/atlas/{group_id}/{site_id}/{endpoint}
```

- 기관별 group_id, site_id는 `/api/v1/dashboard/organizations`에서 확인
- ATLAS 버전별 별도 site_id 존재 (v2.7.6, v2.12.0 등)

### 1.3 포탈 vs ATLAS WebAPI

| API | URL 패턴 | 용도 |
|-----|---------|------|
| **포탈 API** | `/api/v1/projects/{pid}/...` | 프로젝트 관리, 실행 트리거, 결과 다운로드 |
| **ATLAS WebAPI** | `/api/v1/atlas/{gid}/{sid}/...` | 코호트, Estimation, Characterization |

**주의**: 포탈 API에서 `project`(단수)와 `projects`(복수) 혼용됨
- 실행 트리거: `/api/v1/project/{pid}/analysis/{aid}/execution` (단수)
- 분석 목록: `/api/v1/projects/{pid}/analysis` (복수)

---

## 2. 기관 매핑 (v2.12.0)

### 2.1 전체 기관 목록 (24개)

| # | group_id | site_id | CDM코드 | 기관명 | 최신 Source |
|---|---------|---------|---------|--------|-----------|
| 1 | 3 | 190 | PNUH | 부산대학교병원 | PNUH_5.3.0_04 |
| 2 | 4 | 201 | KDH | 강동성심병원 | KDH_5.3.1_08 |
| 3 | 5 | 197 | EUMC | 이화의료원(목동,서울) | EUMC_5.3.1_07 |
| 4 | 7 | 203 | KHNMC | 강동경희대학교병원 (본원) | KHNMC_5.3.1_08 |
| 5 | 9 | 191 | AUMC | 아주대학교병원 | AUMC_5.3.1_11 |
| 6 | 10 | 213 | KWMC | 강원대학교병원 | KWMC_5.3.1_09 |
| 7 | 11 | 202 | KHMC | 경희의료원 | KHMC_5.3.1_07 |
| 8 | 13 | 188 | WKUH | 원광대학교병원 | WKUH_5.3.1_07 |
| 9 | 16 | 196 | DCMC | 대구가톨릭대학교병원 | DCMC_5.3.1_06 |
| 10 | 18 | 202 | CHAMC | 차의과학대 | CHAMC_5.3.1_03 |
| 11 | 27 | 209 | SCHSU | 순천향대 서울병원 | SCHSU_5.3.3_03 |
| 12 | 28 | 207 | SCHCA | 순천향대 천안병원 | SCHCA_5.3.3_03 |
| 13 | 29 | 206 | SCHBC | 순천향대 부천병원 | SCHBC_5.3.1_03 |
| 14 | 30 | 208 | SCHGM | 순천향대 구미병원 | SCHGM_5.3.3_03 |
| 15 | 67 | 204 | MJH | 명지병원 | MJH_5.3.1_06 |
| 16 | **93** | 226 | JCMJ | 제천명지병원 | JCMJ_5.3.1_04 (구 ATLAS: group=69/DKUH) |
| 17 | 81 | 222 | ISH | 국제성모병원 | ISH_5.3.1_05 |
| 18 | 86 | 224 | GNUCH | 창원경상국립대학교병원 | GNUCH_5.3.1_06 |
| 19 | 88 | 198 | GNUH | 경상국립대학교병원 | GNUH_5.3.1_07 |
| 20 | 91 | 225 | KCCH | 원자력병원 | KCCH_5.3.1_05 |
| 21 | 95 | 227 | CHNUH | 충남대학교병원 | CHNUH_5.3.1_01 |
| 22 | 99 | 243 | UUH | 울산대학교병원 | UUH_5.3.0_04 |
| 23 | 103 | 235 | DSMC | 동산병원(대구동산) | DSMC_5.3.1_06 |
| 24 | 117 | 256 | HUMC | 동탄성심병원 | HUMC_DONGTAN_5.3.1_04 |

### 2.2 분석에 포함된 14개 기관 (확정)

CAUHS (3.4년, N=917), DAEGU_DONGSAN_06 (4.2년, N=194) 제외.

| # | CDM코드 | 기간 | N | Target |
|---|---------|------|--:|-------:|
| 1 | AUMC | 1995-2025 (30.0y) | 13,184 | 3,570 |
| 2 | CHNUH | 2013-2021 (8.9y) | 3,905 | 780 |
| 3 | DCMC | 2006-2025 (19.6y) | 4,980 | 748 |
| 4 | GNUCH | 2017-2025 (8.5y) | 1,091 | 381 |
| 5 | GNUH | 2010-2025 (14.9y) | 3,433 | 502 |
| 6 | HUMC | 2014-2025 (11.8y) | 5,912 | 2,510 |
| 7 | ISH | 2015-2025 (10.5y) | 3,185 | 1,194 |
| 8 | JCMJ | 2012-2025 (12.7y) | 1,959 | 1,108 |
| 9 | KDH | 2003-2025 (22.1y) | 7,963 | 3,904 |
| 10 | KHNMC | 2007-2025 (18.0y) | 9,715 | 4,037 |
| 11 | KWMC | 2004-2025 (21.8y) | 5,167 | 2,095 |
| 12 | SCHCA | 2007-2024 (16.8y) | 6,358 | 1,389 |
| 13 | SCHGM | 2007-2024 (17.0y) | 4,025 | 2,640 |
| 14 | SCHSU | 2003-2024 (20.8y) | 4,214 | 1,740 |

### 2.3 API 참조 패키지 (`tool_package/`)

feedernet/ATLAS API 사용이 가능한 이유: `tool_package/`에 원본 패키지 소스가 있어 API 엔드포인트, 파라미터 구조를 직접 참조 가능.

| 패키지 | 역할 |
|--------|------|
| `WebAPI-master` | ATLAS WebAPI 엔드포인트 구조 (cohort, estimation, characterization, vocabulary) |
| `evidnet` | feedernet 포탈 API 구조 (project, analysis, execution) |
| `Data2Evidence-develop` | estimation/characterization 실행 구조 |
| `Hades-main` | OHDSI R 패키지 전체 구조 |
| `Cyclops-main` | PS fitting 로직 |
| `EmpiricalCalibration-main` | NC calibration |
| `OmopVocabularyKorea-master` | 한국 CDM 용어 매핑 |
| `TheBookOfOhdsiKorea-master` | OHDSI 방법론 한국어 번역 |

### 2.4 기관별 ID 체계 (4종)

feedernet에서 기관을 식별하는 ID가 **4가지** 존재하며, 모두 다름:

| ID | 용도 | 예시(KHNMC) |
|---|---|---|
| **group_id** | ATLAS WebAPI 접속 (`connect_site(group_id, site_id)`) | 7 |
| **site_id (=atlasId)** | ATLAS 인스턴스 | 203 |
| **portal orgId** | feedernet 포탈 기관 식별 | 14 |
| **cdmId** | feedernet execution 대상 CDM | 583 |

전체 매핑: `atlas_auto_cmdata/site_id_mapping_full.csv` (23개 기관)

### 2.4 Source 선택 규칙

- 기본: static DB 중 최신 (`sourceName` 끝 `_숫자`가 가장 큰 것)
- 제외: `_monthly`, `_weekly`
- 코드: `get_latest_static_source()` — `re.search(r'_(\d+)$', sourceName)`

---

## 3. 연구 실행 파이프라인

### 3.1 Estimation 실행 흐름

```
1. POST /api/v1/projects/{pid}/analysis           → analysis 생성
2. GET  /api/v1/projects/{pid}/analysis/{aid}/atlas → 기관 목록
3. GET  .../atlas/{atlasId}                         → estimation 목록
4. POST .../atlas/{atlasId}                         → estimation import
   body: {atlasResearchId, atlasResearchName, researchType: "ESTIMATION"}
5. POST /api/v1/project/{pid}/analysis/{aid}/execution → 실행 트리거
   body: {researchName, executionType: "ESTIMATION", cdmIds: [...]}
```

### 3.2 상태 확인 / 결과 다운로드 / 취소

```python
GET  /api/v1/project/{pid}/analysis/{aid}/execution         # 상태
GET  .../execution/{eid}/files/{fid}/download                # 결과
DELETE /api/v1/project/{pid}/analysis/{aid}/execution        # 취소 (body: {executionId})
```

상태값: `EXECUTING_DOCKER`, `WAITING`, `FINISHED_SUCCESSFULLY`, `FINISHED_WITH_ERROR`, `CANCELED`

---

## 4. Characterization API

### 4.1 Feature Analysis 유형

| 유형 | 특징 | API 생성 |
|------|------|:--------:|
| **PRESET** | 내장 분석 (시간 구간 고정) | ❌ 수정 불가 |
| **CRITERIA_SET** | criteria 기반 커스텀 | ⚠️ copy+PUT만 가능 |
| **CUSTOM_FE** | SQL 직접 작성 | ✅ POST 가능, 실행 실패 |

### 4.2 CRITERIA_SET 생성: copy + 2단계 PUT

```python
# Step 1: 기존 FA 복사
GET /feature-analysis/{id}/copy → 새 FA (id 자동 부여)

# Step 2a: PUT — 이름 + 시간 구간
PUT /feature-analysis/{new_id} (name, StartWindow 변경)

# Step 2b: PUT — concept
PUT /feature-analysis/{new_id} (CodesetId, conceptSets 변경)
```

**한번에 하면 500 에러** → 반드시 2단계로 분리.

### 4.3 시간 구간 설정

```json
"StartWindow": {
    "Start": {"Days": 1, "Coeff": 1},   // Coeff: +1=after, -1=before index
    "End": {"Days": 30, "Coeff": 1},
    "UseIndexEnd": false, "UseEventEnd": false
}
```

### 4.4 Distribution 통계 얻기

- `criteriaType`: **WindowedCriteria** (CriteriaGroup 아님)
- `statType`: **DISTRIBUTION**
- `aggregate`: **Value as number (id=7)**
- 결과: mean, SD, median, P25, P75, min, max

### 4.5 다기관 배포: export → import

```python
GET  /cohort-characterization/{id}/export   → KHNMC에서 전체 JSON
POST /cohort-characterization/import        → 타 기관에 import (코호트+FA 자동 생성)
POST /cohort-characterization/{new_id}/generation/{sourceKey}  → 실행
```

검증: KHNMC→GNUCH export/import 성공 (6분 완료, N 비례).

### 4.6 PRESET FA 방식 (확정, 2026-04-15)

**CRITERIA_SET(copy+PUT) 방식은 concept이 안 잡히는 문제 발견** → PRESET FA 방식으로 전환.

`MeasurementValueLongTerm` (PRESET id=42)을 사용하면:
- concept별 자동 분리 (모든 measurement가 개별 행으로 산출)
- mean, SD, median, Q1, Q3, min, max, P10, P90 전부 포함
- export/import 시 concept 소실 없음

**핵심: PRESET FA의 시간 구간은 Characterization의 `parameters`로 제어한다.**
기본값(longTermStartDays=-365, endDays=0)을 원하는 구간으로 오버라이드.
단, endDays는 Long/Medium/Short 3개 window가 공유하므로, 구간별 별도 Characterization 생성:

| Characterization | longTermStartDays | endDays | 구간 |
|---|---|---|---|
| Bio_Pre365 | -365 | -1 | 수술 전 |
| Bio_Post1_30 | 1 | 30 | 급성기 |
| Bio_Post31_90 | 31 | 90 | 아급성기 |
| Bio_Post91_365 | 91 | 365 | 단기만성 |
| Bio_Post1y3y | 366 | 1095 | 중기 |

**AnyTimePrior(id=63)**: startDay 조절 불가 (전체 과거 고정). CDM Inventory 용도로 사용.

### 4.7 PRESET FA ID 참조

PRESET FA 목록은 `atlas_preset_fa_list.csv` (105개)에 저장. 주요 ID:

| ID | 이름 | statType | 용도 |
|----|------|----------|------|
| 42 | Measurement Value Long Term | DISTRIBUTION | **바이오마커 기술통계 (시간구간 지정)** |
| 58 | Measurement Value Short Term | DISTRIBUTION | 바이오마커 (Short term) |
| 61 | Measurement Value Medium Term | DISTRIBUTION | 바이오마커 (Medium term) |
| 63 | Measurement Value Any Time Prior | DISTRIBUTION | **CDM Inventory (전체 기간)** |
| 74 | Demographics Gender | PREVALENCE | 성별 |
| 71 | Demographics Age Group | PREVALENCE | 연령 |
| 49 | Charlson Index | DISTRIBUTION | CCI |

**주의**: Characterization API로 직접 생성(`POST /cohort-characterization`)하면 FA가 비어있을 수 있음. **반드시 export → import 방식**으로 생성해야 FA가 정상 등록됨.

### 4.8 기관별 concept ID 차이

- CBC 항목: 절대값(#/volume) vs 백분율(/100 leukocytes) 기관마다 다름
- Glucose: 일반(3004501) vs 공복(3037110)
- 취합 시: 전 기관 결과 전수 조사 후 다수 기관이 쓰는 concept 기준으로 통일
- 매핑 테이블: `atlas_auto_cmdata/biomarker_concept_mapping.csv`
- PRESET FA 목록: `atlas_auto_cmdata/atlas_preset_fa_list.csv`

**★ 바이오마커 outcome 코호트 재설계 필요 (2026-04-15 발견)**:

같은 검사인데 기관마다 다른 LOINC concept ID를 사용하는 경우, outcome 코호트의 concept set에 **모든 변이 concept을 OR 조건**으로 포함해야 함. 단일 concept만 넣으면 해당 concept이 없는 기관에서 이벤트 0이 됨.

예: Neutrophils %
- 3017354: Segmented neutrophils/100 leukocytes (KHNMC, GNUCH, GNUH, JCMJ, KHNMC)
- 3018010: Neutrophils/100 leukocytes (AUMC, KDH, HUMC)
- 둘 다 같은 단위(%), 같은 cutoff(>70) → concept set에 둘 다 포함

**OR 필요한 concept (7개 기관 기준)**:

| Biomarker | Concept A | Concept B | Cutoff | 해당 기관 |
|---|---|---|---|---|
| WBC | 3000905 | 3010813 | >11 (10³/μL) | KDH=A, 나머지=B |
| Neutro% | 3017354 (Seg.) | 3018010 | >70 (%) | AUMC/KDH/KHNMC=B |
| Mono% | 3002385 | 3019069 | >12 (%) | HUMC=A |
| Glucose | 3004501 | 3037110 (fasting) | ≥126 (mg/dL) | HUMC=B |

나머지 12개 바이오마커는 전 기관 concept 동일.
기관별 상세: `atlas_auto_cmdata/biomarker_concept_by_site.csv`
Achilles frequency: `atlas_auto_cmdata/concept_frequency/{기관}_measurement.csv`

**최종 확정: 22개 바이오마커, 13개 기관 (2026-04-15)**

AUMC, CHNUH, DCMC, GNUCH, HUMC, ISH, JCMJ, KDH, KHNMC, KWMC, SCHCA, SCHGM, SCHSU.
GNUH 제외 (CRP 없음). GFR 제외 (2개 기관 누락). ANA는 estimation에 포함하되 characterization 기술통계는 제외 (ValueAsConcept).

OR multi-concept 코호트 7개: WBC, Neutro, Mono, GlucDM, GlucPreDM, Hgb (+ GFR 제외됨)
기존 코호트 15개: 단일 concept 그대로 사용.

**Characterization 기술통계 보고 방침**:
- 단위 동일한 OR (WBC, Glucose, Hgb): 합산 보고
- 단위 다른 OR (Neutro %, Neutro #, Mono %, Mono #): **분리 보고**
- ANA: 기술통계 제외

**주의: Concept 참조는 반드시 CONCEPT_ID 기준**. LOINC CONCEPT_CODE로 조회/매핑하지 말 것 — 코드 혼동으로 잘못된 concept을 넣는 실수 발생함 (3002385 RDW를 Mono로 오인한 사례).

**절차**:
1. 위 바이오마커 outcome 코호트의 concept set에 변이 concept을 OR로 포함
2. cutoff 동일 확인 (단위 같으면 OK, 다르면 별도 cutoff)
3. Achilles frequency로 기관별 concept 존재 여부 사전 검증
4. feedernet에서 재실행

### 4.11 Outcome 코호트 v2 변경 내역 (2026-04-15 확정)

**13개 기관, 33개 outcome (clinical 11 + biomarker 22)**

Clinical 수정 2건:
| 코호트 ID | 변경 | 이유 |
|----------|------|------|
| 1270 O07_T2DM_v2 | Fasting glucose(3037110) ≥126 OR 추가 | HUMC 등에서 fasting concept만 있는 기관 커버 |
| 1271 O06_AcuteMI_v2 | Inpatient Visit 조건 제거 | 이벤트 수 확보 (입원 제한으로 과소 추정) |

Biomarker 수정 7건:
| 코호트 ID | Concepts (OR) | Cutoff |
|----------|--------------|--------|
| 1262 B_WBC_v2 | 3000905 + 3010813 | >11 (×10³/μL) |
| 1263 B_Neutro_v2 | 3017354 + 3018010 (%) + 3017732 (#) | >70% / >7.7 |
| 1265 B_GlucDM_v2 | 3004501 + 3037110 | ≥126 (mg/dL) |
| 1266 B_Mono_v3 | 3019069 (%) + 3001604 (#) | >12% / >0.8 |
| 1267 B_GlucPreDM_v2 | 3004501 + 3037110 | 100-125 (mg/dL) |
| 1268 B_Hgb_v2 | 3000963 + 3027484 | <12 (g/dL) |

Clinical 기존 유지 9건: UC(81893), CD(201606), Asthma(317009), Atopic(133834), RA(80809), CDI(193688), Parkinson(381270), BilCalc(4145627), CRC(197500+74582)
— condition은 includeDescendants로 기관 간 차이 커버됨.

Biomarker 기존 유지 15건: Lympho(3002030), Eosino(3006504), Baso(3022096), CRP(3020460), ESR(3015183), RF(3021614), ANA(3029103), HbA1c(3004410), LDL(3028437), TG(3022192), HDL(3007070), UA(3037556), ALT(3006923), GGT(3026910), ALP(3035995)

### 4.9 CDM Measurement Inventory (2026-04-15)

**목적**: 다음 연구 시 기관별 데이터 검증 없이 바로 사용할 수 있도록, 전 기관 measurement concept + unit + 기술통계를 미리 수집.

- **코호트**: CDM_AnyVisit (모든 방문 환자, cohort id=1259 KHNMC)
- **FA**: Measurement Value Any Time Prior (PRESET id=63)
- **배포**: 23개 기관 (DKUH 제외)
- **결과**: 기관별 모든 measurement concept의 N, mean, SD, median, Q1, Q3
- 배포 기록: `atlas_auto_cmdata/cdm_inventory_v3_deploy.json`

### 4.10 수동 다운로드

ATLAS 웹 UI CSV에 min, P10, P25, median, P75, P90, max 포함.
API result에는 mean/count만 나오는 경우 있음 → UI 다운로드가 더 상세.

---

## 5. Achilles 결과 활용

```python
GET /cdmresults/{sourceKey}/{domain}                    # concept별 frequency
GET /cdmresults/{sourceKey}/measurement/{conceptId}     # value distribution
```

domain: condition, drug, procedure, measurement, observation, visit.
Distribution: min, P10, P25, median, P75, P90, max. **CDM 전체 환자** 대상 (코호트 특이적 아님).

**★ Unit 차이 주의 (2026-04-15 발견)**:

| 바이오마커 | Unit 변이 | cutoff 영향 | 대응 |
|-----------|----------|-----------|------|
| **CRP** | mg/dL vs mg/L | **10배** | **코호트 2개 분리**: 1274(>0.8 mgdL) + 1275(>8 mgL), 기관별 선택 |
| **Neutro#** | 10³/μL vs /μL (AUMC,ISH,KHNMC) | **1000배** | **코호트 2개 분리**: 1276(>7.7 thou) + 1277(>7700 uL), 기관별 선택 |
| ALT/GGT/ALP | U/L vs IU/L | 없음 (동일) | |
| RF | IU/mL vs U/mL | 없음 (동일) | |

기관별 unit 상세: `atlas_auto_cmdata/biomarker_units_by_site.csv`

**23개 기관 × 5 domain Achilles 수집 완료** (2026-04-15):
저장 위치: `atlas_auto_cmdata/concept_frequency/{기관코드}_{domain}.csv`
신규 연구 시 기관별 concept 가용성 확인은 이 파일을 먼저 참조.
한계: 해당 concept 직접 빈도만 반환, descendant는 별도 검색 필요.

---

## 6. 분석 방법론

### 6.1 IPD Pooled Analysis (Main)

- **데이터**: 다기관 CmData (SQLite) — result.zip에서 추출
- **PS**: Cyclops (Laplace prior, cross-validation) + site dummy covariate
- **매칭**: 1:1 nearest-neighbor, caliper = 0.2 × SD(logit PS)
- **Outcome model**: Site-stratified Cox proportional hazard regression
- **공변량 (이번 연구)**: Demographics(Gender, AgeGroup) + ConditionLongTerm + DrugLongTerm → 7,751 covariates

### 6.2 시간 구간별 분석 (Landmark)

PS matching은 1회만 → 매칭된 동일 코호트에서 시간 구간별 Cox.

| 구간 | 기간 | 목적 |
|------|------|------|
| 1-30d | 급성기 | 수술 스트레스 (모든 수술군 동일 예상) |
| 31-90d | 아급성기 | 스트레스 회복 후 차이 시작 |
| 91-365d | 단기 만성 | 충수 특이적 효과 |
| 366-1095d | 중기 | 면역 shift 지속 여부 |
| 1096-3650d | 장기 | 장기 면역 변화 |
| 1-3650d | 전체 | reference |

```r
# 구간별 로직 핵심
oc <- outcomes[daysToEvent >= windowStart & daysToEvent <= windowEnd]
df <- df[df$maxFollow >= windowStart]  # 구간까지 생존한 환자만
df$time <- pmin(daysToObsEnd, windowEnd) - windowStart + 1
```

**해석**: 급성기에서만 유의 → 수술 스트레스. 91d+ 유의 → 충수 특이적.

### 6.3 Characterization (보조 기술통계)

- WindowedCriteria + DISTRIBUTION + Value as number → mean, SD, median, Q1, Q3
- 다기관 통합: **weighted mean ± pooled SD** (기관별 N, mean, SD로 계산)
- median/Q1/Q3는 기관별 개별 보고 (supplementary)

### 6.4 Negative Control Calibration

- 48+ NC outcomes, EmpiricalCalibration 패키지
- NC HR 분포 기준: median ≈ 1.0, 유의 비율 ≈ 5%
- vs GenPop은 bias 심함 (median 0.654, 27.7% 양성) → vs Chol, vs Hernia가 primary

### 6.5 분석 규모 (충수절제술 연구, v2 확정)

| 항목 | 수 | 비고 |
|------|---:|------|
| 기관 | 13 | GNUH 제외 (CRP 없음) |
| 비교군 | 2 primary + 1 supplementary | vs Chol, vs Hernia (primary) / vs GenPop (supplementary) |
| Clinical outcomes | 11 | AMI v2 (입원 제거), T2DM v2 (fasting glucose 추가) |
| Biomarker outcomes | 22 | GFR 제외, 6개 multi-concept OR |
| 시간 구간 | 6 | |
| Negative controls | 48+ | |

---

## 7. 이슈 사항 & 해결 방법

### 7.1 R 패키지 호환성

| 문제 | 원인 | 해결 |
|------|------|------|
| `loadCohortMethodData` 실패 | Andromeda 1.x가 0.6.0 형식 못 읽음 | **Andromeda 0.6.0** |
| FeatureExtraction 로드 실패 | Andromeda >= 1.0.0 요구 | **FeatureExtraction 3.2.0** |
| CohortMethod 설치 실패 | Rtools 미설치 | **Rtools 4.5** |
| rJava 로드 실패 | JAVA_HOME 미설정 | **JDK 21 + JAVA_HOME** |
| `no slot of name "conn_ref"` | duckdb가 RSQLite dispatch 오염 | **duckdb 제거** |
| Rtools "cc1 not found" | gcc libexec 경로 누락 | **R 내 PATH 설정** |
| sparse→dense 메모리 폭발 | Cyclops PS fitting | CohortMethod 내부 함수 사용 (sparse 유지) |

### 7.2 R 스크립트 실행 ��경

**원칙: R 스크립트는 VS Code R 터미��에서 `source()`로 실행한다.**

bash에서 `Rscript`로 호출하면 JAVA_HOME 누락, 메모리 경합(Claude+VSCode가 2GB+ 점유) 등 불필요한 문제가 발생한다. VS Code R 터미널은 사용자 환경변수가 자동 적용되고 메모리도 안정적이다.

```r
# VS Code R 터미널���서 실행
source("C:/Users/data1/Desktop/atlas_auto_cmdata/ipd_10sites_bio.R")
```

메모리 부족 시에만 `rm() + gc()`로 대응하면 된다.

### 7.3 기관 변동 시 민감도 분석 원칙

기관 수를 변경(제외/추가)하여 재분석할 때는 **반드시 최종 단계(NC + Calibration)까지 완료한 후 비교**한다. Calibration 전 raw HR만으로 비교하면 bias 보정 없이 판단하게 되어 의미 없다.

```
1. v7b (clinical) → 2. biomarker → 3. NC → 4. calibration → 5. 비교
```

중간 단계(예: raw HR)에서 비교하지 말 것.

**핵심**: CmData 생성 시 패키지 버전과 분석 시 버전을 **일치**시켜야 함.

### 7.4 Characterization API 이슈 (2026-04-15 발견)

| 문제 | 원인 | 해결 |
|------|------|------|
| CRITERIA_SET FA에 concept 안 잡힘 | copy+PUT으로 conceptSets 설정해도 실행 시 `any_measurement`로 합산 | **PRESET FA 방식으로 전환** |
| `POST /cohort-characterization`로 생성하면 FA 비어있음 | 직접 POST는 FA 참조가 안 됨 | **export → import 방식으로만 생성** |
| PRESET FA id=41을 `MeasurementValueAnyTimePrior`로 오인 | id=41은 `Distinct Condition Count Long Term` | **PRESET FA 목록 참조 필수** (`atlas_preset_fa_list.csv`) |
| JCMJ group_id 혼동 | 구 ATLAS(group=69, DKUH)와 신 ATLAS(group=93, JCMJ) 공존 | **group=93만 사용, 69는 폐기** |

### 7.5 feedernet API 제약

| 제약 | 상세 |
|------|------|
| 커스텀 zip 업로드 불가 | API로 직접 업로드 안 됨 (415) |
| researchType | ESTIMATION, PREDICTION만 지원 |
| DateAdjustment | ATLAS v2.12.0에서 cohort에 적용해도 무시됨 |
| CUSTOM_FE | FA 생성 되지만 실행 시 SQL 프레임워크 충돌 |
| FA POST | CRITERIA_SET 직접 생성 500 → copy+PUT만 가능 |
| statType PUT | 500 에러 → aggregate id만 변경 가능 |

### 7.6 기관 서버 이슈

| 유형 | 증상 | 원인 |
|------|------|------|
| HTTP -1 | 즉시 실패 | 서버 다운 / 방화벽 |
| 504 Timeout (180s) | nginx 타임아웃 | 서버 과부하 |
| NO SOURCE | sources 빈 배열 | CDM source 미등록 |
| FAILED (즉시) | 시작시간 없이 실패 | CDM 환경 문제 |
| FAILED (수분) | 수분 후 실패 | R 의존성 / 코호트 없음 |

---

## 8. R 환경 설정

| 항목 | 값 |
|------|-----|
| R | 4.5.2 |
| Rtools | 4.5 (C:\rtools45) |
| Java | JDK 21 (C:\Users\data1\java\jdk-21.0.10+7) |
| CohortMethod | 4.2.2 (CmData 호환) |
| Andromeda | 0.6.0 (CmData 호환) |
| FeatureExtraction | 3.2.0 |
| Cyclops | latest |
| duckdb | **제거 필수** (RSQLite 충돌) |
| ATLAS | v2.12.0 (feedernet) |
| CmData 경로 | C:\Users\data1\Desktop\atlas_auto_cmdata\ |

---

## 9. 실행 기록

### 9.1 Analysis 10957: v7b_noStop

**Package**: E01_E04_clinical_ms_v7b_maxCohort50k_noStop | maxCohortSize=50000, stopOnError=false

| CDM | 기관 | 상태 | execId |
|-----|------|:----:|--------|
| AUMC_5.3.1_11 | 아주대 | COMPLETE | 242052 |
| CAUHS_5.3.1_03 | 중앙대 | COMPLETE | 242045 |
| CHNUH_5.3.1_01 | 충남대 | COMPLETE | 242043 |
| DAEGU_DONGSAN_06 | 대구동산 | COMPLETE | 242233 |
| DCMC_5.3.1_06 | 대구가톨릭대 | COMPLETE | 242604 |
| GNUCH_5.3.1_06 | 창원경상국립대 | COMPLETE | 242044 |
| GNUH_5.3.1_07 | 경상국립대 | COMPLETE | 242474 |
| HUMC_DONGTAN_04 | 동탄성심 | COMPLETE | 242475 |
| ISH_5.3.1_05 | 국제성모 | COMPLETE | 242476 |
| JCMJ_5.3.1_04 | 제천명지 | COMPLETE | 242477 |
| KDH_5.3.1_08 | 강동성심 | COMPLETE | 242479 |
| KHNMC_5.3.1_08 | 본원 | COMPLETE | 242603 |
| KWMC_5.3.1_09 | 강원대 | COMPLETE | 242482 |
| SCHCA_5.3.3_03 | 순천향 천안 | COMPLETE | 242602 |
| SCHGM_5.3.3_03 | 순천향 구미 | COMPLETE | 242494 |
| SCHSU_5.3.3_03 | 순천향 서울 | COMPLETE | 242048 |
| SCHBC_5.3.1_03 | 순천향 부천 | RUNNING | 242485 |
| KHMC_5.3.1_07 | 경희의료원 | RUNNING | 242480 |
| EUMC_5.3.1_07 | 이화의료원 | FAILED | 242046 |
| KYUH_5.3_01 | 건양대 | FAILED | 242599 |
| MJH_5.3.1_06 | 명지 | FAILED | 242598 |
| SEJONG_BCN/ICN | 세종 | FAILED | — |

### 9.2 Analysis 10961: biomarker_v1

**Package**: B01_B23_biomarker_ms_v1 | maxCohortSize=50000, stopOnError=false

분석 포함 16개 기관 중 COMPLETE 17 / RUNNING 5 / WAITING 2 / FAILED 5 (2026-04-14 기준).
상세 execId: execution_records 삭제 전 백업 참조 또는 feedernet API로 실시간 조회.

### 9.3 Analysis 11000/11001: v8 full (2026-04-15)

clinical_v8 + biomarker_v2 전체 outcome. 13+2기관(EUMC/KHMC 추가) 실행 중.

### 9.4 Analysis 11003/11004: v8 changed only (2026-04-15)

**변경된 outcome만 별도 estimation**으로 분리 실행 — 실행 시간 단축.
- 11003 (clinical): 1270(T2DM v2), 1271(AMI v2) — 2 outcomes
- 11004 (biomarker): 1262(WBC), 1263(Neutro), 1266(Mono), 1265(GlucDM), 1267(GlucPreDM), 1268(Hgb) — 6 outcomes
- 13개 기관 실행 중. 변경 안 된 outcome은 기존 v7b/v1 result 재사용.

### 9.5 Characterization: PRESET × 5구간

PRESET MeasurementValueLongTerm × 5 시간 구간, parameters 오버라이드.
13개 기관 배포 완료. Achilles 재수집 + multi-concept OR 후 13개 기관 확정.

---

## 10. 2026-04-15 발견/오류/수정 전체 기록

### 10.1 발견 사항

| # | 발견 | 영향 | 대응 |
|---|------|------|------|
| 1 | CRITERIA_SET FA에서 concept이 안 잡힘 (any_measurement로 합산) | Bio17 Characterization 14개 기관 전부 무효 | PRESET FA 방식으로 전환 |
| 2 | 기관별 measurement concept ID가 다름 (Neutro %, #/vol 등) | estimation에서 일부 기관 이벤트 0 | multi-concept OR 코호트 설계 |
| 3 | Achilles measurement 파일 6개 기관 누락 | 7개 기관으로 오판 (실제 13개 가용) | Achilles API 재수집 → 13개 확정 |
| 4 | concept 3002385를 Monocytes로 오인 | 실제는 RDW (적혈구분포폭) | 정확한 concept 3001604로 교체 |
| 5 | Hgb estimation concept(3027484)과 Achilles 주력 concept(3000963) 불일치 | Hgb 이벤트 누락 가능 | multi-concept OR (둘 다 포함) |
| 6 | ANA는 ValueAsConcept (양성/음성) 방식 | Characterization 기술통계 불가 | estimation만 포함, 기술통계 제외 |
| 7 | Acute MI 코호트에 Inpatient Visit 제한 | 이벤트 수 과소 추정 | 입원 조건 제거 (v2) |
| 8 | T2DM Lab 확인에 Fasting glucose(3037110) 누락 | 일부 기관에서 lab 확인 실패 | OR로 추가 (v2) |
| 9 | vs GenPop comparator maxCohortSize=50K capping | 리뷰어 지적 가능 | supplementary로 이동 |
| 10 | feedernet estimation POST로 직접 생성 500 에러 | cohortDefinitions 누락 | ATLAS copy+PUT 방식으로 우회 |
| 11 | feedernet cdmId ≠ atlasId ≠ group_id | execution API에서 CDM not found | 기존 execution에서 cdmId 매핑 추출 |
| 12 | feedernet estimation 서버 불안정으로 즉시 실패 | 일부 기관 FINISHED_WITH_ERROR | 재실행 |

### 10.2 기록 우선순위

변동사항을 기록할 때 **재사용 가치가 높은 것부터** 기록한다:

1. **ID 매핑, 인프라 정보** — 기관별 4종 ID, source 매핑 등. 신규 연구 때 가장 먼저 필요하고, 없으면 매번 헤맴
2. **API 제약/우회법** — feedernet/ATLAS에서 안 되는 것과 대안. 시행착오 방지
3. **concept 매핑** — 기관별 measurement/condition concept 차이. 연구 설계의 핵심
4. **분석 방법론** — PS matching, calibration 등. 코드에 이미 있으므로 후순위
5. **실행 기록** — 특정 연구의 상태. 일시적이므로 최하 우선순위

원칙: **"다음 연구에서 처음부터 다시 찾아야 하는 정보"가 가장 중요하다.**

### 10.3 구조적 교훈

1. **데이터 검증을 estimation 전에 수행** — Achilles로 기관별 concept 전수 조사 후 기관 선정
2. **measurement concept은 descendant 없음** — condition과 달리 OR로 변이 concept을 직접 포함해야 함
3. **concept 참조는 CONCEPT_ID 기준** — LOINC CONCEPT_CODE로 매핑하면 오류 발생
4. **변경된 outcome만 별도 estimation** — 전체를 다시 돌릴 필요 없이 변경분만 분리 실행 가능
5. **Characterization은 PRESET FA + parameters 오버라이드** — CRITERIA_SET copy+PUT은 concept 소실
6. **feedernet ID 체계**: group_id(ATLAS) ≠ orgId(feedernet portal) ≠ cdmId(execution) — 매핑 필수

---

## 10. 분석 파이프라인 템플릿

### 10.1 새 연구 시작 순서

```
1.  ATLAS에서 cohort 정의 + estimation 설계
1b. 공변량 설정 검토 (builder.py covariate_settings — 연구마다 다름)
2.  ★ 기관별 데이터 검증 (concept 가용성 + unit 통일 확인)
    → PRESET Characterization으로 전 기관 measurement 전수 조사
    → 바이오마커 concept ID/unit이 통일된 기관만 분석에 포함
3.  feedernet analysis 생성 + ATLAS import
4.  전체 기관 execution 트리거
5.  Cloud monitoring 설정 (GCP Cloud Function)
6.  완료 기관 result.zip 다운로드
7.  CmData 추출 (zip → SQLite)
8.  IPD pooled analysis (Cyclops PS + Cox)
9.  시간 구간별 분석 (필요 시)
10. Negative control calibration
11. Characterization (보조 기술통계)
12. 결과 정리 + 논문
```

**교훈 (충수절제술 연구)**: 14개 기관으로 시작했으나, Characterization 결과 CBC 항목 concept이 통일된 기관은 7개뿐. estimation을 14개로 돌린 후 7개로 다시 돌리는 이중 작업 발생. **데이터 검증을 먼저 하면 방지 가능.**

### 10.2 주요 스크립트

| 스크립트 | 용도 |
|---------|------|
| `ipd_pooled_cyclops_v7.R` | Cyclops PS + 1:N matching + Cox (검증됨) |
| `ipd_cyclops_timewindow.R` | 시간 구간별 HR (landmark) |
| `ipd_cyclops_nc.R` | Negative control HR |
| `run_calibration.R` | EmpiricalCalibration |
| `create_biomarker_fas_v2.py` | Characterization FA 자동 생성 (copy+PUT) |
| `cloud_monitor/main.py` | GCP Cloud Function 모니터링 |

### 10.3 결과 저장 구조

```
C:\Users\data1\Desktop\atlas_auto_cmdata\
├── results_v7b/               # result.zip (기관별)
├── results_biomarker/
├── cmData_v7b/                # CmData SQLite
├── cmData_biomarker/
├── pooled_14sites_v7b/        # 14-site Cyclops HR
├── pooled_14sites_bio/
├── pooled_10sites_v7b/        # 10-site 민감도 분석
├── pooled_10sites_bio/
├── pooled_*_nc/               # Negative control HR
├── calibration_results/       # Calibrated HR
├── concept_frequency/         # 기관별 concept frequency
└── char_*.json                # Characterization 결과
```

---

## 11. 향후 활용

### 11.1 새 연구 적용

이 시스템은 **연구 주제만 바꾸면** 동일 파이프라인으로 실행 가능:

1. **코호트 변경**: ATLAS에서 새 target/comparator/outcome 정의
2. **Estimation 생성**: `atlas_auto` 패키지로 자동 생성
   - **공변량 설정 필수 검토**: `builder.add_cm_analysis(covariate_settings=custom_cov)`
   - 이번 연구 기본값: Demographics(Gender, AgeGroup) + ConditionLongTerm + DrugLongTerm → 7,751 covariates
   - 연구에 따라 Measurement, Procedure, CharlsonIndex, VisitCount 등 추가/변경 필요
   - TCO별 `excluded_covariate_concept_ids`로 특정 concept 제외 가능
3. **실행 + 모니터링**: 동일 API + Cloud Function
4. **분석**: 동일 R 스크립트 (outcome ID만 변경)

### 11.2 시스템 개선 방향

| 개선 사항 | 우선순위 | 설명 |
|----------|:--------:|------|
| feedernet 커스텀 패키지 업로드 | 높음 | 에비드넷 문의 또는 UI 경로 확인 |
| 결과 자동 취합 파이프라인 | 중간 | 다운로드 → 추출 → 분석 → 보고서 |
| 음성 대조군 자동 선택 | 낮음 | CohortMethod NC 선택 자동화 |
| Shiny 대시보드 | 낮음 | 실시간 실행 상태 + 결과 시각화 |

### 11.3 재사용 자산

| 자산 | 위치 | 설명 |
|------|------|------|
| `src/atlas_auto/` | GitHub | feedernet API 클라이언트 (pip installable) |
| `R/pooled_analysis/` | GitHub | IPD pooled analysis 파이프라인 |
| `cloud_monitor/` | GCP | Telegram 알림 모니터링 |
| `docs/` | GitHub | 지식 베이스, 논문, 가이드 |

---

## 12. 연구별 체크리스트

새 연구를 시작할 때:

- [ ] ATLAS에서 코호트 정의 (target, comparator, outcomes, NCs)
- [ ] Estimation 설계 (PS settings, risk window)
- [ ] **공변량 설정 검토** (`builder.py` covariate_settings 커스텀)
- [ ] **★ 기관별 데이터 검증** — PRESET Characterization으로 measurement concept 전수 조사 → concept/unit 통일 가능한 기관만 선정
- [ ] feedernet analysis 생성 + ATLAS import
- [ ] 선정된 기관만 execution 트리거
- [ ] Cloud monitoring 활성화
- [ ] 완료 기관 result.zip 다운로드
- [ ] CmData 추출 (zip → SQLite)
- [ ] R 환경 확인 (패키지 버전 호환성, duckdb 제거)
- [ ] IPD pooled analysis (Cyclops 1:1 PS matching + Cox)
- [ ] 시간 구간별 분석 (필요 시)
- [ ] Negative control HR + EmpiricalCalibration
- [ ] Characterization (보조 기술통계, 필요 시)
- [ ] 결과 정리 + 논문/보고서
