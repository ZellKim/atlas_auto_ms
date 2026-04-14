# atlas-auto 프로젝트 진행 상황

**repo**: https://github.com/ZellKim/atlas_auto_ms
**최종 업데이트**: 2026-04-14

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

## 4. IPD Pooled Analysis R 코드 (로컬에서 통합, 2026-04-13)

### 현재 상태: 로컬 코드 통합 완료

기존 `R/pooled_analysis.R` (잘못된 meta-analysis)은 유지하되, 로컬 PC에서 가져온 **실제 IPD pooled analysis 파이프라인**을 `R/pooled_analysis/`에 통합.

### R/pooled_analysis/ 파이프라인 (실행 순서)

```
00_config.R           → 사이트 경로, 코호트 ID, outcome/NC 정의
    ↓
01_pool_cmdata.R      → 다기관 CmData(SQLite) 합침 + rowId 재매핑 + site 변수
    ↓
02_run_pooled_analysis.R → PS 재추정(Cyclops) → IPTW/층화/매칭 → Cox regression
    ↓
03_meta_analysis.R    → 기관별 결과로 BayesianNonNormal/DL 메타분석
    ↓
04_calibrate_and_report.R → Empirical calibration + Forest plot + 요약 테이블
```

| 파일 | 상태 | 역할 |
|------|:----:|------|
| `00_config.R` | ✅ | 설정 (사이트, 코호트, outcome, NC) |
| `01_pool_cmdata.R` | ✅ | CmData 풀링 + site covariate |
| `02_run_pooled_analysis.R` | ✅ | PS→IPTW/층화/매칭→Cox (3가지 방법) |
| `03_meta_analysis.R` | ✅ | Bayesian/DL 메타분석 |
| `04_calibrate_and_report.R` | ✅ | Calibration + Forest plot |
| `ipd_pooled_cyclops.R` | ✅ | 독립 실행 IPD pooled (1:2 매칭, Cyclops) |
| `ipd_pooled_cyclops_v7.R` | ✅ | v7 데이터용 (경로만 다름) |
| `ipd_pooled_matching.py` | ✅ | Python 버전 (scikit-learn + lifelines) |
| `update_and_rerun.py` | ✅ | 완료 감시→다운로드→분석 자동화 |

### 의존 R 패키지 (18개)

CohortMethod, Cyclops, Andromeda, survival, FeatureExtraction,
EmpiricalCalibration, EvidenceSynthesis, meta, dplyr, ggplot2,
ParallelLogger, readr, SqlRender, DBI, RSQLite

### 주의: 하드코딩 경로 수정 필요

- `00_config.R`: `resultFolders$AUMC` 등 → 실제 result 경로로 수정
- `ipd_pooled_cyclops*.R`: `BASE_DIR` → 실제 pooled_analysis 경로
- `collect_pooled_data.py`: Windows 절대 경로 → 상대 경로로 수정

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
| `estimation_model/` | R 패키지 + estimation export JSON/zip |
| `tool_package/` | 참고용 Data2Evidence 패키지 |
| `fromlocal/` | 로컬 PC에서 가져온 원본 파일 |
| `config.yaml` | feedernet 비밀번호 포함 |
| `R/pooled_analysis/cmData*/` | 대용량 CmData SQLite |
| `R/pooled_analysis/matched_results*/` | 매칭 결과 |

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

## 8. IPD Pooled Analysis 실행 결과 (Cyclops 확정, 2026-04-14)

16개 기관 pooled. **Cyclops PS + 1:2 매칭 + site-stratified Cox** (확정).
결과 CSV: `C:\Users\data1\Desktop\atlas_auto_cmdata\pooled_results_v7b\`, `pooled_results_biomarker\`

### v7b Clinical (유의한 결과)

| Comparison | Outcome | HR | p |
|------------|---------|---:|--:|
| vs Chol | Atopic dermatitis | 0.544 | 0.022 |
| vs Chol | T2DM | 0.769 | 0.046 |
| vs GenPop | Parkinson's | 0.354 | 0.039 |
| vs GenPop | T2DM | 0.355 | <0.001 |
| vs Hernia | T2DM | 1.633 | 0.005 |

**주의**: T2DM은 비교군 의존적 (vs Chol/GenPop 감소, vs Hernia 증가)

### Biomarker (3개 비교 일관)

- **WBC/Neutro/Lympho**: 3개 비교 모두 감소 (HR 0.17~0.69) — 가장 robust
- **Eosino/Mono/Baso**: vs GenPop/Hernia에서 증가 (HR 1.23~1.42)


---

## 9. Time-window Stratified Analysis (2026-04-14) - COMPLETED

PS matching 1회, 동일 matched cohort에서 6개 구간별 Cox (landmark approach).

### Biomarker vs Hernia (핵심)

| Biomarker | 1-30d | 31-90d | 91-365d | 366-1095d | 1096-3650d |
|-----------|------:|-------:|--------:|----------:|-----------:|
| WBC | 0.81* | 1.54 | 0.37* | 0.36* | 0.39* |
| Neutro | 0.61* | 1.00 | 0.31* | 0.37* | 0.35* |
| Lympho | 0.67* | 0.63 | 0.24* | 0.28* | 0.26* |
| Eosino | 2.04* | 1.92* | 0.89 | 0.81 | 1.25 |
| CRP | 1.77* | 4.24 | 0.42* | 0.29* | 0.41* |

91d+ 급성면역 지속 감소 = 충수 특이적 효과. 알레르기세포는 급성기만 일시적.

---

## 10. Characterization (기술통계) - 실행중

WindowedCriteria + DISTRIBUTION + Value as number (FA 372). copy+PUT API.
19 biomarker x 5 time windows = 95 FA. Char 120 ATLAS 실행중 (gen=3252).
다기관: weighted mean +/- pooled SD.

---

## 11. Biomarker Cohort Definition (확인 완료)

Inclusion: 수술전 1년 정상 + 과거 이상없음 -> 수술후 첫 이상만 포착.
WBC>11, Neutro>70%, Lympho<20%, Eosino>7%, Mono>12%, Baso>1%,
CRP>0.8, ESR>20, GlucDM>=126, GlucPreDM 100-125, ALT>40, Albumin<3.5.

---

## 12. Negative Control Calibration - 실행중

48 NC in CmData. Same matched cohort. 3 comparisons x 48 NC = 144 HR.
EmpiricalCalibration -> calibrated p-value/CI.

---

## Environment

- R 4.5.2 + Rtools 4.5 (C:/rtools45)
- Java JDK 21 (C:/Users/data1/java/jdk-21.0.10+7)
- CohortMethod 4.2.2, Andromeda 0.6.0, FeatureExtraction 3.2.0
- duckdb removed (RSQLite conflict)
- CmData: C:/Users/data1/Desktop/atlas_auto_cmdata/

---

## TODO

- [x] Biomarker cohort definition check
- [x] Time-window HR analysis (v7b + biomarker)
- [ ] NC calibration (running)
- [ ] Characterization 120 result (ATLAS running)
- [ ] At-risk N per time window (for Table)
- [ ] Paper Methods/Results writing
- [ ] Multi-site Characterization
- [ ] Download remaining RUNNING sites
- [ ] FAILED sites investigation
- [ ] fromlocal cleanup
- [ ] Cloud monitor scheduler cleanup
