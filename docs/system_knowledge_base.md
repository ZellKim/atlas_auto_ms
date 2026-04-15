# atlas-auto 시스템 지식 베이스

## 목적

이 문서는 feedernet/ATLAS API 활용법, 기관 매핑, 분석 방법론, 이슈 해결, 실행 기록을 **한 곳에** 정리하여 향후 새로운 연구에 재사용 가능한 중앙 지식 저장소입니다.

> **문서 구조 원칙**: 변동사항, 새로 발견한 사항, 이슈 해결은 모두 이 문서에 기록합니다.
> - `PROGRESS.md` — 현재 상태 + TODO만 (간결한 스냅샷)
> - `concept_selection_guide.md` — Concept ID 선정 전용 가이드
> - `paper_draft.md` — 논문 본문
> - `paper_ijs_checklist.md` — 투고 체크리스트

---

## 1. feedernet API 구조

### 1.1 인증

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
| 16 | 69 | 226 | JCMJ | 제천명지병원 | JCMJ_5.3.1_04 |
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

### 2.3 Source 선택 규칙

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

### 4.6 수동 다운로드

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

### 6.5 분석 규모 (충수절제술 연구)

| 항목 | 수 |
|------|---:|
| 기관 (primary) | 14 |
| 비교군 | 3 (Cholecystectomy, General Pop, Hernia repair) |
| Clinical outcomes | 11 |
| Biomarker outcomes | 17 |
| 시간 구간 | 6 |
| Negative controls | 48+ |

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

### 7.3 feedernet API 제약

| 제약 | 상세 |
|------|------|
| 커스텀 zip 업로드 불가 | API로 직접 업로드 안 됨 (415) |
| researchType | ESTIMATION, PREDICTION만 지원 |
| DateAdjustment | ATLAS v2.12.0에서 cohort에 적용해도 무시됨 |
| CUSTOM_FE | FA 생성 되지만 실행 시 SQL 프레임워크 충돌 |
| FA POST | CRITERIA_SET 직접 생성 500 → copy+PUT만 가능 |
| statType PUT | 500 에러 → aggregate id만 변경 가능 |

### 7.4 기관 서버 이슈

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

### 9.3 Characterization: Bio17_PrePost

17 biomarker × 5 time window = 85 FAs. KHNMC에서 생성 → 13개 기관 배포.
2026-04-15 기준: 7/14 완료, 6 실행 중, 1 실패 (JCMJ).

---

## 10. 분석 파이프라인 템플릿

### 10.1 새 연구 시작 순서

```
1.  ATLAS에서 cohort 정의 + estimation 설계
1b. 공변량 설정 검토 (builder.py covariate_settings — 연구마다 다름)
2.  feedernet analysis 생성 + ATLAS import
3.  전체 기관 execution 트리거
4.  Cloud monitoring 설정 (GCP Cloud Function)
5.  완료 기관 result.zip 다운로드
6.  CmData 추출 (zip → SQLite)
7.  IPD pooled analysis (Cyclops PS + Cox)
8.  시간 구간별 분석 (필요 시)
9.  Negative control calibration
10. Characterization (보조 기술통계, 필요 시)
11. 결과 정리 + 논문
```

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
- [ ] feedernet analysis 생성 + ATLAS import
- [ ] 전체 기관 execution 트리거
- [ ] Cloud monitoring 활성화
- [ ] 완료 기관 result.zip 다운로드
- [ ] CmData 추출 (zip → SQLite)
- [ ] R 환경 확인 (패키지 버전 호환성, duckdb 제거)
- [ ] IPD pooled analysis (Cyclops 1:1 PS matching + Cox)
- [ ] 시간 구간별 분석 (필요 시)
- [ ] Negative control HR + EmpiricalCalibration
- [ ] Characterization (보조 기술통계, 필요 시)
- [ ] 결과 정리 + 논문/보고서
