# atlas-auto 시스템 지식 베이스

## 목적

이 문서는 충수절제술 연구를 수행하면서 축적된 feedernet/ATLAS API 활용법, 이슈 사항, 해결 방법을 정리하여 **향후 새로운 연구 주제에 재사용 가능한 시스템**으로 구축하기 위한 것입니다.

---

## 1. feedernet API 구조 (확인 완료)

### 1.1 인증

```python
client.login_portal(email, password)
# → POST /api/v1/auth/login
# → session cookie 자동 관리
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

## 2. 연구 실행 파이프라인 (검증 완료)

### 2.1 Estimation 실행 흐름

```
1. POST /api/v1/projects/{pid}/analysis
   → analysis 생성 (name만)

2. GET  /api/v1/projects/{pid}/analysis/{aid}/atlas
   → 접근 가능한 ATLAS 기관 목록

3. GET  /api/v1/projects/{pid}/analysis/{aid}/atlas/{atlasId}
   → 해당 ATLAS의 estimation 목록

4. POST /api/v1/projects/{pid}/analysis/{aid}/atlas/{atlasId}
   body: {atlasResearchId, atlasResearchName, researchType: "ESTIMATION"}
   → estimation import (feedernet이 ATLAS에서 R 패키지 zip 자동 생성)

5. POST /api/v1/project/{pid}/analysis/{aid}/execution
   body: {researchName, executionType: "ESTIMATION", cdmIds: [...]}
   → 다기관 실행 트리거
```

### 2.2 상태 확인

```python
GET /api/v1/project/{pid}/analysis/{aid}/execution
→ groups[].executionList[].executionStatus
  EXECUTING_DOCKER, WAITING, FINISHED_SUCCESSFULLY, FINISHED_WITH_ERROR, CANCELED
```

### 2.3 결과 다운로드

```python
GET .../execution/{eid}/files → file 목록
GET .../execution/{eid}/files/{fid}/download → result.zip
```

### 2.4 실행 취소

```python
DELETE /api/v1/project/{pid}/analysis/{aid}/execution
body: {executionId}
```

---

## 3. Characterization API (새로 발견)

### 3.1 Feature Analysis 유형

| 유형 | 특징 | API 생성 |
|------|------|:--------:|
| **PRESET** | 내장 분석 (시간 구간 고정) | ❌ 수정 불가 |
| **CRITERIA_SET** | criteria 기반 커스텀 | ⚠️ copy+PUT만 가능 |
| **CUSTOM_FE** | SQL 직접 작성 | ✅ POST 가능, 실행 실패 |

### 3.2 CRITERIA_SET 생성 방법 (검증 완료)

**직접 POST는 안 됨** → `copy` + `PUT` 방식 사용:

```python
# Step 1: 기존 FA 복사
GET /feature-analysis/{id}/copy
→ 새 FA 생성 (id 자동 부여)

# Step 2: PUT으로 수정 (이름, 시간 구간 등)
PUT /feature-analysis/{new_id}
→ 시간 구간, conceptSets, aggregate 변경 가능
```

### 3.3 시간 구간 설정

```json
"StartWindow": {
    "Start": {"Days": 1, "Coeff": 1},   // +1 = after index, -1 = before
    "End": {"Days": 30, "Coeff": 1},
    "UseIndexEnd": false,
    "UseEventEnd": false
}
```

### 3.4 Distribution stat을 얻으려면

- `criteriaType`: **WindowedCriteria** (CriteriaGroup 아님)
- `statType`: **DISTRIBUTION**
- `aggregate`: **Value as number (id=7)**
- 결과: mean, SD, median, P25, P75, min, max

### 3.5 concept별 분류

- `CodesetId = null` → 모든 measurement 합산 (의미 없음)
- `CodesetId = 0` + `conceptSets` 지정 → 특정 concept만

### 3.6 Characterization 실행

```python
POST /cohort-characterization/{id}/generation/{sourceKey}
GET  /cohort-characterization/{id}/generation → status 확인
GET  /cohort-characterization/generation/{genId}/result → 결과 (result, 단수)
```

### 3.7 수동 다운로드

ATLAS 웹 UI에서 다운로드하면 **CSV에 min, P10, P25, median, P75, P90, max** 포함.
API result에는 mean/count만 나오는 경우 있음 → UI 다운로드가 더 상세.

---

## 4. Achilles 결과 활용

### 4.1 Concept Frequency

```python
GET /cdmresults/{sourceKey}/{domain}
→ conceptId, numPersons, percentPersons, recordsPerPerson
```

domain: condition, drug, procedure, measurement, observation, visit

### 4.2 Measurement Value Distribution

```python
GET /cdmresults/{sourceKey}/measurement/{conceptId}
→ measurementValueDistribution: min, P10, P25, median, P75, P90, max
```

**CDM 전체 환자** 대상 (코호트 특이적 아님).

---

## 5. 이슈 사항 & 해결 방법

### 5.1 R 패키지 호환성

| 문제 | 원인 | 해결 |
|------|------|------|
| `loadCohortMethodData` 실패 ('from' and 'to') | Andromeda 1.x가 0.6.0 형식 못 읽음 | **Andromeda 0.6.0 설치** |
| FeatureExtraction 로드 실패 | Andromeda >= 1.0.0 요구 | **FeatureExtraction 3.2.0으로 다운그레이드** |
| CohortMethod 설치 실패 | Rtools 미설치 | **Rtools 4.5 설치** |
| rJava 로드 실패 | JAVA_HOME 미설정 | **JDK 21 설치 + JAVA_HOME 설정** |
| `no slot of name "conn_ref"` | duckdb가 RSQLite dispatch 오염 | **duckdb 패키지 제거** |
| Rtools "cc1 not found" | gcc libexec 경로 누락 | **R 스크립트 내에서 PATH 설정** |

**핵심**: CmData 생성 시 사용한 패키지 버전과 분석 시 사용하는 버전을 **일치**시켜야 함.
- `estimation_model/renv.lock`에서 버전 확인 가능

### 5.2 Characterization 다기관 배포 방법 (2026-04-14 발견)

**핵심: export → import 방식으로 다기관 자동화 가능**

```python
# KHNMC에서 export
GET /cohort-characterization/{id}/export → 전체 JSON (코호트+FA 포함)

# 다른 기관에 import
POST /cohort-characterization/import (body: export JSON)
→ 코호트 + FA 자동 생성
```

**FA 개별 생성 시 제약 (참고)**:
- PRESET copy: 모든 기관에서 500 (IllegalArgumentException)
- POST로 FA 생성: design이 빈 배열로 저장됨
- PUT으로 design 채우기: 한번에 하면 500, **2단계로 나누면 성공** (1차: 시간, 2차: concept)
- WindowedCriteria FA: **UI에서만 최초 생성 가능**, 이후 copy+PUT으로 복제
- **가장 간단한 방법**: UI에서 빈 WindowedCriteria FA 1개 생성 → copy+2단계 PUT

**source 선택 규칙**:
- 기본: static DB 중 최신 (예: `cdmpv53_251128`)
- 제외: `_monthly`, `_weekly` (주기변환 DB)
- sourceKey에서 `m`이나 `monthly/weekly` 포함 여부로 필터

```python
# 최신 static source 선택
sources = client.get_sources()
static = [s for s in sources 
          if not any(k in s['sourceKey'] for k in ['monthly', 'weekly', 'cdmpv53m'])]
latest = sorted(static, key=lambda s: s['sourceKey'])[-1]
```

### 5.3 feedernet API 제약

| 제약 | 상세 |
|------|------|
| 커스텀 zip 업로드 불가 | API로 research zip 직접 업로드 안 됨 (415) |
| researchType | ESTIMATION, PREDICTION만 지원 |
| DateAdjustment | ATLAS v2.12.0에서 cohort에 적용해도 무시됨 |
| CUSTOM_FE | FA 생성은 되지만 Characterization 실행 시 SQL 프레임워크 충돌 |
| Feature Analysis POST | CRITERIA_SET 직접 생성 500 에러 → copy+PUT만 가능 |
| statType 변경 | PUT으로 statType 변경 시 500 → aggregate id만 변경 가능 |

### 5.3 기관 서버 이슈

| 유형 | 증상 | 원인 |
|------|------|------|
| HTTP -1 | 즉시 실패 | 서버 다운 / 방화벽 |
| 504 Gateway Timeout (180s) | nginx 타임아웃 | 서버 과부하 / Achilles 미실행 |
| NO SOURCE | sources 빈 배열 | CDM source 미등록 |
| estimation FAILED (즉시) | 시작시간 없이 실패 | CDM 환경 문제 |
| estimation FAILED (0:07) | 수분 후 실패 | R 패키지 의존성 / 코호트 없음 |

### 5.4 메모리 이슈

- Cyclops PS fitting 시 sparse→dense 변환: 수십 GB 필요
- 해결: CohortMethod 내부 함수 사용 (sparse 유지) 또는 subsampling

---

## 6. 분석 파이프라인 템플릿

### 6.1 새 연구 시작 순서

```
1. ATLAS에서 cohort 정의 + estimation 설계
2. feedernet에서 analysis 생성 + ATLAS import
3. 전체 기관 execution 트리거
4. Cloud monitoring 설정 (GCP Cloud Function)
5. 완료 기관 result.zip 다운로드 (로컬)
6. CmData 추출 (zip → SQLite)
7. IPD pooled analysis (Cyclops PS + Cox)
8. 시간 구간별 분석
9. Negative control calibration
10. Characterization (보조 기술통계)
11. 결과 정리 + 논문
```

### 6.2 주요 스크립트

| 스크립트 | 용도 |
|---------|------|
| `ipd_pooled_cyclops_v7.R` | Cyclops PS + 1:N matching + Cox (검증됨) |
| `ipd_cyclops_timewindow.R` | 시간 구간별 HR (landmark) |
| `ipd_cyclops_nc.R` | Negative control HR |
| `run_calibration.R` | EmpiricalCalibration |
| `create_biomarker_fas_v2.py` | Characterization FA 자동 생성 (copy+PUT) |
| `cloud_monitor/main.py` | GCP Cloud Function 모니터링 |

### 6.3 결과 저장 구조

```
C:\Users\data1\Desktop\atlas_auto_cmdata\
├── results_v7b/           # v7b result.zip (기관별)
├── results_biomarker/     # biomarker result.zip
├── cmData_v7b/            # CmData SQLite (기관별/비교별)
├── cmData_biomarker/
├── pooled_results_v7b/    # Cyclops pooled HR
├── pooled_results_biomarker/
├── pooled_results_timewindow/    # 시간 구간별 HR
├── pooled_results_timewindow_bio/
├── pooled_results_nc/     # Negative control HR
├── calibration_results/   # Calibrated HR
├── concept_frequency/     # 기관별 concept frequency
└── char_*.json            # Characterization 결과
```

---

## 7. 향후 활용 계획

### 7.1 새 연구 주제 적용

이 시스템은 **연구 주제만 바꾸면** 동일 파이프라인으로 실행 가능:

1. **코호트 변경**: ATLAS에서 새 target/comparator/outcome 정의
2. **Estimation 생성**: `atlas_auto` 패키지로 자동 생성
3. **실행 + 모니터링**: 동일 API + Cloud Function
4. **분석**: 동일 R 스크립트 (outcome ID만 변경)

### 7.2 시스템 개선 방향

| 개선 사항 | 우선순위 | 설명 |
|----------|:--------:|------|
| feedernet 커스텀 패키지 업로드 | 높음 | 에비드넷 문의 또는 UI 경로 확인 |
| Characterization 다기관 자동화 | 중간 | 기관별 ATLAS에 FA 생성 + 실행 |
| 결과 자동 취합 파이프라인 | 중간 | 다운로드 → 추출 → 분석 → 보고서 |
| 음성 대조군 자동 선택 | 낮음 | CohortMethod NC 선택 자동화 |
| Shiny 대시보드 | 낮음 | 실시간 실행 상태 + 결과 시각화 |

### 7.3 재사용 가능한 자산

| 자산 | 위치 | 설명 |
|------|------|------|
| `src/atlas_auto/` | GitHub | feedernet API 클라이언트 (pip installable) |
| `R/pooled_analysis/` | GitHub | IPD pooled analysis 파이프라인 |
| `cloud_monitor/` | GCP 배포 | Telegram 알림 모니터링 |
| `OHDSI_REPOS.md` | GitHub | OHDSI 패키지 레퍼런스 |
| `docs/` | GitHub | 방법론, 실행 기록, 논문 구조 |
| `automation/` | 로컬 | 레거시 스크립트 (참고용) |

---

## 8. 연구별 체크리스트

새 연구를 시작할 때 이 체크리스트를 따르세요:

- [ ] ATLAS에서 코호트 정의 (target, comparator, outcomes, NCs)
- [ ] Estimation 설계 (PS settings, risk window, covariates)
- [ ] feedernet analysis 생성 + ATLAS import
- [ ] 전체 기관 execution 트리거
- [ ] Cloud monitoring 활성화
- [ ] 완료 기관 result.zip 다운로드
- [ ] CmData 추출 (zip → SQLite 폴더)
- [ ] R 환경 확인 (패키지 버전 호환성, duckdb 제거)
- [ ] IPD pooled analysis (Cyclops 1:1 PS matching + Cox)
- [ ] 시간 구간별 분석 (필요 시)
- [ ] Negative control HR 산출
- [ ] EmpiricalCalibration 적용
- [ ] Characterization (보조 기술통계, 필요 시)
- [ ] 결과 정리 + 논문/보고서 작성
