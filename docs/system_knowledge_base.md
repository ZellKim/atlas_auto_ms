# atlas-auto 시스템 지식 베이스

> 신규 연구 시 이 문서를 **처음부터 끝까지 읽고** 시작할 것.
> **API 호출 전 반드시 이 문서를 참조.** 추측으로 호출하지 말 것.

## 참조 데이터 위치

| 데이터 | 파일 |
|--------|------|
| API 엔드포인트 | `data/atlas_reference/atlas_webapi_endpoints.csv` (8 category, pathway 포함) |
| 기관 4종 ID 매핑 (24기관) | `data/site_mapping/site_id_mapping_full.csv` |
| 기관 sourceKey 매핑 | `data/site_mapping/source_key_mapping.csv` |
| **기관 총 환자수·데이터 기간·DB명** | `data/site_mapping/site_summary_23.csv` |
| PRESET FA 목록 (105개) | `data/atlas_reference/atlas_preset_fa_list.csv` |
| ETRI measurement 리스트 | `data/atlas_reference/etri_measurement_list.csv` |
| **Measurement 연구 시작 키트** | `data/measurement/` (README 있음) |
| - 기관별 biomarker 최종 선택 | `data/measurement/site_concept_matrix.csv` |
| - biomarker 안정성 요약 | `data/measurement/stability_summary.csv` |
| - 기관별 unit | `data/measurement/by_site/units_by_site.csv` |
| - Value 분포 (p10-90) | `data/measurement/unit_survey_full.csv`, `data/measurement/v4_surveys/*.csv` |
| - Characterization (FA preset) | `data/measurement/characterization/char_preset_all.csv` |
| **Achilles concept frequency** (23기관×5 domain) | `data/concept_frequency/` (README 있음) |
| - 표준 기관별 dump | `data/concept_frequency/by_site/{CODE}_{domain}.csv` |
| - KCD native vocab | `data/concept_frequency/kcd_vocab/` |
| - OHDSI 공개 benchmark | `data/concept_frequency/benchmark/` |
| R 환경 설정 | `data/reference/r_environment.csv` |
| 이슈 히스토리 | `data/reference/issue_history.csv` |
| **문서 렌더 QA 도구** (DOCX→PDF/PNG) | `data/scripts/render_docx_qa.py` (§10) |

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
| GET | `/pathway-analysis/` | Cohort Pathways 목록 | `content[]` 페이징. base `/pathway-analysis`(하이픈). 전체 17 endpoint는 CSV 참조 |
| POST | `/pathway-analysis/{id}/generation/{sourceKey}` | pathway 실행 | |
| GET | `/pathway-analysis/{id}/generation` | 실행 목록 | **미생성 pathway → 500**(정상, ↓1.4 함정). 생성됨 → status `COMPLETED` |
| GET | `/pathway-analysis/generation/{genId}/result` | 실행 결과 | `{eventCodes, pathwayGroups}` |
| GET | `/conceptset/` | concept set 목록/관리 | `/{id}/expression`=resolved, `/{id}/export`=**zip(bytes)** |
| GET | `/ir/` | Incidence Rate 분석 | 실행=**GET** `/ir/{id}/execute/{sourceKey}`. `/info`=AnalysisInfoDTO[] (status는 executionInfo 내부) |
| GET | `/prediction/` | Patient-Level Prediction | estimation/pathway와 동형(generation→result) |
| GET | `/job/` | 범용 job 상태 | `/job/execution?jobName=` → Page, status `COMPLETED` |
| GET | `/vocabulary/{sourceKey}/info` | vocab 메타 | lookup/identifiers·mapped·recommended는 **POST**(conceptId 배열). 전체는 CSV 참조 |

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
| Empty NC failure | `negativeControlOutcomeCohortDefinition`이 남아 있는데 `negativeControls`와 `conceptSetCrossReference`가 비어 있으면 feedernet이 NC cohort SQL `IN ()`류를 만들며 `syntax error at or near ")"`로 실패 가능. GD v0.1에서 2026-06-21에 10/10 site 실패 확인. |
| cohortDefinitions | feedernet이 export 시 ATLAS에서 **자동 resolve**. spec에 expression 없어도 실행 가능 |
| 500 에러 | **API 불안정이 아니라 호출 방식 오류** 가능성 먼저 확인 |
| pathway generation 500 | `/pathway-analysis/{id}/generation`은 **한 번도 generate 안 한 pathway**에서 500(Spring ConversionFailed) — 경로/호출 오류 아닌 WebAPI 2.12.0 버그. 생성 이력 있으면 200. `get_pathway_generations()`가 []로 처리 (위 "500=호출오류"의 예외 케이스). feedernet site 7/203 live 검증 2026-06 |
| IR 실행 = GET | Incidence Rate 실행은 `GET /ir/{id}/execute/{sourceKey}` (코호트 generate처럼 **GET**, POST 아님). 취소는 `DELETE` 같은 경로 |
| 코호트 cancel = GET | `GET /cohortdefinition/{id}/cancel/{sourceKey}` (cancel도 GET) |
| conceptset export = zip | `/conceptset/{id}/export`는 JSON이 아니라 **zip(bytes)** 반환 → `resp.json()` 금지(`export_concept_set`가 bytes로 처리) |
| vocab lookup = POST | `/vocabulary/{sourceKey}/lookup/{identifiers,mapped,recommended}`는 **POST**(body=conceptId 배열). 단건 `/vocabulary/concept/{id}`만 GET |
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

**Monitor status classification fix (2026-06-21)**:
`EXECUTING_PREPARING` is an active execution state, not a failure. During the
GD v0.2 smoke execution, the raw feedernet API returned `EXECUTING_PREPARING`
for newly started sites, but `data/scripts/v4_phase_e_monitor.py` classified it
as `FAILED` because only `EXECUTING_DOCKER` and `RUNNING` were mapped to
RUNNING. The monitor now maps `EXECUTING_PREPARING`, `EXECUTING_DOCKER`, and
`RUNNING` to `RUNNING`. When reported counts look surprising, verify raw
`executionStatus` before interpreting monitor categories.

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
- Keep ATLAS PS matching ON. 2026-06-19 user-confirmed operational bug:
  turning PS matching off can make feedernet estimation execution error.
  If final HRs come from central IPD pooled analysis, still leave site-level
  PS/matching enabled and ignore ATLAS site-level HRs.
- Appendectomy v4 live ATLAS pattern checked on 2026-06-19: base `212` and
  copied estimations `222`-`227` used `createPs=true`, `matchOnPs=true`,
  `matchOnPsArgs.caliper=10`, `matchOnPsArgs.caliperScale="standardized logit"`,
  `matchOnPsArgs.maxRatio=0`, and `useCovariates=true`; copied `222`-`227`
  used `createPsArgs.stopOnError=false`.
- cohortDefinitions 전부 포함 (T + Cs + 모든 outcome)
- NC 54 items + exclude 110 items 채움
- concept set name `\n` strip
- specification=string (json.dumps)

### 2.4 Execution 취소  [포탈, 단수 project]

```python
session.post(f'{base}/api/v1/project/{pid}/analysis/{aid}/execution/{eid}/cancel')
```

### 2.4a Trigger 패턴 — bulk POST vs sequential (2026-04-26 검증)

**결론**: bulk POST(`cdmIds: [...N개...]`)는 **clean queue에서 안전**. Sequential(1개씩 90s gap)도 안전. 선택 기준 = **속도 vs 큐 부하**.

```python
# 패턴 A: bulk POST (권장 — 큐 비어있고 1 estimation 다중 사이트)
session.post(f'.../execution',
    json={'cdmIds': [273, 312, 318, ...22개], 'researchName': '...', 'executionType': 'ESTIMATION'})
# → 1 POST → 22개 동시 큐 entry (큐가 알아서 처리, 동시 spawn은 ~6개 등 엔진풀 capacity 제한됨)

# 패턴 B: sequential single (구버전 기본 — 보수적)
for cid in cdmIds:
    session.post(f'.../execution', json={'cdmIds': [cid], ...})
    time.sleep(90)
```

**검증 결과 (appendectomy v4.2, PID 5126 artifact name `appendectomy_v8`, 2026-04-26)**:
- Bulk 5 estimation × 22 사이트 = 110 site bulk POST → **0 즉사**
- 같은 시간대 sequential cbc_wbc 22 → 1 fail (5%)
- 즉 bulk가 sequential보다 더 안전했음 (큐 부하 동일 분포)

**과거 issue #13 ("bulk 11/11 즉사") 정정**:
- 원인은 bulk POST 자체가 아니라 **v2 spec 문제 + 큐 부하 + 동시기 다른 사이트 RUNNING** 등 복합 요인
- bulk POST 단독 비난 정당화 안 됨
- 메모리: `feedback_bulk_trigger_safe.md`

**언제 sequential을 쓸까**:
- 큐에 다른 분석 RUNNING 다수 + 추가 부담 회피 원할 때
- 사이트 100개+ 트리거하면서 gradual rate 통제 원할 때
- 그 외 대부분 → bulk 권장 (트리거 시간 ~200x 단축)

**검증 후 중복 cancel — 상태 조회 시 함정 (2026-04-28 기록)**:
v4.2 검증 시퀀스는 (1) 2026-04-26 16:36 sequential trigger 132 + (2) 같은 날 bulk POST 110 (cbc_rbc/chem_hepa/meta_endo/sex_specific/clinical 각 22) 였음. **(2) bulk POST가 안전함을 확인한 즉시 110 중복 execution은 모두 의도적으로 cancel** 함 (사이트 부담 회피). 결과적으로 feedernet API에서 v4.2 5개 분석을 polling 하면 site별로 `[FINISHED_SUCCESSFULLY/WAITING, CANCELED-startedAt-None]` 두 execution이 보임.

**함정**: naïve "latest by id" 로직 (`v4_phase_e_monitor.flatten_latest_per_cdm` 구버전 / 직접 작성한 일회성 poll 스크립트)으로 polling 하면 → 21/22 CANCELED → "v4.2 폭망" false alarm. CLAUDE.md ⛔ 추측 금지 규칙 직접 위반 케이스.

**올바른 read 규칙**:
- `executionStatus == 'CANCELED'` AND `startedAt is None` AND `completedAt is None` AND **그 cdm에 더 이전 execution이 있으면** → preempted-duplicate, 무시. 그 이전의 의미 있는 execution을 latest로 사용
- 단일 execution이거나 startedAt이 있는 CANCELED는 진짜 cancel (예: UUH 2026-04-23 hang cancel 처럼) → 그대로 보고
- `data/scripts/v4_phase_e_monitor.py`에 이 로직 반영 완료 (2026-04-28)
- cloud_monitor는 이미 `e992f2b` commit에서 per-cdm any-state aggregation으로 처리

### 2.4b v4_phase_e_monitor PID-first 리팩토링 (2026-05-29)

**배경**: 기존 monitor는 단일 PID 가정 (`v4_analysis_map.json`에 aid 6개만 hardcode). `--pid 5126` 로 호출해도 v4.1 (PID 5115) aid를 query → 같은 결과를 다른 PID라고 잘못 보고. spec sensitivity 비교 (v4.1 vs v4.2) workflow에서 silent 오류 source.

**근본 fix** (commit pending):
- `discover_analyses(client, pid)` 함수 추가: `/api/v1/projects/{pid}/analysis` 자동 query → aid/name 매핑
- `--map` flag는 explicit override (advanced only)
- state path 자동 suffix: `data/v4_monitor_state_pid{PID}.json`
- results dir 자동 suffix: `…/v4_results/pid{PID}/{analysis_name}/`

**검증**:
- PID 5115 (v4.1) → 6 aids `AD_v4_*_v4` (11034-11044)
- PID 5126 (v4.2) → 6 aids `appendectomy_v8_*` (11070-11075)
- 두 PID 동시 모니터링 가능, state 분리

**다른 연구 적용**:
- allergic_diseases, GLP-1 cancer, 기타 spec sensitivity 비교 시 `--pid {N}` 만 변경. 코드 수정 0.
- 옛 `v4_analysis_map.json`은 보존 (v4.1 historical 참조 + `--map` explicit 호출 가능)
- 옛 `v4_monitor_state.json`은 historical only — 신규 호출은 자동 `v4_monitor_state_pid{PID}.json` 사용

**호환성**:
- `--map`/`--state`/`--results` explicit override 모두 그대로 작동 (backward compat)
- 기본 동작만 PID-aware 자동화로 변경

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

Implementation note (verified 2026-06-10): `R/lib/ipd_pooled.R` calls
`ipd_add_site_covariates()` inside `run_ipd_pooled()` after lookback filtering
and before `ipd_fit_ps()`. The helper adds `nSites - 1` synthetic site dummies
to `pool$covariates` by default. Disable only intentionally with
`config$add_site_covariates = FALSE`. Verification on local R 4.6.0:
`source("R/lib/ipd_pooled.R")` passed after installing `Cyclops 3.7.1`,
`EmpiricalCalibration 3.1.4`, `DBI 1.3.0`, `RSQLite 3.53.1`, and `dplyr 1.2.1`;
a synthetic 3-site Cyclops PS fit completed with 2 site dummies. If broad
dependency installation pulls `duckdb` or `Andromeda 1.x` into the user library,
remove them; this repo still documents `duckdb` as incompatible and Andromeda
0.6.0 as the CmData-compatible line.

**PS covariate 축소 매칭 옵션 (2026-06-26 기록)**:
Large-scale matching에서 caliper 탈락이 과도하면 domain/analysis set 단위뿐 아니라
`covariateId` 단위로 PS 입력 변수를 줄일 수 있다. `CmData`의 `covariates`
테이블은 sparse long format(`rowId`, `covariateId`, `covariateValue`)이므로
`ipd_fit_ps()` 호출 전에 `pool$covariates`와 `pool$covariateRef`를 같은
`keep_ids`로 필터링하면 된다. `outcomes`/follow-up time은 PS 매칭 변수로
넣지 않고, 매칭 후 Cox 단계에서만 붙인다.

```r
pool <- ipd_build_pooled(cmdata_root, sites, target_id, comparator_id)
pool <- ipd_apply_lookback(pool, primary_outcomes, 365L)

keep_ids <- c(
  8507001, 8532001,        # sex
  3, 1003, 2003, 3003,     # age groups 예시
  901,                     # Charlson
  1920                     # visit count
  # + 사전 지정한 condition/drug covariateIds
)

pool$covariates <- pool$covariates[pool$covariates$covariateId %in% keep_ids, ]
pool$covariateRef <- pool$covariateRef[pool$covariateRef$covariateId %in% keep_ids, ]
pool <- ipd_add_site_covariates(pool)

psCoh <- ipd_fit_ps(pool)
matched <- ipd_match_1to1(psCoh)
```

권장 비교 tier: (1) age + sex + site + visit count + Charlson, (2) + 주요
condition confounder, (3) + 주요 drug confounder, (4) full high-dimensional PS.
각 tier마다 matched pairs, post-match SMD, primary HR/CI 변화를 같이 보고
yield 개선이 confounding 악화로 이어졌는지 판단한다.

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

### 5.5 Baseline Table 1 (publication-ready, exact N) — 2026-04-28 확립

**원칙**: CmData sqlite의 row-level data를 직접 카운트해서 정확한 N + signed SMD 산출. CohortMethod의 `prepareTable1`/`createCmTable1`는 미국 표준 concept ID(Race/Ethnicity 등)에 의존해 한국 CDM에서 crash. 사용자 옛 패턴(prop × N 복원)은 round-off 손실.

**핵심 차이**:

| 접근 | 정확도 | 한국 CDM 호환 |
|---|---|---|
| `CohortMethod::createCmTable1()` (default spec) | exact | ❌ Race/Ethnicity 부재로 crash |
| 사용자 옛 `prepareTable1()` + prop × N | ±수십 (round-off) | ✅ 함수 자체는 robust |
| **sqlite 직접 카운트** (권장) | exact (machine epsilon) | ✅ |

**구현 패턴** (R 스크립트, 표준 위치 `studies/{연구}/R/run_*_table1_exact.R`):

```r
# 1) 16 site sqlite의 covariates 테이블에서 spec covariateId만 SELECT
con <- dbConnect(SQLite(), site_sqlite)
cov <- dbGetQuery(con, sprintf("SELECT rowId, covariateId, covariateValue
                                 FROM covariates WHERE covariateId IN (%s)", cid_sql))
coh <- dbGetQuery(con, "SELECT rowId, treatment FROM cohorts")

# 2) site offset (1e8 × site_index) 후 pool
cov[, rowId := as.integer(rowId) + offset]
cov[, covariateId := as.numeric(covariateId)]   # drug ID는 int32 overflow → numeric 필수

# 3) Lookback 일관성 — primary 분석과 동일 365d 적용
prior_ids <- outcomes WHERE outcomeId IN primary AND daysToEvent IN [-365, 0)
coh_pool <- coh_pool[!rowId %in% prior_ids]

# 4) Pre/post N exact count
nT_pre  <- coh_pool[treatment == 1, .N]      # primary.csv N과 정확히 일치해야
nT_post <- coh_pool[rowId %in% matched_ids & treatment == 1, .N]

# 5) Cov sum per (covariateId, treatment) → exact 환자 N
sum_T <- cov[treatment == 1, sum(covariateValue), by = covariateId]
mean_T <- sum_T / nT
SMD <- (mean_T - mean_C) / sqrt((mean_T*(1-mean_T) + mean_C*(1-mean_C)) / 2)
```

**Spec 선정 (Korean CDM 적응)**:
- Demographics: analysisId 1 (gender 8507/8532), analysisId 3 (age group, 5y bands)
- Medical history: analysisId 210, **default spec covariateIds 무시** + 우리 데이터 top-prevalence로 동적 선택
- Medication: analysisId 410, 동일 패턴
- Race/Ethnicity (analysisId 4, 5) **제외** — Korean CDM 미수집

**검증 체크리스트**:
1. Sanity: `meanT_pre × nT_pre`로 계산한 sum vs sqlite 직접 sum의 max diff < 1e-10 (machine epsilon)
2. Pre-match N이 `primary.csv`의 nT, nC와 정확히 일치 (lookback 적용 확인)
3. Post-match N이 matched.rds rowId 수의 절반과 정확히 일치

**SMD 부호 관행**: 기본 signed (T-C / pooled SD). `+0.00`/`-0.00`은 cosmetic으로 `0.00`으로 통일. \|SMD\|>0.1 임계값은 footnote 명시.

**<5 cell suppression**: 없음. CmData는 patient-level이고 feedernet은 row data 그대로 전송. 옛 NHIS/HIRA 집계 결과처럼 <5 마스킹 걱정 불필요.

**재사용 라이브러리**: `R/lib/baseline_table1.R` — `build_table1(config)` 한 호출로 끝.

```r
source("R/lib/baseline_table1.R")
result <- build_table1(list(
  cmdata_root      = ".../cmData_<study>",
  target_id        = 1290L, comparator_id = 1287L,
  primary_outcomes = c(1288L, 1289L), lookback_days = 365L,
  matched_rds      = ".../matched.rds",
  spec_top_n_cond  = 10L, spec_top_n_drug = 8L
))
fwrite(result$table1, "table1_publication.csv")     # paper-ready
fwrite(result$balance, "table1_balance_exact_N.csv") # 모든 spec covariate 상세
```

**Multi-analysis 연구 (v4 스타일)**: 한 사이트에 여러 analysis 디렉토리가 있고(예: `cbc_wbc/`, `chem_hepa/`) primary outcome이 분석마다 분산되어 있을 때:

```r
build_table1(list(
  cmdata_root        = ".../cmData_<study>",
  analysis_subdir    = "v4_1a_cbc_wbc",          # site/analysis_subdir/CmData_*
  prior_excluded_ids = full_union_lookback_ids,   # 호출자가 모든 analysis의 outcomes union
  ...
))
```
이유: 각 analysis sqlite는 자기 outcomes만 보유 → full-union lookback은 caller가 사전 계산 후 주입. `analysis_subdir = NULL`(default)일 때는 single-analysis 경로 (`{site}/CmData_l1_t<T>_c<C>/`).

**참조 구현**: `studies/allergic_diseases/R/run_v7_table1_exact.R` (v7 16-site standalone, 2026-04-28) ↔ `R/run_v7_table1_via_lib.R` (lib 호출, bit-for-bit identical regression 통과).

### 5.6 Multi-model Progressive Cox from CmData (Park 2023 비교용) — 2026-04-29 확립

**가능함**: CmData 의 covariates 테이블이 patient-level (sparse long format `rowId × covariateId × covariateValue`)이라 PS 매칭 없이 표준 Cox 회귀 progressive adjustment 분석 가능. Park 2023 / 사용자 옛 statin 분석과 동일한 4-5 model progressive 구조를 구현할 수 있다.

**활용 동기**:
- Reviewer가 "PS-matched HR만 있고 traditional Cox adjusted HR 없냐" 질문 시 답변
- Park 2023 (NHIS) 같은 선행연구의 adjusted HR과 직접 비교 행 생성
- PS matching이 적절했음을 표준 회귀 결과와 일치 확인 (robustness)

**데이터 구조**:
```
cohorts:    rowId, personId, treatment, daysToObsEnd, cohortStartDate ...
outcomes:   rowId, outcomeId, daysToEvent
covariates: rowId, covariateId, covariateValue   (sparse: 0이면 미저장)
covariateRef: covariateId, covariateName
```

**Wide format 변환 (R, 약 15개 핵심 변수만)**:
```r
SEL <- list(
  male       = 8507001L, female  = 8532001L,
  age_0_4    = 3L,       age_5_9 = 1003L,    age_10_14 = 2003L, age_15_19 = 3003L,
  visit_count= 1920L,    charlson= 901L,
  resp_drug  = 21605007410, sense_drug = 21603550410,
  # + 기타 specific condition/drug covariateIds
)
cov_w <- dcast(cov_long, rowId ~ covariateId, value.var = "covariateValue", fill = 0)
# 컬럼명 friendly로 rename
```

**Categorical 통합 (paper-friendly)**:
```r
# one-hot binary 4개 → factor 1개
final[, age_group := fcase(
  age_0_4 == 1, "0-4", age_5_9 == 1, "5-9",
  age_10_14 == 1, "10-14", age_15_19 == 1, "15-19")]
final[, age_group := factor(age_group, levels = c("0-4","5-9","10-14","15-19"))]
final[, age_group := relevel(age_group, ref = "5-9")]   # 큰 군 reference
final[, sex := factor(fcase(male == 1, "Male", female == 1, "Female"),
                      levels = c("Female","Male"))]
```

**Time/event 컬럼 (Cox 입력)**:
```r
oc <- outcomes[outcomeId == primary_oid &
               daysToEvent >= risk_start & daysToEvent <= risk_end,
               .(adhd_day = min(daysToEvent)), by = rowId]
final <- merge(coh, oc, all.x = TRUE)
final[, max_fu := pmin(daysToObsEnd, risk_end)]
final[, event  := as.integer(!is.na(adhd_day) & adhd_day <= max_fu)]
final[, time   := ifelse(event == 1, adhd_day, max_fu)]
```

**Progressive Cox (Park 2023 / 옛 statin 패턴)**:
```r
m0 <- coxph(Surv(time, event) ~ treatment + strata(site), data = final)             # crude
m1 <- update(m0, . ~ . + sex + age_group)                                            # demographics
m2 <- update(m1, . ~ . + visit_count + charlson)                                     # utilization + comorb
m3 <- update(m2, . ~ . + resp_drug + sense_drug)                                     # drug history
# + Cox formula별 HR/CI/p 추출하여 progressive table
```

**검증 체크**:
1. m0의 treatment HR은 raw Cox 결과 (PS 매칭 안 한 경우, 큰 imbalance 반영)
2. m3가 가장 보정 강하지만, 1만 covariate 중 ~15만 사용하므로 PS LASSO보다 약함
3. PS-matched + NC calibrated HR이 m3 HR과 비슷하면 → 우리 PS 결과 robust
4. 큰 차이 나면 → unmeasured confounding 가능성 시사

**참조 스크립트**:
- `studies/allergic_diseases/R/show_analysis_table_head.R` — wide-format 변환 + categorical 통합 데모
- `studies/allergic_diseases/R/check_covariate_level.R` — CmData 환자레벨 구조 검증

**한계**:
- 사용 변수 선택은 manual curation 필요 (1만 covariate 다 못 넣음)
- PS LASSO만큼 high-dim 보정 약함 (그래서 PS-matched가 primary)
- Multi-model은 supplementary / Park 비교 행 용도가 적합

### 5.7 Fast LOSO via `ipd_loso_fast()` — 2026-05-05 확립

**Naive LOSO (run_v4_*_loso.R 패턴)**: 60 iter 동안 매번 cmData 로드 + Pool 빌드 + Cyclops LASSO PSM 재fit + match + Cox + null refit + calibrate. **iter당 ~10분 → 60 iter 총 ~10시간**.

**Smart LOSO (`ipd_loso_fast()`)**: primary 결과의 matched cohort + null fit 재활용. iter마다 site별 row drop + Cox만 재실행. **iter당 ~30초 → 60 iter 총 ~10분 (~70× 빠름)**.

**가능한 이유**: `run_ipd_pooled()` 의 Cyclops LASSO PSM이 기본적으로 **site indicator를 covariate로 포함**하므로 PS 모델은 이미 site-aware. 구현 위치는 `ipd_add_site_covariates()` 호출부다. LOSO는 본질적으로 "이 site의 데이터를 분석에서 빼면" 인데, site-stratified Cox에 한 stratum이 없는 것과 등가 → 매칭된 cohort에서 그 site 행만 drop하면 됨.

**API**:
```r
res <- run_ipd_pooled(config)              # primary 1회 (~15-30 min)
loso <- ipd_loso_fast(
  matched     = res$matched,
  outcomes    = res$pool$outcomes,
  primary_ids = config$primary_outcomes,
  sites       = config$sites,
  null_fit    = res$null,                  # primary null 재사용 (fast path)
  risk_window = config$risk_window,
  recompute_null = FALSE                    # TRUE 면 iter마다 nc로 null 재fit (slow)
)
```

**Driver 패턴**: `studies/appendectomy/R/run_v4_1_15site_beta_loso_fast.R` 참조. 다른 연구에서 SITES + outcome IDs + cmData_root 만 변경하면 재사용.

**Fast vs Full LOSO 차이** (검증 2026-05-05, appendectomy v4.1 15-site β):

| 항목 | Full LOSO | Fast LOSO |
|---|---|---|
| 시간 (60 iter) | ~10시간 | ~10분 |
| Statistical question | "이 site가 study에 없었다면?" — full pipeline 재실행 | "이 site의 데이터를 분석에서만 뺐다면?" — cohort 고정, Cox만 재실행 |
| Null fit | iter마다 재fit (per-cohort) | primary 1회 결과 재사용 |
| 결과 차이 (15-site appendectomy 예) | Chole bio retain 21/23, Hernia bio 7/16, protective core 5 | Chole bio 19/23, Hernia bio 13/16, protective core 6 |
| 보수성 | 더 보수적 (null이 iter별로 변동) | 약간 더 permissive |

**언제 어느 것?**
- **Paper 제출용 LOSO 검증**: Full LOSO (보수적, gold standard)
- **빠른 sensitivity check / 다른 분석 비교 / 다기관 robustness 진단**: Fast LOSO 충분
- 두 결과가 큰 차이 (예: protective core 5 vs 8 등)면 PS 모델이 site-imbalanced → site indicator coefficient 점검 + null heterogeneity 평가

**경고**:
- `recompute_null=TRUE` 옵션은 nc outcomes를 가지고 iter별 null 재fit을 하지만 여전히 PSM은 fixed. 더 정확한 보정이지만 full LOSO와 같진 않음. 시간은 ~30분-1시간 (Cox + null fit per iter).
- matched cohort에 `site` 컬럼 필요. `ipd_match_1to1` 출력은 site 보존하지만 외부 변환 시 누락 주의.

### 5.8 Build script SRC path 관리 (silent staleness 방지) — 2026-05-05 교훈

**증상**: `data/scripts/build_etable*.py` 같은 supplementary 빌드 스크립트가 SRC 경로를 hardcode 하고 있는데, 그 경로의 분석 spec과 paper 본문 spec이 silent하게 어긋남. 결과: paper Table 2 cHR 0.17 + supplementary eTable4 cHR 0.21 같은 내부 불일치 — reviewer 1차 catch 위험.

**전형적 시나리오 (2026-05-05 appendectomy 사례)**:
- paper Tables 1-4: adam 머신 `v4_1_15site_beta_primary` (β-spec, 15-site, lookback 365-30) 출처
- 사용자가 PC를 data1으로 옮김
- 누군가 `build_etable4.py` 를 data1에서 재실행 — script SRC가 data1의 `v4_pooled_output/v4_fu365d_primary.csv` 가리킴
- 그러나 그 파일은 옛 α-spec (lookback 365 strict, no skip_recent_days, 16-site) regression test 결과
- → eTable4 가 다른 분석에서 만들어졌는데 paper와 같은 source인 것처럼 commit됨

**예방 패턴**:

1. **Build script header에 source spec 명시**:
   ```python
   """
   eTable X: ...
   Source: paper β analysis (15 sites, Full-Union 365-30 lookback) at <path>.
   Reproduces <reference machine/run> bit-for-bit (verified <date>: <key numbers>).
   """
   ```

2. **Cross-check paper claim 자동 verify**: build script 끝에 paper의 핵심 N + sig count 와 generated 결과 비교 print:
   ```python
   # End of script:
   print(f'\n=== Paper claim cross-check ===')
   for stratum, expected_sig, expected_N in PAPER_CLAIMS:
       actual_sig = ...; actual_N = ...
       match = '✓' if actual_sig == expected_sig and actual_N == expected_N else '✗'
       print(f'  {stratum}: paper {expected_sig}/{expected_N} vs run {actual_sig}/{actual_N} {match}')
   ```

3. **Spec 변경 시 SRC 경로도 따라 변경 (또는 스크립트 새로 작성)**: paper β로 업그레이드할 때 build_etable4.py의 SRC도 함께 갱신. 옛 α regression test는 별도 파일/path로 유지.

4. **Cross-machine 작업 시 cmData 동일성 우선 검증**: PC 옮긴 직후 primary 1회 재실행 후 N + 핵심 cHR 검증해야 paper와 supplementary 정합 보장됨. 검증 안 하고 supplementary만 재빌드 → silent staleness.

**관련 메모리**: `feedback_build_script_src_path.md` (글로벌 메모리에 등재).

---

## 6. 이슈 해결 패턴

> 상세: `data/reference/issue_history.csv`

- **500 에러**: API 불안정이 아니라 **호출 방식 오류** 가능성 먼저 확인 (Generate GET/POST, expression string/object)
- **estimation 실패 (수시간 후)**: stopOnError=True + 특정 outcome 에러 → stopOnError=False로 변경
- **estimation 실패 (PS matching off)**: 2026-06-19 사용자 확인 ATLAS 버그. 최종 IPD pooled에서 ATLAS site-level matching을 쓰지 않더라도 ATLAS/feedernet package에서는 PS matching을 켜둔다. Appendectomy v4에서 확인한 workaround는 `matchOnPs=true`, `caliper=10`, `maxRatio=0`, `stopOnError=false`.
- **estimation 실패 (diagnostics export)**: 2026-06-21 GD v0.2에서 EUMC/MJH가 `exportDiagnostics - preference_score_dist table` 직후 `FATAL readr write_delim is.data.frame(x) is not TRUE`로 실패. 같은 spec에서 8/10 sites는 성공했으므로 global spec/NC 문제와 구분. site-specific diagnostics-export/data-shape edge case로 분류하고, 실패 상태에서는 files API가 code 7020으로 result.zip 다운로드를 막는다.
- **MJH historical site-quality caveat**: Appendectomy v4 measurement-estimation execution excluded MJH before execution (`data/scripts/v4_phase_d_execute.py`, `EXCLUDED_CODES = {'MJH'}`). The recorded reason was observation-period median `53` days, `46.5%` with less than `30` days, and only `1` qualifying target after the `365`-day prior-observation requirement. MJH may still have substantial measurement rows, so distinguish "measurement volume exists" from "site is estimation-ready with clean observation-period/unit structure." For GD, see `studies/gestational_dysglycemia/docs/mjh_site_quality_review_v0.1.md`.
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
  → 저장: {연구}/cmData/{기관}/CmData_l1_t{T}_c{C}/*.sqlite
  (2026-04-24 이후 계층: C:\Users\data1\Desktop\atlas_auto_cmdata\{study}\[v{N}\]{cmData,results,pooled_output})

Step 3-4: IPD Pooled + NC Calibration (R) — **R/lib/ipd_pooled.R 사용**

  2026-04-24 v4 canonical (v4_main_365d_analysis_v3_clinicalstate.R) 로직을
  공통 lib으로 추출. Regression test: v4 Chole 30 outcome 전 항목 bit-for-bit
  일치 (hr/ciLb/ciUb/calHr/calP diff = 0).

  신규 연구는 driver 스크립트만 60줄 작성:
  ```r
  Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
  source("R/lib/ipd_pooled.R")
  result <- run_ipd_pooled(list(
    cmdata_root = "C:/Users/data1/Desktop/atlas_auto_cmdata/{연구}/cmData",
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

## 10. 문서 렌더 QA — DOCX → PDF/PNG (캐노니컬 도구, 2026-06-30 확립)

**원고/보충 DOCX를 렌더해서 시각·구조 QA 할 때는 매번 즉석 스크립트 짜지 말고 이 도구 사용**:

```bash
python data/scripts/render_docx_qa.py <원고.docx>
# 출력: <docx 디렉터리>/render_qa_<stem>/  (PDF + page_01.png… + contact_sheet.png + qa_report.md)
python data/scripts/render_docx_qa.py ms.docx --out render_qa_ms --dpi 150 --backend chrome
python data/scripts/render_docx_qa.py already.pdf   # PDF 입력이면 변환 건너뛰고 PNG/QA만
```

**백엔드 자동 폴백** (`--backend auto` 기본, 우선순위 **word → soffice → chrome**):
| 백엔드 | 동작 | 비고 |
|---|---|---|
| `word` | MS Word COM `ExportAsFixedFormat` | **최고 충실도** — reviewer가 Word로 열었을 때 실제 페이지 레이아웃 그대로. 첫 export는 cold-start로 60~120초 걸릴 수 있어 `--word-timeout` 기본 180s. timeout 초과 시 폴백 |
| `soffice` | LibreOffice headless `--convert-to pdf` | 설치 시 빠르고 충실. **현재 이 PC에 미설치** |
| `chrome` | DOCX→HTML(mammoth)→Chrome/Edge `--headless --print-to-pdf` | 브라우저만 있으면 어디서든(최종 폴백). HTML 재배치라 Word 페이지와 pixel 일치 X (내용·표·그림·mojibake 검수엔 충분) |

`qa_report.md` 자동 산출: 페이지 수, 단락/표 shape/section orientation(python-docx), **mojibake 스캔**(U+FFFD·literal `??` 카운트 → PASS/CHECK).

**⚠️ 함정 — Word COM은 데드락이 아니라 "느린 cold-start"** (2026-06-30 검증·정정):
- 첫 `ExportAsFixedFormat` 호출이 PDF 엔진을 초기화하느라 이미지 많은 문서에서 **60~120초** 걸림. 짧은 timeout(45~90s)으로 기다리면 hang으로 **오진**하기 쉬움(실제로 처음에 그렇게 오진했음).
- subprocess + `--word-timeout 120` 이상으로 주면 **정상 렌더 확인됨**(260623 원고 11페이지, pixel-exact Word 레이아웃). → 그래서 auto 우선순위를 word로 둠.
- `Documents.Open`은 빠르고 렌더 단계만 느린 게 정상 동작. 즉 Office만 있으면 이 도구로 **Word 렌더가 기본 경로**.
- 정말 멈추는 환경(데스크톱 분리 등)이면 timeout 후 자동으로 soffice→chrome 폴백하므로 어디서든 결과는 나옴.

**의존성**: `pypdfium2`(PDF→PNG), `Pillow`(contact sheet), `mammoth`(chrome 백엔드용 DOCX→HTML), `python-docx`(구조 스캔). 없으면 해당 기능만 graceful degrade.

**탄생 배경** (이 도구가 생긴 이유): 2026-06-30 Antibiotics 원고 렌더 QA 갱신 작업 중, Word COM의 느린 cold-start를 데드락으로 오진해 짧은 timeout으로 여러 번 잘라먹으며 시간 낭비. 매 연구 반복되는 작업인데 글로벌 자산이 없어서 매번 재발명하던 것을, 백엔드 폴백 + 충분한 timeout으로 캡슐화해 도구화.

---

## 11. 시스템 TODO

- [x] measurement unit 전수조사: 13/23기관 완료
- [x] feedernet analysis 생성 API 확인: `POST /projects/{pid}/analysis`
- [ ] client.py에 Generate GET 방식 반영
- [ ] measurement unit 나머지 10기관 수집
