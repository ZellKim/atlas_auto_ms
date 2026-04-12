# atlas-auto 프로젝트 진행 상황

**repo**: https://github.com/ZellKim/atlas_auto_ms
**최종 업데이트**: 2026-04-12

---

## 전체 파이프라인 목표

```
연구설계 YAML → 코호트 JSON → ATLAS 업로드 → Estimation 실행 → 결과 다운로드 → IPD Pooled Analysis
├─────────────────── Python (atlas-auto) ───────────────────┤  ├──── R ────┤
```

---

## 1. Python 패키지 (완료, push됨)

### src/atlas_auto/

| 모듈 | 상태 | 역할 |
|------|:----:|------|
| `client.py` | ✅ 완료 | feedernet 포탈 로그인 + 기관별 WebAPI 클라이언트 |
| `builder.py` | ✅ 완료 | Estimation JSON 스펙 빌더 (TCO, PS, Cox 설정) |
| `cohort_designer.py` | ✅ 완료 | YAML 코호트 정의 → ATLAS CIRCE JSON 자동 변환 |
| `protocol.py` | ✅ 완료 | StudyProtocol: YAML 하나로 전체 파이프라인 오케스트레이션 |
| `runner.py` | ✅ 완료 | 본원(R 직접실행) + 타기관(API) 통합 실행 |
| `cli.py` | ✅ 완료 | CLI: protocol, run, status, download, concepts |
| `data/concepts.py` | ✅ 완료 | OMOP Concept ID 레퍼런스 (300+ concepts) |

### 지원 기능

- feedernet 포탈 로그인 (이메일/PW, 쿠키, Bearer 토큰)
- 기관 ATLAS 연결 (group_id/site_id 또는 URL 파싱)
- 코호트 CRUD + Generate + 완료 대기
- Estimation Import + 실행 + 완료 대기 + 결과 다운로드
- 포탈 프로젝트/Analysis 실행 트리거 + 상태 모니터링
- 다기관 result.zip 일괄 다운로드
- YAML 연구설계 → 코호트 JSON 자동 생성 (5가지 domain 지원)
- dry run 모드 (JSON만 생성, ATLAS 실행 안 함)

---

## 2. 현재 진행중인 Estimation 실행 (2026-04-11)

### Analysis 10957: v7b_noStop (E01_E04_clinical_ms_v7b_maxCohort50k_noStop)

**프로젝트 2908 / Analysis 10957**
- 설정: maxCohortSize=50000, stopOnError=false
- 최초 실행: 2026-04-07
- 전체 기관 실행 트리거: 2026-04-11

| 상태 | 수 | 기관 |
|------|:--:|------|
| COMPLETE | 6 | 아주대, 중앙대, 충남대, 대구동산(06), 순천향 서울, 창원경상국립대 |
| RUNNING | 12 | 동탄성심, 대구가톨릭대, 대구동산(05), 이화의료원, 울산대, 건양대, 순천향 천안, 강원대, 강동경희대, 강동성심, 제천명지, 국제성모 |
| WAITING | 7 | 원광대, 순천향 부천, 부산대, 경희의료원, 원자력병원, 경상국립대, 동산병원 |
| FAILED | 4 | 명지, 순천향 구미, 부천 세종, 인천 세종 |

### Analysis 10961: biomarker_v1 (B01_B23_biomarker_ms_v1)

**프로젝트 2908 / Analysis 10961**
- 설정: maxCohortSize=50000, stopOnError=false
- 최초 실행 (본원만): 2026-04-08
- 전체 기관 실행 트리거: 2026-04-11

| 상태 | 수 | 기관 |
|------|:--:|------|
| COMPLETE | 1 | 강동경희대(본원, 9h 53m) |
| 신규 트리거 | 28 | 나머지 전체 기관 |

---

## 3. Cloud 모니터링 (신규, 2026-04-11)

### cloud_monitor/

feedernet estimation 실행 상태를 자동 모니터링하여 Telegram으로 알림.

| 파일 | 역할 |
|------|------|
| `cloud_monitor/main.py` | Cloud Function - 상태 체크 + Telegram 알림 |
| `cloud_monitor/requirements.txt` | 의존성 (functions-framework, requests, google-cloud-storage) |
| `cloud_monitor/DEPLOY.md` | GCP 배포 가이드 |

**아키텍처:**
```
Cloud Scheduler (매 1시간, KST)
    ↓ HTTP trigger
Cloud Function (feedernet-monitor)
    ↓
    1. feedernet 로그인
    2. Analysis 10957, 10961 상태 조회
    3. 이전 상태와 비교 (GCS에 저장)
    4. 완료 기관 증가 시 → Telegram 알림
    5. 전체 완료 시 → "ALL COMPLETE" 알림
    6. 변화 없으면 → 알림 안 함 (로그만)
```

**배포 정보:**
- GCP Project: `investment-os-chain`
- Region: `us-east1`
- Function: `feedernet-monitor`
- Scheduler: `feedernet-monitor-trigger` (매 정시)
- 상태 저장: `gs://investment-os-regiem-state/monitor/feedernet_monitor_state.json`
- 비용: $0/월 (무료 티어)

---

## 4. R 코드 (수정 필요)

### 현재 상태

| 파일 | 상태 | 문제 |
|------|:----:|------|
| `R/pooled_analysis.R` | ❌ 잘못됨 | meta-analysis(DL/Bayesian)로 작성. IPD pooled가 아님 |
| `R/run_pooled.R` | ❌ 잘못됨 | 위와 동일 |
| `R/install_dependencies.R` | ⚠️ 부분 | survival, MatchIt 등 IPD용 패키지 누락 |

### 필요한 IPD Pooled Analysis 워크플로우

```
1. 각 기관 result.zip에서 환자 개별 데이터 추출
   - StudyPop*.rds (subjectId, treatment, survivalTime, outcomeCount)
   - Ps*.rds (subjectId, propensityScore, preferenceScore)
   - CmData*.zip (전체 공변량 SQLite) — PS 재추정 시 필요

2. 전체 기관 데이터 합침
   - rbind로 환자 데이터 통합
   - site 변수 추가 (기관 식별)

3. PS 재추정 & 재매칭
   - site 포함하여 PS 재추정
   - 기관별로 재매칭 (1:1 또는 1:N)

4. Cox regression
   - site-stratified Cox regression (strata = site)
   - 또는 site를 공변량으로 포함

5. 결과 산출
   - Hazard ratio + 95% CI
   - Kaplan-Meier 곡선
   - Forest plot (기관별 + pooled)
```

### result.zip 내 환자수준 데이터 구조 (확인됨)

```
result.zip/script/extras/result/cmOutput/
├── CmData_l1_t1072_c1074.zip      # 환자별 공변량 (SQLite)
├── StudyPop_l1_t1072_c1074_*.rds   # 환자별 생존 데이터 (33개)
├── Ps_l1_t1072_c1074_*.rds         # 환자별 PS (36개)
├── StratPop_l1_t1072_c1074_*.rds   # PS 층화 데이터 (33개)
└── om_*.rds                        # 결과 모델 (193개)
```

---

## 5. 예제 & 문서 (완료, push됨)

| 파일 | 상태 |
|------|:----:|
| `examples/study_protocol_example.yaml` | ✅ 연구설계 YAML 템플릿 |
| `examples/config_example.yaml` | ✅ 인증/DB 설정 템플릿 |
| `examples/quick_start.py` | ✅ 단계별 예제 |
| `examples/new_study_from_scratch.py` | ✅ 새 연구 설계 예제 |
| `examples/download_results.py` | ✅ 결과 다운로드 예제 |
| `README.md` | ✅ 전체 사용 문서 |
| `.gitignore` | ✅ credentials, 대용량 파일 제외 |
| `pyproject.toml` | ✅ pip install 지원 |

---

## 6. git에 포함되지 않는 것 (.gitignore)

| 폴더 | 이유 |
|------|------|
| `automation/` | 레거시 스크립트, 하드코딩된 credentials (비밀번호 평문) |
| `results/` | 대용량 result.zip (수백 MB) |
| `estimation_model/` | 기존 R 패키지 (E01_E04_clinical_ms_v6_nomatch) |
| `tool_package/` | 참고용 Data2Evidence 패키지 |
| `config.yaml` | feedernet 비밀번호 포함 |

---

## 7. 커스텀 R 패키지 (바이오마커 기술통계) — 진행중

### 목적

현재 biomarker estimation(CohortMethod)은 이진 이벤트 발생률만 비교.
바이오마커의 **연속값 기술통계**(평균, SD, median, IQR)와 **수술 전후 변화량** 분석이 필요.

### 접근 방식

feedernet에서 실행하는 건 결국 R 패키지 zip → Docker 실행.
ATLAS Estimation skeleton 구조를 유지하면서 `execute()` 안에서 measurement 테이블을 직접 쿼리하는 커스텀 패키지를 만들어 배포.

```
커스텀 R 패키지/
├── DESCRIPTION
├── NAMESPACE
├── R/Main.R          # execute() — measurement 쿼리 + 기술통계
├── inst/settings/    # 바이오마커 concept ID 목록
├── extras/CodeToRun.R
└── renv.lock
```

### feedernet 업로드 흐름 (API 확인 완료, 2026-04-12)

feedernet 포탈에서 analysis에 ATLAS estimation을 연결하는 전체 API 흐름:

```
1. POST /api/v1/projects/{pid}/analysis                        → analysis 생성 (name)
2. GET  /api/v1/projects/{pid}/analysis/{aid}/atlas             → ATLAS 기관 목록
3. GET  /api/v1/projects/{pid}/analysis/{aid}/atlas/{atlasId}   → 해당 ATLAS의 estimation 목록
4. POST /api/v1/projects/{pid}/analysis/{aid}/atlas/{atlasId}   → estimation import
   body: {atlasResearchId: <id>, atlasResearchName: "<name>", researchType: "ESTIMATION"}
   → feedernet이 ATLAS에서 estimationZip을 자동 생성/다운로드하여 research에 연결
5. POST /api/v1/project/{pid}/analysis/{aid}/execution          → 실행 트리거
   body: {researchName: "<name>", executionType: "ESTIMATION", cdmIds: [...]}
```

### 커스텀 R 코드 실행의 제약 (2026-04-12 확인)

**결론: API로는 커스텀 zip 업로드 불가**

- feedernet은 ATLAS에서 zip을 자동 생성해서 가져오는 구조
- API로 zip 파일 직접 업로드/교체하는 엔드포인트 없음 (415 Unsupported Media Type)
- ATLAS WebAPI에서 estimation zip 다운로드도 500 에러 (feedernet 내부 전용)
- researchType은 ESTIMATION, PREDICTION 2종만 지원

### 가능한 우회 방안

| 방안 | 설명 | 제약 |
|------|------|------|
| **A. 웹 포탈 수동 업로드** | feedernet UI에서 zip 직접 업로드 가능 여부 확인 필요 | 미확인 |
| **B. FeatureExtraction covariate** | estimation spec에 `MeasurementValueLongTerm: true` 등 설정 → baseline characteristics에 바이오마커 mean/SD 포함 | **수술 전(baseline)만** 가능, 수술 후 시간 구간별 불가 |
| **C. 에비드넷 문의** | 커스텀 R 패키지 배포 방법 공식 문의 | 시간 소요 |

### 분석 설계 (테스트용)

- **Target**: E01_Appendectomy (cohort 1072)
- **시간 구간**: pre_365d, post_30d, post_90d, post_365d, post_1y+
- **바이오마커 23종**: WBC, Neutrophil, Lymphocyte, Eosinophil, Monocyte, Basophil, CRP, ESR, RF, ANA, Glucose(DM/preDM), HbA1c, LDL, TG, HDL, GFR, Uric acid, ALT, GGT, ALP, Albumin, Hemoglobin
- **출력**: 구간별 N, mean, SD, median, Q1, Q3, min, max (요약 통계만, 환자 개인정보 없음)

### 참고: 기존 estimation 패키지 구조

`estimation_model/E01_E04_clinical_ms_v6_nomatch/` 참조:
- R 패키지 표준 구조 (DESCRIPTION, NAMESPACE, R/, inst/, extras/)
- `R/Main.R`의 `execute()` 함수가 진입점
- feedernet Docker가 `connectionDetails`, `cdmDatabaseSchema` 등을 주입
- 출력은 `outputFolder`에 저장 → result.zip으로 반환

---

## TODO

- [ ] **커스텀 R 패키지 제작 (바이오마커 기술통계)**
  - [x] feedernet 업로드 API 흐름 전체 확인 (Step 1~5)
  - [x] 커스텀 zip 업로드 가능 여부 API 탐색 → 불가 확인
  - [ ] feedernet 웹 포탈에서 zip 직접 업로드 가능 여부 확인
  - [ ] 우회 방안 결정 (웹 업로드 / FeatureExtraction covariate / 에비드넷 문의)
  - [ ] R 패키지 skeleton 작성 (measurement 쿼리 + 기술통계 요약)
  - [ ] KHNMC(본원)에서 테스트 실행
  - [ ] 성공 시 전체 기관 배포
- [ ] `R/pooled_analysis.R`를 IPD pooled analysis로 재작성
  - [ ] result.zip에서 StudyPop/Ps/CmData 추출
  - [ ] 다기관 환자 데이터 합침 + site 변수
  - [ ] PS 재추정 & 재매칭
  - [ ] Site-stratified Cox regression
  - [ ] Kaplan-Meier + Forest plot
- [ ] 로컬에 있는 기존 IPD pooled R 코드 찾아서 반영
- [ ] `R/install_dependencies.R`에 survival, MatchIt 등 추가
- [ ] README.md의 R 섹션을 IPD pooled analysis로 수정
- [ ] v7b, biomarker 전체 기관 estimation 완료 후 결과 다운로드
- [ ] FAILED 기관 원인 파악 (명지, 순천향 구미, 부천/인천 세종)
- [ ] Cloud 모니터링 완료 후 스케줄러 정리
