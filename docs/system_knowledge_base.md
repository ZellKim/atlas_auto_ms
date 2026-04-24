# atlas-auto 시스템 지식 베이스

> 신규 연구 시 이 문서를 **처음부터 끝까지 읽고** 시작할 것.
> **API 호출 전 반드시 이 문서를 참조.** 추측으로 호출하지 말 것.

## 참조 데이터 위치

| 데이터 | 파일 |
|--------|------|
| API 엔드포인트 (70+) | `data/atlas_reference/atlas_webapi_endpoints_full.csv` |
| 기관 4종 ID 매핑 (24기관) | `data/site_mapping/site_id_mapping_full.csv` |
| 기관 sourceKey 매핑 | `data/site_mapping/source_key_mapping.csv` |
| PRESET FA 목록 (105개) | `data/atlas_reference/atlas_preset_fa_list.csv` |
| ETRI measurement 리스트 | `data/atlas_reference/etri_measurement_list.csv` |
| **Measurement 연구 시작 키트** | `data/measurement/` (README 있음) |
| - 기관별 biomarker 최종 선택 | `data/measurement/site_concept_matrix.csv` |
| - biomarker 안정성 요약 | `data/measurement/stability_summary.csv` |
| - 기관별 unit | `data/measurement/by_site/units_by_site.csv` |
| - Value 분포 (p10-90) | `data/measurement/unit_survey_full.csv`, `data/measurement/v4_surveys/*.csv` |
| - Characterization (FA preset) | `data/measurement/characterization/char_preset_all.csv` |
| Achilles frequency (23기관×5domain, cross-domain) | `data/concept_frequency/` |
| R 환경 설정 | `data/reference/r_environment.csv` |
| 이슈 히스토리 | `data/reference/issue_history.csv` |

---

## 1. API 체계

> **API 엔드포인트 CSV** (항상 먼저 참조):
> - `data/atlas_reference/atlas_webapi_endpoints.csv` — **ATLAS WebAPI** (기관별, /api/v1/atlas/{group_id}/{site_id}/...)
> - `data/atlas_reference/feedernet_portal_api_endpoints.csv` — **feedernet 포털 API** (다기관 관리, /api/v1/...)


feedernet에는 **2개의 API**가 있다. 같은 쿠키로 인증되지만 역할이 다르다.

### 1.1 ATLAS WebAPI — 기관별 ATLAS 인스턴스

```
Base URL: /api/v1/atlas/{group_id}/{site_id}/
용도: 코호트, estimation, vocabulary, Achilles (기관 단위)
접속: client.connect_site(group_id, site_id) → client.webapi_url
```

| Method | Endpoint | 용도 | 주의 |
|--------|----------|------|------|
| POST | `/cohortdefinition` | 코호트 생성 | expression은 **object** (string → 400) |
| **GET** | `/cohortdefinition/{id}/generate/{sourceKey}` | Generate | **GET!** (POST → 500) |
| GET | `/cohortdefinition/{id}/info` | Generate 상태 (personCount) | |
| GET | `/estimation/{id}` | estimation 상세 | `specification` 필드 = JSON string |
| GET | `/estimation/{id}/copy` | 복사 → 새 ID | **정석 생성 방법** |
| PUT | `/estimation/{id}` | 수정 | spec은 `json.dumps()`로 string 전달 |
| GET | `/estimation/{id}/export` | export (conceptSets resolve됨) | |
| GET | `/source/sources` | CDM source 목록 | **sourceKey ≠ cdmName** |
| GET | `/vocabulary/search/{query}` | concept 검색 | |
| GET | `/vocabulary/concept/{id}/descendants` | 하위 concept | |
| GET | `/cdmresults/{sourceKey}/{domain}` | Achilles frequency | |
| GET | `/cdmresults/{sourceKey}/measurement/{id}` | measurement drilldown | |

### 1.2 feedernet 포탈 API — 다기관 실행 관리

**Project 관리 (2026-04-18 추가)**:
| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/v1/projects` | project 목록 (복수) |
| POST | `/api/v1/projects` | project 생성. body: `{name, projectType: 'COMPARATIVE_EFFECTIVENESS' or 'OTHER'}`. 응답에 ID 없음, 이후 GET으로 확인 |
| DELETE | `/api/v1/projects/{pid}` | project 삭제 |

**projectType 값** (기존 projects 기준):
- `COMPARATIVE_EFFECTIVENESS`: CER (estimation 분석)
- `OTHER`: 기타

**Analysis 관리 (기존)**:


```
Base URL: /api/v1/
★ projects(복수) = 관리, project(단수) = 실행
```

| Method | Endpoint | 용도 | 주의 |
|--------|----------|------|------|
| GET | `/projects` | 프로젝트 목록 | **ID 매번 확인** |
| POST | `/projects/{pid}/analysis` | analysis 생성 | 복수 `projects` |
| GET | `/projects/{pid}/analysis` | analysis 목록 | 복수 `projects` |
| GET | `/projects/{pid}/analysis/{aid}/atlas` | ATLAS 기관 목록 | |
| POST | `/projects/{pid}/analysis/{aid}/atlas/{siteId}` | estimation import | body: atlasResearchId, researchType |
| POST | `/project/{pid}/analysis/{aid}/execution` | 실행 트리거 | 단수 `project`, **researchName 필수** |
| GET | `/project/{pid}/analysis/{aid}/execution` | 상태 조회 | content[] → executionList[] 중첩. WAITING entry `waitingRank` = **포털 전체 큐 내 순위** (해당 analysis만이 아님) |
| POST | `.../execution/{eid}/cancel` | 취소 | WAITING + EXECUTING 가능 |
| GET | `.../execution/{eid}/files` | 결과 파일 목록 | |
| GET | `.../execution/{eid}/files/{fid}/download` | 다운로드 | |

### 1.3 ATLAS UI = WebAPI 프론트엔드

브라우저(`/atlas-resolve/...`)와 Python(`/api/v1/atlas/...`)은 같은 백엔드. UI에서 설계한 것은 API로 그대로 접근 가능.

### 1.4 함정 정리

| 함정 | 설명 |
|------|------|
| `project` vs `projects` | 실행=단수, 관리=복수 |
| 프로젝트 ID | 하드코딩 금지 → `GET /projects`로 확인 |
| `cohortdefinition` 하이픈 | 없음. `cohort-characterization`은 있음 |
| sourceKey ≠ cdmName | `GET /source/sources`로 조회 |
| 기관 ID 4종 | group_id ≠ site_id ≠ orgId ≠ cdmId |
| Generate | **GET** (POST → 500) |
| 코호트 expression | **object**로 전송 (string → 400) |
| estimation spec | **string**으로 전송 (`json.dumps(spec)`) |
| NC concept set | `conceptSets` + `crossReference`로 설정. `negativeControls[]` 배열 아님 |
| NC items=0 | **정상**. ATLAS가 실행 시 conceptSetId로 자동 resolve |
| cohortDefinitions | feedernet이 export 시 ATLAS에서 **자동 resolve**. spec에 expression 없어도 실행 가능 |
| 500 에러 | **API 불안정이 아니라 호출 방식 오류** 가능성 먼저 확인 |
| concept set name 줄바꿈 | name에 `\n` 포함 시 R exportOutcomes에서 FATAL. ATLAS UI에서 복사 시 발생 가능 → strip() 필요 |
| cohortdefinition PUT | expression은 **object**로 (string → 400). estimation PUT과 반대 |

---

## 2. 실행 레시피

### 2.1 인증

```python
client = FedernetClient()
client.login_portal(email, password)  # automation/ 스크립트에서 확인
client.connect_site(group_id=7, site_id=203)
```

### 2.2 Estimation 생성 → 실행 (정석: copy 방식)

```python
base = client.PORTAL_URL

# ━━━ Step 1: 프로젝트 ID 확인 ━━━  [포탈]
resp = session.get(f'{base}/api/v1/projects')
pid = resp.json()['content'][0]['id']

# ━━━ Step 2: 기존 estimation copy + TCO 변경 ━━━  [WebAPI]
# ★ 정석: 잘 돌아가는 estimation을 copy해서 TCO만 바꾼다
# NC, exclude, PS설정, stopOnError 전부 원본 유지
resp = client.session.get(f'{client.webapi_url}/estimation/{working_id}/copy')
new_id = resp.json()['id']
est_data = resp.json()
spec = json.loads(est_data['specification'])

# TCO만 변경
spec['estimationAnalysisSettings']['analysisSpecification']['targetComparatorOutcomes'] = new_tcos
# cohortDefinitions에 새 코호트 추가 (선택 — feedernet이 자동 resolve하지만 명시적으로 넣어도 됨)

est_data['specification'] = json.dumps(spec)
client.session.put(f'{client.webapi_url}/estimation/{new_id}', json=est_data)

# ━━━ Step 3: feedernet analysis 생성 ━━━  [포탈, 복수 projects]
session.post(f'{base}/api/v1/projects/{pid}/analysis', json={'name': '...'})
resp = session.get(f'{base}/api/v1/projects/{pid}/analysis')
fed_aid = resp.json()['content'][0]['id']

# ━━━ Step 4: estimation import ━━━  [포탈, 복수 projects]
session.post(f'{base}/api/v1/projects/{pid}/analysis/{fed_aid}/atlas/{site_id}',
    json={'atlasResearchId': new_id, 'atlasResearchName': '...', 'researchType': 'ESTIMATION'})

# ━━━ Step 5: execution 트리거 ━━━  [포탈, 단수 project]
session.post(f'{base}/api/v1/project/{pid}/analysis/{fed_aid}/execution',
    json={'cdmIds': [...], 'researchName': '...', 'executionType': 'ESTIMATION'})
```

### 2.3 Execution 상태 확인  [포탈, 단수 project]

```python
resp = session.get(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution')
groups = resp.json().get('content', [])
for group in groups:
    for ex in group.get('executionList', []):  # ★ 중첩 구조
        status = ex.get('executionStatus')
        cdm = ex.get('cdmName')
        eid = ex.get('id')
```

상태값: `EXECUTING_PREPARING`, `EXECUTING_DOCKER`, `WAITING`, `FINISHED_SUCCESSFULLY`, `FINISHED_WITH_ERROR`, `CANCELED`

### 2.3a Execution log 조회 (SUCCESS만 가능)

```python
# 성공한 execution만 log 조회 가능
# GET /api/v1/project/{pid}/analysis/{aid}/execution/{eid}/logs
resp = session.get(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/logs')
log_text = resp.json().get('content', '')
# → 전체 R 실행 log: timestamp\t[thread]\tLEVEL\tclass\tmethod\tmessage
```

**FAILED execution의 경우 API로 log 완전 차단 (2026-04-18 전수 검증)**:
- `/logs`: 제네릭 메시지 `"연구가 실패했습니다. 로그를 확인해주세요"`
- `/files`, `/files/{n}/view`, `/files/{n}/download`: **code 7020** "Not completed"
- `/shiny`: code 7020
- UI frontend JS bundle(`index-CPRjfs_0.js`) 분석 결과 숨겨진 log endpoint 없음 — UI도 동일 response
- 서버사이드 deliberate block (보안 추정)

**실패 시 대안**:
1. 포털 UI 수동 확인 (제네릭일 수 있음)
2. feedernet admin 연락 (DB/docker 직접 접근 필요)
3. Spec 재검토 후 재실행 (예방이 최선)
4. 소규모 test execution (KHNMC 1 site 선실행 → 전체 확대)

**예방 체크리스트** (실패 방지):
- stopOnError=false ★
- cohortDefinitions 전부 포함 (T + Cs + 모든 outcome)
- NC 54 items + exclude 110 items 채움
- concept set name `\n` strip
- specification=string (json.dumps)

### 2.4 Execution 취소  [포탈, 단수 project]

```python
session.post(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/cancel')
```

### 2.5 Achilles 수집

```python
data = client.get_achilles_frequency(source_key, domain)
data = client.get_achilles_drilldown(source_key, 'measurement', concept_id)
# recordsByUnit, measurementValueDistribution
```

### 2.6 결과 다운로드  [포탈, 단수 project]

```python
resp = session.get(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/files')
resp = session.get(f'.../{fid}/download')
```

---

## 3. feedernet estimation 실행 구조

```
ATLAS (1개 기관에서 설계)
  └── estimation spec
       ↓ feedernet export → CIRCE JSON → SQL 변환 → R 패키지 생성
각 기관 Docker에서 독립 실행:
  1. createCohorts() ← 같은 SQL을 각 기관 CDM에서 실행
  2. runCohortMethod() ← PS fitting + matching + Cox
  3. packageResults() ← result.zip
```

코호트 "복제"가 아니라 **동일 SQL 배포/실행**. 1개 기관에서 설계하면 feedernet이 전 기관에 배포.

### 3.1 result.zip 구조

```
cmOutput/
  CmData_l1_t{T}_c{C}/     ← 원본 (PS 전, 매칭 전)
  StudyPop_..._.rds          ← risk window 적용 (PS 전)
  Ps_..._.rds                ← PS model
  StratPop_..._.rds          ← PS 매칭/층화 완료 (최종)
export/
  cohort_method_result.csv   ← HR
  negative_control_outcome.csv ← NC HR
  covariate_balance.csv, kaplan_meier_dist.csv, attrition.csv, ...
```

### 3.2 CmData → StudyPop → StratPop

| 파일 | PS | 매칭 | risk window | 용도 |
|------|:---:|:---:|:---:|------|
| CmData | X | X | X | IPD pooled 시작점 |
| StudyPop | X | X | O | risk window + prior outcome 제거 |
| StratPop | O | O | O | 최종 분석 대상 |

### 3.3 다기관 분석 방법

**IPD pooled (기본)**: 전 기관 CmData 합산 → 통합 PS (site dummy + LASSO) → 1:1 matching → site-stratified Cox. feedernet의 StudyPop/StratPop은 사용하지 않고 CmData부터 처리.

**Meta-analysis (선택)**: 기관별 outcome N 충분할 때만. feedernet 결과의 기관별 HR을 pooling.

**StratPop 합산 비권장**: 기관별 PS model이 달라 PS scale 불일치.

---

## 4. Concept ID 탐색

### 탐색 순서
1. **Achilles frequency** (1차) → `data/concept_frequency/`
2. **ATLAS vocabulary API** (보완) → `/vocabulary/search/`, `/vocabulary/concept/{id}/descendants`
3. **KCDtoConcept_id** (참고만) → 과거 스냅샷, 업데이트 미반영 가능

### 주의사항
- Achilles 우선 (실제 CDM 반영)
- KCD→SNOMED 매핑이 예상과 다를 수 있음 (예: F90.0 → 4047120)
- CONCEPT_ID 기준 (CONCEPT_CODE 아님)
- measurement는 descendant 없음 → OR로 직접 포함
- unit 이질성 → dual-unit 코호트 분리 필요

### 4.1 Achilles Drilldown API 실수 방지 (2026-04-17 기록)

**Endpoint**: `GET /api/v1/atlas/{group_id}/{site_id}/cdmresults/{sourceKey}/measurement/{concept_id}` (timeout=30)

**Unit 데이터 정확한 필드** — `recordsByUnit`:
```python
data['recordsByUnit']  # [{'conceptId': 8840, 'conceptName': 'milligram per deciliter', 'countValue': 310059}, ...]
```
**쓰면 안 되는 필드** (혼동 주의):
- `valuesRelativeToNorm` — "Within Range" 등 범주만, conceptName에 unit 이름 섞여 있어 파싱 오해
- `measurementValueDistribution` — 값 분포, unit 아님

**기존 `data/scripts/collect_measurement_units.py`는 버그 있음** (`valuesRelativeToNorm` 파싱). 참고 시 `collect_v4_biomarker_units.py` (recordsByUnit 사용) 기준으로 쓸 것.

**자주 하는 실수 3종**:
1. `cdmName`을 `sourceKey` 자리에 넣음 → 502 에러. **반드시** `data/site_mapping/source_key_mapping.csv` 3번째 컬럼
2. drilldown JSON에서 `recordsByUnit` 대신 다른 필드 파싱 → unit 정보 누락
3. Python stdout 버퍼링 → redirect 시 `python -u` 또는 `print(..., flush=True)` 필수. 안 하면 "정지한 줄 알았는데 실은 돌고 있음" 상황 발생

---

## 5. 분석 방법론

### 5.1 IPD Pooled Analysis (기본)
- PS: Cyclops large-scale LASSO + site dummy covariate
- 매칭: 1:1 nearest-neighbor, caliper = 0.2 × SD(logit PS)
- Outcome: Site-stratified Cox
- Forest plot: outcome별 pooled HR (기관별 HR 미산출 — outcome N 부족)

### 5.2 시간 구간별 분석 (Landmark)
PS matching 1회 → 구간별 Cox. 구간: 1-30d, 31-90d, 91-365d, 366-1095d, 1096-3650d, 1-3650d.

### 5.3 Negative Control Calibration
NC HR → EmpiricalCalibration → calibrated HR. 기준: NC median ≈ 1.0, 유의 비율 ≈ 5%.

**패키지 함정 2종 (2026-04-18 v4 분석에서 확인)**:

1. **`fitMcmcNull()` 반환 객체 [2] = precision, SD 아님**
   - 반환값이 `c(mean, precision)`. 헷갈려서 sd로 출력하면 비정상 큰 값 (`1/√77≈0.11`이 정상인데 `77`로 찍힘)
   - 해결: `sd = 1/sqrt(precision)` 변환 또는 `fitNull()` (method-of-moments, `c(mean, sd)` 반환) 사용
   - MCMC는 precision posterior CI가 넓은 경우(e.g., [6.7, 1256]) 불확실성 있음 — method-of-moments는 점추정만

2. **R `tryCatch` 안 `<<-` 절대 금지 (silent empty return)**
   - tryCatch **expr 블록 안에서 `<<-`** 쓰면 함수 local 변수가 아닌 전역 scope에 할당 → 함수 return 시 empty data frame
   - 증상: 정상 flow의 `<<-`는 silent fail, 에러 flow와 early-return만 정상 작동 → `nrow=0` 결과
   - downstream에서 `df$col <- ...` "replacement has 1 row, data has 0" 에러로 뒤늦게 발견
   - **해결 패턴** (권장):
     ```r
     new_row <- tryCatch({
       fit <- coxph(...)
       data.frame(outcomeId=oid, hr=..., ...)
     }, error = function(e) {
       data.frame(outcomeId=oid, hr=NA, ...)
     })
     res <- rbind(res, new_row)  # always local <-
     ```
   - 주기 검사: `grep -rn 'res <<- rbind' R/`

3. **`calibrateConfidenceInterval()` 내부 `legacy` 변수 미정의 silent error (EmpiricalCalibration 최신)**
   - 함수 시그니처: `function(logRr, seLogRr, model, ciWidth = 0.95)`
   - 내부 `logBound()` 호출 시 `if (legacy) {...}` 체크 → `missing value where TRUE/FALSE needed`
   - tryCatch 안에서 silent NULL 반환 → 모든 `calHr/calCI = NA` (결과 없음)
   - **우회**: Schuemie 2014 공식 직접 구현
     ```r
     calLogHr <- logHr - null_mean
     calSe    <- sqrt(seLogHr^2 + null_sd^2)
     calCi    <- c(exp(calLogHr - 1.96*calSe), exp(calLogHr + 1.96*calSe))
     calP     <- 2 * pnorm(-abs(calLogHr)/calSe)
     ```
   - `calibrateP()`는 정상 작동 (legacy 버그 영향 없음)

### 5.4 Measurement NC의 구조적 제약 (2026-04-20 정리)

**결론**: 표준 NC conceptSet 경로로는 measurement NC를 넣을 수 없다. 구조적으로 condition/procedure 기반 프레임워크임.

**원인**: estimation spec의 `negativeControlOutcomeCohortDefinition`:
```json
{
  "occurrenceType": "first",
  "detectOnDescendants": true,
  "domains": ["condition", "procedure"]
}
```
→ NC는 concept IDs만 넣으면 framework가 자동으로 "첫 condition/procedure occurrence of concept_id"를 event로 cohort 생성. **threshold logic(value > range_high 등) 주입 hook 없음**.

**왜 domains에 "measurement" 추가로 해결 안 되나**:
- 자동 생성되는 event = "그 검사가 처음 수행된 시점" (surveillance indicator)
- 원하는 event = "첫 이상치 발견 시점" (abnormality)
- OMOP measurement 테이블은 `value_as_number` + `range_high/low` 조합으로 이상치 판단 → framework의 "first occurrence" 로직으로는 불가

**우회 경로 (이론상 존재, 실용적 아님)**:
- primary outcome처럼 CIRCE JSON 수작업으로 threshold cohort 54개 빌드 → `targetComparatorOutcomes`에 regular outcome으로 추가 → R side에서 NC로 간주
- 비용: 54 × dual-unit/bidirectional 변종 = 100+ cohort, 기관별 unit 처리, "수술 무관" justification, OHDSI 선례 부재

**OHDSI 표준 NC는 전부 condition 기반** (Voss 2017 등) — measurement NC catalog 없음. Schuemie empirical calibration tutorial도 condition_era/condition_occurrence 기반만 예시.

**실무 의사결정**:
- primary가 measurement threshold인 연구에서 NC는 **condition outcome 유지**가 표준
- NC-primary ascertainment 구조 불일치는 paper limitation에 명시 (surveillance bias 일부 잡히지 않음)
- Reviewer 지적 시 σ-grid sensitivity (σ=0/0.16/0.3/0.5)로 calibration robustness 증명으로 대응

**출처**: v4 analysis에서 54 condition NC 유지 결정 (`studies/appendectomy/v4_analysis_plan.md` §2.4, §4).

---

## 6. 이슈 해결 패턴

> 상세: `data/reference/issue_history.csv`

- **500 에러**: API 불안정이 아니라 **호출 방식 오류** 가능성 먼저 확인 (Generate GET/POST, expression string/object)
- **estimation 실패 (수시간 후)**: stopOnError=True + 특정 outcome 에러 → stopOnError=False로 변경
- **R 패키지**: Andromeda 0.6.0 필수, duckdb 제거, VS Code R 터미널에서 source() 실행

---

## 7. 파이프라인 + 체크리스트

### 7.0 3계층 저장 구조
- GitHub: 시스템 코드 + 참조 데이터
- Google Drive (`studies/`): 연구별 문서, 코호트, PROGRESS
- Local Desktop: result.zip, CmData, pooled 결과

### 7.1 새 연구 시작 순서
```
0.  연구 폴더 생성 (studies/{연구}/) + CLAUDE.md 포인터 변경
1.  ATLAS에서 코호트 + estimation 설계 (기존 copy → TCO 변경)
2.  ★ Achilles로 기관별 concept 검증 → 기관 선정
3.  feedernet analysis 생성 + import + execution
4.  결과 다운로드 → CmData → IPD pooled → NC calibration
5.  논문 정리
```

### 7.2 결과 다운로드 → IPD pooled 프로세스 (강제 참조)

```
Step 1: result.zip 다운로드
  → API: GET .../execution/{eid}/files/{fid}/download
  → 또는 feedernet UI에서 직접 다운로드
  → 저장: C:\Users\data1\Desktop\atlas_auto_cmdata\results_{연구명}\

Step 2: CmData 추출 (Python)
  → result.zip 안의 cmOutput/CmData_l1_t{T}_c{C}.zip 추출
  → CmData.zip을 다시 unzip → *.sqlite + *.rds
  → 저장: cmData_{연구명}\{기관}\CmData_l1_t{T}_c{C}\*.sqlite

Step 3-4: IPD Pooled + NC Calibration (R) — **R/lib/ipd_pooled.R 사용**

  2026-04-24 v4 canonical (v4_main_365d_analysis_v3_clinicalstate.R) 로직을
  공통 lib으로 추출. Regression test: v4 Chole 30 outcome 전 항목 bit-for-bit
  일치 (hr/ciLb/ciUb/calHr/calP diff = 0).

  신규 연구는 driver 스크립트만 60줄 작성:
  ```r
  Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
  source("R/lib/ipd_pooled.R")
  result <- run_ipd_pooled(list(
    cmdata_root = "C:/Users/data1/Desktop/atlas_auto_cmdata/cmData_{연구}",
    sites = c(...),
    target_id = ..., comparator_id = ...,
    analyses = NULL,                      # or c("a","b","c") for multi-analysis
    primary_outcomes = c(...),
    nc_outcomes = NULL,                   # or explicit; default auto-detect
    risk_window = c(91L, 1185L),
    lookback_days = 365L,
    dual_unit_map = NULL                  # or list("9001"=c(...))
  ))
  write.csv(result$primary, ..., row.names = FALSE)
  ```

  lib이 처리: rowId offset pool → lookback filter → Cyclops LASSO PS
             (caliper search bounds 0.01-20) → 1:1 NN caliper 0.2×SD
             → site-stratified Cox → fitNull (method-of-moments, 54 NC)
             → Schuemie 2014 수동 calibration → E-value.
```

**⚠️ 반드시 지킬 것:**
- **R/lib/ipd_pooled.R 경유**: 연구별 monolithic 스크립트 작성 금지 (2026-04-24 이후)
- CmData 로드는 **DBI::dbConnect(RSQLite::SQLite(), *.sqlite)** 사용 (lib 내부에서 처리)
- `loadCohortMethodData()`는 **Andromeda 버전 호환 문제**로 실패할 수 있음
- `Rscript`로 실행 시 JAVA_HOME 누락 가능 → driver 첫줄에 `Sys.setenv(JAVA_HOME=...)` 필수
- dual-unit outcome (CRP, Neutro#)은 **기관별 unit에 맞는 코호트만 선택**하고 `dual_unit_map`에 pseudo_id → c(variant_ids) 등록
- R 패키지: Andromeda 0.6.0, CohortMethod 4.2.2, duckdb 제거

**Deprecated scripts (lib으로 superseded, 참고용 보존)**:
- `R/v4_main_365d_analysis*.R`, `R/v4_loso_sensitivity*.R`, `R/v4_ipd_*.R`, `R/v4_clinical_*.R` — v4 monolithic
- `R/pooled_analysis/00-04_*.R`, `R/pooled_analysis/ipd_pooled_cyclops*.R` — 구형 4-step pipeline
- `R/allergic_ipd_pilot.R` — 3-site allergic pilot (v1)

### 7.3 교훈
1. 데이터 검증을 estimation 전에 수행
2. estimation은 기존 copy → TCO만 변경 (새로 만들지 말 것)
3. 500 에러 시 호출 방식 먼저 확인
4. CmData 로드는 SQLite 직접 (loadCohortMethodData 금지)
5. result.zip → CmData.zip → sqlite 2단계 unzip 필요

---

## 8. FeatureExtraction unit_concept_id 검증

| 공변량 유형 | unit 영향 |
|---|---|
| Measurement (binary) | 없음 |
| MeasurementValue (continuous) | 있음 — 현재 OFF |
| MeasurementRangeGroup | 없음 — range_low/high NOT NULL만 확인 |

---

## 9. 자동화 Hook

`.claude/settings.json`에 설정된 hook이 매 세션·프롬프트마다 관련 문서를 context에 자동 주입.

| Hook | 동작 | 스크립트 |
|---|---|---|
| **SessionStart** | 세션 시작 시 system_knowledge_base + study_knowledge_base + PROGRESS + IRB protocol 전체 주입 | `.claude/hooks/load_project_docs.sh` |
| **UserPromptSubmit** | 프롬프트에 `분석\|실행\|IPD\|estimation\|calibration\|Cox\|matching\|outcome\|comparator` 키워드 있으면 §5·§7 재주입 | `.claude/hooks/load_analysis_context.sh` |

이유: 메모리·CLAUDE.md는 수동 참조라 Claude가 놓칠 수 있음 → hook은 harness 실행이라 강제됨.

수정·비활성화: `/hooks` 또는 `.claude/settings.json` 직접 편집.

## 10. 시스템 TODO

- [x] measurement unit 전수조사: 13/23기관 완료
- [x] feedernet analysis 생성 API 확인: `POST /projects/{pid}/analysis`
- [ ] client.py에 Generate GET 방식 반영
- [ ] measurement unit 나머지 10기관 수집
