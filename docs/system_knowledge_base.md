# atlas-auto 시스템 지식 베이스

> 신규 연구 시 이 문서를 **처음부터 끝까지 읽고** 시작할 것.
> 데이터 테이블은 CSV로 분리, 이 문서는 **운영 지식과 레시피**만 유지.

## 참조 데이터 위치

| 데이터 | 파일 |
|--------|------|
| API 엔드포인트 (70+) | `data/atlas_reference/atlas_webapi_endpoints_full.csv` |
| 기관 4종 ID 매핑 (24기관) | `data/site_mapping/site_id_mapping_full.csv` |
| 기관 sourceKey 매핑 | `data/site_mapping/source_key_mapping.csv` |
| PRESET FA 목록 (105개) | `data/atlas_reference/atlas_preset_fa_list.csv` |
| ETRI measurement 리스트 | `data/atlas_reference/etri_measurement_list.csv` |
| 바이오마커 unit 매핑 | `data/biomarker/biomarker_units_by_site.csv` |
| Achilles frequency (23기관×5domain) | `data/concept_frequency/` |
| R 환경 설정 | `data/reference/r_environment.csv` |
| 이슈 히스토리 (13건+) | `data/reference/issue_history.csv` |

---

## 1. API 체계

feedernet에는 **2개의 독립된 API**가 있다. 같은 쿠키로 인증되지만 역할이 다르다.

### 1.1 ATLAS WebAPI — 기관별 ATLAS 인스턴스

```
Base URL: /api/v1/atlas/{group_id}/{site_id}/
용도: 코호트, estimation, vocabulary, Achilles (기관 단위)
접속: client.connect_site(group_id, site_id) → client.webapi_url
```

| Method | Endpoint | 용도 | 주의 |
|--------|----------|------|------|
| **코호트** | | | |
| POST | `/cohortdefinition` | 코호트 생성 | expression은 **object**로 (string 아님 → 400) |
| **GET** | `/cohortdefinition/{id}/generate/{sourceKey}` | 코호트 Generate | **GET이다!** POST → 500 |
| GET | `/cohortdefinition/{id}/info` | Generate 상태/결과 (personCount) | |
| **Estimation** | | | |
| GET | `/estimation/{id}` | estimation 상세 | spec은 `specification` 필드 (JSON string) |
| GET | `/estimation/{id}/copy` | 복사 → 새 ID | 안정적 생성 방법 |
| PUT | `/estimation/{id}` | 수정 | spec은 `json.dumps(spec)`으로 string 전달 |
| POST | `/estimation/import` | import | 실패 시 copy+PUT 방식 사용 |
| **Vocabulary** | | | |
| GET | `/vocabulary/search/{query}` | concept 검색 | |
| GET | `/vocabulary/concept/{id}/descendants` | 하위 concept | |
| GET | `/source/sources` | CDM source 목록 | **sourceKey ≠ cdmName** |
| **Achilles** | | | |
| GET | `/cdmresults/{sourceKey}/{domain}` | concept frequency | domain: condition/drug/measurement/... |
| GET | `/cdmresults/{sourceKey}/measurement/{conceptId}` | drilldown (unit, distribution) | |
| **Characterization** | | | |
| POST | `/cohort-characterization/import` | import (export → import 방식만 사용) | 직접 POST는 FA 비어있음 |
| GET | `/cohort-characterization/{id}/export` | export | |

### 1.2 feedernet 포탈 API — 다기관 실행 관리

```
Base URL: /api/v1/
용도: 프로젝트, analysis, execution 관리 (다기관 중앙 관리)
접속: client.session (로그인 쿠키 자동)
★ projects(복수) = 관리, project(단수) = 실행
```

| Method | Endpoint | 용도 | 주의 |
|--------|----------|------|------|
| **프로젝트** | | | |
| GET | `/projects` | 프로젝트 목록 | **ID 매번 확인 (하드코딩 금지)** |
| **Analysis (복수 projects)** | | | |
| POST | `/projects/{pid}/analysis` | analysis 생성 | 복수 `projects` |
| GET | `/projects/{pid}/analysis` | analysis 목록 | 복수 `projects` |
| GET | `/projects/{pid}/analysis/{aid}/atlas` | ATLAS 기관 목록 | |
| POST | `/projects/{pid}/analysis/{aid}/atlas/{siteId}` | estimation import | body: atlasResearchId, researchType |
| **Execution (단수 project)** | | | |
| POST | `/project/{pid}/analysis/{aid}/execution` | 실행 트리거 | 단수 `project`, **researchName 필수** |
| GET | `/project/{pid}/analysis/{aid}/execution` | 상태 조회 | 응답: content[] → executionList[] 중첩 |
| POST | `/project/{pid}/analysis/{aid}/execution/{eid}/cancel` | 취소 | WAITING + EXECUTING 모두 가능 |
| GET | `.../execution/{eid}/files` | 결과 파일 목록 | |
| GET | `.../execution/{eid}/files/{fid}/download` | 다운로드 | |

### 1.3 ATLAS UI vs API

```
ATLAS UI  (브라우저)  = feedernet.com/atlas-resolve/v2.12.0/{gid}/{sid}/main
ATLAS WebAPI (Python) = feedernet.com/api/v1/atlas/{gid}/{sid}/
→ 같은 백엔드. UI에서 클릭 = API 호출과 동일.
```

### 1.4 함정 정리

| 함정 | 설명 |
|------|------|
| `project` vs `projects` | 실행=단수, 관리=복수 |
| 프로젝트 ID 변경 | 하드코딩 금지 → `GET /projects`로 확인 |
| `cohortdefinition` 하이픈 | 없음. `cohort-characterization`은 있음 |
| sourceKey ≠ cdmName | `GET /source/sources`로 조회 |
| 기관 ID 4종 | group_id ≠ site_id ≠ orgId ≠ cdmId |
| Generate는 GET | POST → 500 |
| 코호트 expression | object로 전송 (string → 400) |
| estimation spec | string으로 전송 (`json.dumps(spec)`) |
| cohortDefinitions | full expression 포함 필수 (누락 → 수시간 후 실패) |
| NC concept set | `conceptSets` + `crossReference`로 설정 (`negativeControls[]` 아님) |
| NC conceptSets items=0 | **정상** — ATLAS가 conceptSetId로 실행 시점에 resolve. `GET /estimation/{id}`는 items 미포함, `GET /estimation/{id}/export`는 포함 |

---

## 2. 실행 레시피

### 2.1 인증

```python
client = FedernetClient()
client.login_portal(email, password)  # automation/ 스크립트에서 확인
client.connect_site(group_id=7, site_id=203)  # → client.webapi_url 설정
# session = client.session  # 포탈 API도 같은 세션 사용
```

### 2.2 Estimation 생성 → 실행 전체 흐름

```python
base = client.PORTAL_URL  # https://www.feedernet.com

# ━━━ Step 1: 프로젝트 ID 확인 ━━━  [포탈 API]
resp = session.get(f'{base}/api/v1/projects')
pid = resp.json()['content'][0]['id']  # 하드코딩 금지

# ━━━ Step 2: ATLAS estimation 생성 ━━━  [ATLAS WebAPI]
resp = client.session.get(f'{client.webapi_url}/estimation/{existing_id}/copy')
new_id = resp.json()['id']
copy_data = resp.json()
copy_data['specification'] = json.dumps(spec)  # spec에 cohortDefinitions + conceptSets + crossRef 포함
client.session.put(f'{client.webapi_url}/estimation/{new_id}', json=copy_data)

# ━━━ Step 3: feedernet analysis 생성 ━━━  [포탈 API, 복수 projects]
session.post(f'{base}/api/v1/projects/{pid}/analysis', json={'name': '...'})
resp = session.get(f'{base}/api/v1/projects/{pid}/analysis')
fed_aid = resp.json()['content'][0]['id']

# ━━━ Step 4: estimation import ━━━  [포탈 API, 복수 projects]
session.post(f'{base}/api/v1/projects/{pid}/analysis/{fed_aid}/atlas/{site_id}',
    json={'atlasResearchId': new_id, 'atlasResearchName': '...', 'researchType': 'ESTIMATION'})

# ━━━ Step 5: execution 트리거 ━━━  [포탈 API, 단수 project]
session.post(f'{base}/api/v1/project/{pid}/analysis/{fed_aid}/execution',
    json={'cdmIds': [...], 'researchName': '...', 'executionType': 'ESTIMATION'})
```

### 2.3 Estimation spec 필수 구성

```python
spec = {
    'cohortDefinitions': [...],          # full expression 포함 필수
    'conceptSets': [
        {'id': 0, 'name': 'NC outcomes', 'expression': {'items': [...]}},  # NC 54+
        {'id': 1, 'name': 'Exclude covariates', 'expression': {'items': [...]}},
    ],
    'conceptSetCrossReference': [        # 각 TCO × (NC + exclude) = N개
        {'conceptSetId': 0, 'targetName': 'negativeControlOutcomes',
         'targetIndex': i, 'propertyName': 'outcomeId'},
        {'conceptSetId': 1,
         'targetName': 'estimationAnalysisSettings.analysisSpecification.targetComparatorOutcomes',
         'targetIndex': i, 'propertyName': 'excludedCovariateConceptIds'},
    ],
    'negativeControlOutcomeCohortDefinition': {
        'occurrenceType': 'all', 'detectOnDescendants': True,
        'domains': ['condition', 'procedure'],
    },
    'estimationAnalysisSettings': { ... },  # TCO + CM analysis
}
# ★ spec.negativeControls[] 배열은 사용하지 않음
```

### 2.4 Execution 상태 확인  [포탈 API, 단수 project]

```python
resp = session.get(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution')
groups = resp.json().get('content', [])
for group in groups:
    for ex in group.get('executionList', []):  # ★ 중첩 구조
        status = ex.get('executionStatus')     # FINISHED_SUCCESSFULLY 등
        cdm = ex.get('cdmName')
        eid = ex.get('id')
```

### 2.5 Execution 취소  [포탈 API, 단수 project]

```python
session.post(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/cancel')
```

### 2.4 Execution 취소

```python
session.post(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/cancel')
# WAITING + EXECUTING_DOCKER 모두 취소 가능
```

### 2.5 Estimation spec 수정

```python
# ATLAS WebAPI (포탈 API 아님)
resp = client.session.get(f'{client.webapi_url}/estimation/{atlasId}')
est_data = resp.json()
spec = json.loads(est_data['specification'])

# cohortDefinitions 수정
spec['cohortDefinitions'] = [...]  # ★ full expression 포함 필수
# outcomeIds 수정
spec['estimationAnalysisSettings']['analysisSpecification']['targetComparatorOutcomes'][0]['outcomeIds'] = [...]

est_data['specification'] = json.dumps(spec)
client.session.put(f'{client.webapi_url}/estimation/{atlasId}', json=est_data)
```

### 2.6 Achilles 수집

```python
# frequency (concept별 인원수)
data = client.get_achilles_frequency(source_key, 'measurement')  # domain: condition/drug/measurement/procedure/observation

# drilldown (unit + value distribution)
data = client.get_achilles_drilldown(source_key, 'measurement', concept_id)
# 주요 필드:
#   recordsByUnit: [{conceptId, conceptName, countValue}]  ← unit별 레코드 수
#   measurementValueDistribution: [{category, minValue, p10Value, p25Value, medianValue, p75Value, p90Value, maxValue}]
```

수집 스크립트: `data/scripts/collect_measurement_units.py`
sourceKey는 `data/site_mapping/source_key_mapping.csv` 참조.

### 2.7 결과 다운로드 + CmData 추출

```python
# 1. 파일 목록 조회
resp = session.get(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/files')
files = resp.json().get('content', [])
# files: [{id, name, size}] — result.zip

# 2. 다운로드
resp = session.get(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/files/{fid}/download')
with open(f'{cdmName}_result.zip', 'wb') as f:
    f.write(resp.content)
```

```r
# 3. CmData 추출 (R)
library(CohortMethod)
zipFile <- "AUMC_5.3.1_11_result.zip"
unzip(zipFile, exdir = "AUMC")
# result/export/ 아래 CSV → loadCohortMethodData()
```

기존 스크립트: `automation/download_results.py`

### 2.8 result.zip 구조

```
result.zip/
├── cmOutput/                              ← CohortMethod 중간 산출물
│   ├── CmData_l1_t{T}_c{C}/              ← 원본 데이터 (SQLite/Andromeda)
│   │   ├── cohorts                        ←   T/C 코호트 + PS 적합 전
│   │   ├── outcomes                       ←   outcome event
│   │   ├── covariates                     ←   공변량 (sparse matrix)
│   │   ├── covariateRef                   ←   공변량 이름 매핑
│   │   └── analysisRef                    ←   분석 설정
│   ├── StudyPop_l1_s1_t{T}_c{C}_o{O}.rds ← PS 매칭 + risk window 적용된 population
│   ├── Ps_l1_s1_t{T}_c{C}.rds            ← PS model
│   ├── StrPop_l1_s1_t{T}_c{C}_o{O}.rds   ← stratified population
│   └── outcomeModelReference.rds          ← 결과 참조
├── export/                                ← CSV 요약 (Shiny + 분석용)
│   ├── cohort_method_result.csv           ←   기관별 HR
│   ├── negative_control_outcome.csv       ←   NC HR
│   ├── covariate_balance.csv              ←   SMD
│   ├── preference_score_dist.csv          ←   PS 분포
│   ├── kaplan_meier_dist.csv              ←   KM 데이터
│   ├── attrition.csv                      ←   환자 흐름
│   ├── propensity_model.csv               ←   PS model coefficients
│   └── ...
├── balance/                               ← covariate balance 상세
├── ShinyApp/                              ← Evidence Explorer 데이터
└── log.txt                                ← 실행 로그
```

### 2.9 CohortMethod 파이프라인 (CmData → StudyPop → StratPop)

```
CmData (SQLite)
  │  원본: T/C 코호트 + outcome + covariates (sparse matrix)
  │  PS 미적합, 매칭 안 됨, risk window 미적용
  │
  ↓ createStudyPopulation(riskWindowStart, riskWindowEnd, removeSubjectsWithPriorOutcome)
  │
StudyPop (.rds)
  │  risk window 적용, prior outcome 제거, washout 적용
  │  PS 미적합, 매칭 안 됨
  │
  ↓ createPs() — PS score 계산
  ↓ matchOnPs() 또는 stratifyByPs()
  │
StratPop (.rds)
  │  PS matching(1:1) 또는 stratification(5분위) 완료
  │  ★ 최종 분석 대상 population
  │
  ↓ fitOutcomeModel(modelType="cox", stratified=TRUE)
  │
OutcomeModel → HR, 95% CI, p-value
```

| 파일 | PS 적합 | 매칭/층화 | risk window | 용도 |
|------|:---:|:---:|:---:|------|
| **CmData** | X | X | X | 원본 데이터, IPD pooled 분석 시작점 |
| **StudyPop** | X | X | O | risk window + prior outcome 제거 |
| **StratPop** | O | O | O | 최종 분석 대상, Cox 입력 |

### 2.10 feedernet estimation 실행 구조

```
ATLAS (KHNMC 1개 기관에서 설계)
  └── estimation spec (cohortDefinitions + TCO + NC + PS설정)
       ↓ feedernet이 export 시 CIRCE JSON → SQL 변환
R 패키지 생성 (inst/sql/ + inst/settings/)
       ↓ 각 기관 Docker 컨테이너에 배포
각 기관에서 독립 실행:
  1. createCohorts() ← 동일한 SQL을 각 기관 CDM DB에서 실행 (코호트 복제가 아님)
  2. runCohortMethod() ← PS fitting + matching + Cox
  3. packageResults() ← result.zip 생성
```

코호트를 각 기관에 "복제"하는 것이 아니라, **같은 코호트 정의 SQL을 각 기관 CDM에서 실행**하는 구조.
따라서 ATLAS에서 1개 기관에만 설계하면 feedernet이 전 기관에 동일 SQL을 배포/실행한다.

### 2.11 다기관 분석 방법 비교

**feedernet 결과 (기관별 독립 실행)**:
- 각 기관이 **독립된 PS model**로 fitting → StudyPop → StratPop → HR
- result.zip의 export CSV = 기관별 HR (Shiny Evidence Explorer용)
- 기관별 HR → meta-analysis pooling 가능 (DL, Bayesian)

**IPD pooled (CmData 합산, 우리 방식)**:
- 전 기관 CmData를 합산 → **통합 PS model** (site dummy covariate 포함)
- Cyclops large-scale LASSO로 수천 개 covariates + site dummy 동시 fitting
- 1:1 PS matching → site-stratified Cox → pooled HR
- feedernet의 StudyPop/StratPop은 사용하지 않고 **CmData부터 다시 처리**

**StratPop 합산은 왜 안 하나?**:
- 기관별 PS model이 다르므로, 기관 A의 PS=0.3 ≠ 기관 B의 PS=0.3
- 합산 시 PS 보정 의미가 희석됨
- site-stratified Cox로 일부 보완 가능하지만 통합 PS fitting이 정석
- 소규모 기관에서 매칭 pool이 작아 매칭 성공률 저하

**선택 기준**:
- IPD pooled (기본): 기관별 outcome N이 작을 때. 통합 PS로 검정력 최대화
- Meta-analysis (선택): 기관별 outcome N이 충분할 때만. 기관별 HR의 이질성 평가 가능

---

## 3. Characterization 운영

### 3.1 PRESET FA 방식 (확정)

CRITERIA_SET copy+PUT은 concept 소실 문제 → **PRESET FA만 사용**.

`MeasurementValueLongTerm` (id=42): concept별 자동 분리, mean/SD/median/Q1/Q3/min/max/P10/P90 전부 포함.
시간 구간은 Characterization `parameters`로 제어 (longTermStartDays, endDays 오버라이드).

### 3.2 배포: export → import

```python
GET  /cohort-characterization/{id}/export   → 원본 기관에서 JSON
POST /cohort-characterization/import        → 타 기관에 import (코호트+FA 자동 생성)
POST /cohort-characterization/{new_id}/generation/{sourceKey}  → 실행
```

### 3.3 FA 수정: copy + 2단계 PUT

```python
GET /feature-analysis/{id}/copy              → 새 FA
PUT /feature-analysis/{new_id}               → 1단계: 이름 + 시간 구간
PUT /feature-analysis/{new_id}               → 2단계: concept
# 한번에 하면 500 에러 → 반드시 2단계 분리
```

---

## 4. Concept ID 탐색 프로세스

### 4.1 탐색 순서 (확정)

```
Step 1. Achilles frequency에서 직접 검색 (1차 소스)
  → data/concept_frequency/{기관}_{domain}.csv
  → 실제 CDM에 존재하는 concept만 반환
  → descendant는 개별 concept으로 나옴 (합산 필요)

Step 2. ATLAS vocabulary API로 보완
  → /vocabulary/search/{query} — 키워드 검색
  → /vocabulary/concept/{id}/descendants — 하위 개념 조회
  → /vocabulary/concept/{id}/related — 매핑 관계 확인

Step 3. (참고만) KCDtoConcept_id/all_kcd_map.csv
  → 기관별 KCD→SNOMED 실제 매핑 (과거 시점 스냅샷)
  → 업데이트 반영 안 될 수 있으므로 참고용만
```

### 4.2 핵심 주의사항

- **Achilles 우선**: vocabulary 검색보다 Achilles frequency가 실제 CDM 상태를 반영
- **KCD→SNOMED 매핑이 예상과 다를 수 있음**: 예) F90.0(ADHD)이 438409가 아닌 4047120으로 매핑된 사례 → Achilles에서 확인 필수
- **includeDescendants=true 시뮬레이션**: Achilles에서는 개별 concept만 나오므로, descendants 전부를 수동 합산해야 실제 코호트 크기 추정 가능
- **Concept 참조는 반드시 CONCEPT_ID 기준** — LOINC/KCD CONCEPT_CODE로 매핑하면 오류
- **measurement concept은 descendant 없음** — condition과 달리 OR로 변이 concept 직접 포함
- **unit 이질성**: 같은 검사라도 기관별 단위가 다를 수 있음 → dual-unit 코호트 분리 필요
- **multi-concept OR 코호트의 InclusionRules**: Prior normal = **ANY**, No prior abnormal = **ALL**

### 4.3 Achilles 수집 코드

```python
# frequency (concept별 인원수) — 이미 data/concept_frequency/에 수집 완료
data = client.get_achilles_frequency(source_key, domain)
# domain: condition, drug, measurement, procedure, observation

# drilldown (unit + value distribution) — measurement 전용
data = client.get_achilles_drilldown(source_key, 'measurement', concept_id)
# recordsByUnit, measurementValueDistribution 필드 참조
```

sourceKey: `data/site_mapping/source_key_mapping.csv` 참조
unit 전수조사: `data/biomarker/biomarker_units_by_site.csv`

---

## 5. 분석 방법론

### 5.1 IPD Pooled Analysis (기본)

- PS: Cyclops (Laplace prior, cross-validation) + site dummy covariate
- 매칭: 1:1 nearest-neighbor, caliper = 0.2 × SD(logit PS)
- Outcome model: Site-stratified Cox proportional hazard regression
- 공변량: Demographics(Gender, AgeGroup) + ConditionLongTerm + DrugLongTerm (연구마다 커스텀)
- Forest plot: outcome별 pooled HR 표시 (기관별 HR은 outcome N 부족으로 미산출)

**IPD vs Meta-analysis 선택 기준**:
- **IPD pooled (기본)**: 기관별 outcome event 수가 적을 때 (대부분의 다기관 CDM 연구). 전체 데이터를 합산하여 PS fitting하므로 검정력 높음.
- **Meta-analysis (선택적)**: 기관별 outcome N이 충분히 클 때만 고려. 기관별로 독립적으로 HR 산출 후 DL/Bayesian pooling. Shiny Evidence Explorer 기본 방식이지만, 소규모 기관에서 HR 추정이 불안정.

### 5.2 시간 구간별 분석 (Landmark)

PS matching 1회 → 동일 코호트에서 시간 구간별 Cox.
구간: 1-30d(급성기), 31-90d(아급성기), 91-365d(단기만성), 366-1095d(중기), 1096-3650d(장기), 1-3650d(전체).

```r
oc <- outcomes[daysToEvent >= windowStart & daysToEvent <= windowEnd]
df <- df[df$maxFollow >= windowStart]
df$time <- pmin(daysToObsEnd, windowEnd) - windowStart + 1
```

### 5.3 Negative Control Calibration

48+ NC outcomes, EmpiricalCalibration 패키지.
기준: NC HR median ≈ 1.0, 유의 비율 ≈ 5%.

### 5.4 Characterization 기술통계

다기관 통합: weighted mean ± pooled SD. median/Q1/Q3는 기관별 개별 보고.

---

## 6. 이슈 해결 패턴

> 상세 이슈 목록: `data/reference/issue_history.csv`

### 6.1 R 패키지

- `loadCohortMethodData` 실패 → **Andromeda 0.6.0** (1.x 호환 안 됨)
- `no slot of name "conn_ref"` → **duckdb 제거** (RSQLite 충돌)
- Rtools "cc1 not found" → R 내 PATH 설정
- **원칙: R 스크립트는 VS Code R 터미널에서 `source()` 실행** (bash Rscript 금지)

### 6.2 feedernet API

- Estimation POST 500 에러 → copy+PUT 방식
- cdmId ≠ group_id ≠ atlasId → 매핑 CSV 참조
- 서버 불안정 즉시 실패 → 재실행
- 1~5시간 후 실패 + 에러 메시지 없음 → **cohortDefinitions 누락 확인**

### 6.3 Characterization

- CRITERIA_SET concept 안 잡힘 → PRESET FA 전환
- 직접 POST FA 비어있음 → export/import
- PRESET FA id 혼동 → `atlas_preset_fa_list.csv` 필수 확인

---

## 7. 파이프라인 + 체크리스트

### 7.0 3계층 저장 구조

```
1. GitHub (atlas_auto_ms)           ← 시스템 코드 + 참조 데이터 (연구 공통)
   ├── src/atlas_auto/              ← Python 패키지
   ├── data/site_mapping/           ← 기관 매핑 (공통)
   ├── data/concept_frequency/      ← Achilles (공통)
   ├── data/atlas_reference/        ← API, ETRI list (공통)
   └── docs/system_knowledge_base.md

2. Google Drive (연구별 폴더)        ← 연구 문서, 설계 (공유/백업)
   └── KHNMC/{연구명}/
       ├── CLAUDE.md                ← 연구별 컨텍스트
       ├── PROGRESS.md              ← 연구별 진행상황
       ├── docs/                    ← paper, IRB, checklist
       ├── cohort_definitions/      ← 이 연구의 코호트 JSON
       ├── estimation_model/        ← estimation spec
       └── data/                    ← 연구별 데이터 (characterization 등)

3. Local Desktop ({연구명}_cmdata/) ← 무거운 결과 파일
   ├── results/                    ← result.zip (기관별)
   ├── cmData/                     ← CmData SQLite
   └── pooled_results/             ← HR 결과
```

**원칙**: git에는 연구 특이적 파일을 넣지 않는다. 시스템은 `pip install`로 가져오고, 연구별 폴더에서 import하여 사용.

### 7.1 새 연구 시작 순서

```
0.  pip install atlas-auto (또는 git clone)
0b. Google Drive에 연구 폴더 생성 + CLAUDE.md 작성
1.  ATLAS에서 cohort 정의 + estimation 설계
1b. 공변량 설정 검토 (builder.py covariate_settings — 연구마다 다름)
2.  ★ 기관별 데이터 검증 (Achilles로 concept 가용성 + unit 확인)
    → data/concept_frequency/ 먼저 참조, 없으면 API 수집
    → concept/unit 통일 가능한 기관만 선정
3.  feedernet analysis 생성 + ATLAS import
4.  전체 기관 execution 트리거
5.  Cloud monitoring 설정 (GCP Cloud Function)
6.  완료 기관 result.zip 다운로드 → Local Desktop
7.  CmData 추출 (zip → SQLite) → Local Desktop
8.  IPD pooled analysis (Cyclops PS + Cox)
9.  시간 구간별 분석 (필요 시)
10. Negative control calibration
11. Characterization (보조 기술통계)
12. 결과 정리 + 논문 → Google Drive
```

**교훈**: 데이터 검증(2단계)을 estimation 전에 반드시 수행. 안 하면 기관 수 변경으로 이중 작업 발생.

### 7.2 구조적 교훈

1. measurement concept은 descendant 없음 → OR로 직접 포함
2. 변경된 outcome만 별도 estimation 분리 실행 가능
3. Characterization은 PRESET FA + parameters 오버라이드
4. 기관 변동 시 NC+Calibration까지 완료 후 비교 (raw HR 비교 무의미)
5. CmData 생성/분석 시 패키지 버전 반드시 일치

### 7.3 주요 스크립트

| 스크립트 | 용도 |
|---------|------|
| `data/scripts/collect_measurement_units.py` | 전 기관 unit 전수조사 |
| `data/scripts/create_multi_concept_cohorts.py` | multi-concept 코호트 생성 |
| `cloud_monitor/main.py` | GCP Telegram 모니터링 |
| R 분석 스크립트 (IPD, calibration, KM 등) | 연구별 폴더의 `R/reference_scripts/` 참조 |

---

## 8. FeatureExtraction unit_concept_id 검증

unit_concept_id=0이 PS matching에 미치는 영향:

| 공변량 유형 | unit 영향 |
|---|---|
| Measurement (binary) | 없음 — 존재 여부만 확인 |
| MeasurementValue (continuous) | **있음** — 현재 OFF |
| MeasurementRangeGroup | 없음 — range_low/range_high NOT NULL만 확인, unit 미참조 |

기관별 unit 등급: `data/biomarker/biomarker_units_by_site.csv` 참조.
A(완벽): GNUCH, JCMJ, KDH, KWMC / F(전멸): CHNUH / 상세: 이전 조사 결과 참고.

---

## 9. 시스템 TODO

- [x] **measurement unit 전수조사**: 13/23기관 완료 (1,266행). KHNMC 별도 완료. 누락: KWMC, KHMC, MJH, PNUH, SCHBC, SCHCA, SCHGM, SCHSU, UUH, SEJONG (에러/503). 결과: `data/measurement_unit_survey_full.csv`
- [x] **feedernet analysis 생성 API**: `POST /api/v1/projects/{pid}/analysis` (복수 projects). **프로젝트 ID는 `GET /api/v1/projects`로 확인** — 이전 ID(2908)와 현재 ID(5104)가 다를 수 있음. `project`(단수)는 execution 전용, `projects`(복수)는 analysis 관리용.
- [ ] **Generate 엔드포인트 정리**: GET으로 generate 되는 것 확인됨. POST는 500. knowledge base에 기록 완료. client.py에 반영 필요.

---

## 10. DQM 인프라

feedernet 내부 전용. 외부 접근 불가 (DNS NXDOMAIN).
- DQM ATLAS: `api.feedernet.co.kr/atlas/v2.7.6/...`
- 각 기관 CDM: PostgreSQL (db=omop)
- 커스텀 쿼리 → 에비드넷 관리자 협조 필요
- 상세: `SENSITIVE_DO_NOT_COMMIT/` (git 미포함)
