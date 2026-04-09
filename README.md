# atlas-auto

OHDSI ATLAS / feedernet 다기관 연구 자동화 툴킷 (v0.2.0)

**연구설계 YAML 하나로 전체 파이프라인을 자동 실행합니다:**

```
┌─────────────────── Python (atlas-auto) ───────────────────┐  ┌──── R ────┐
│                                                           │  │           │
│  연구설계    코호트 JSON    ATLAS     Estimation   결과    │  │  Pooled   │
│  YAML    →  자동생성    →  업로드  →  실행     →  다운로드 │→ │  Analysis │
│                                                           │  │  + Shiny  │
└───────────────────────────────────────────────────────────┘  └───────────┘
```

```
본원 (DB 직접 접속)     →  R 패키지 직접 실행 (CohortMethod)
타기관 (웹만 접근 가능)  →  feedernet WebAPI REST 호출 (Python)
결과 통합 분석          →  R meta-analysis (EvidenceSynthesis / DerSimonian-Laird)
```

---

## 설치

```bash
# GitHub에서 설치
pip install git+https://github.com/ZellKim/atlas_auto_ms.git

# 또는 로컬 개발 모드
git clone https://github.com/ZellKim/atlas_auto_ms.git
cd atlas_auto_ms
pip install -e .
```

### 다른 프로젝트에서 플러그인처럼 사용

```txt
# requirements.txt에 추가
atlas-auto @ git+https://github.com/ZellKim/atlas_auto_ms.git
```

```python
# 어느 프로젝트에서든 import
from atlas_auto import FedernetClient, EstimationBuilder, StudyProtocol
```

---

## 프로젝트 구조

```
atlas_auto_ms/
├── pyproject.toml                      # pip install 지원
├── README.md
├── .gitignore
├── src/atlas_auto/                     # Python 패키지
│   ├── __init__.py                     #   export: FedernetClient, EstimationBuilder,
│   │                                   #           CohortDesigner, StudyProtocol
│   ├── client.py                       #   feedernet 포탈 + WebAPI 클라이언트
│   ├── builder.py                      #   Estimation JSON 스펙 빌더
│   ├── cohort_designer.py              #   YAML 코호트 정의 → CIRCE JSON 변환기
│   ├── protocol.py                     #   StudyProtocol: YAML → 전체 파이프라인
│   ├── runner.py                       #   본원(R) + 타기관(API) 통합 실행
│   ├── cli.py                          #   CLI: atlas-auto 명령
│   └── data/
│       └── concepts.py                 #   OMOP Concept ID 레퍼런스 (300+)
├── R/                                  # R 분석 코드
│   ├── pooled_analysis.R               #   메타분석 + Evidence Explorer
│   ├── run_pooled.R                    #   실행 스크립트
│   └── install_dependencies.R          #   R 패키지 설치
└── examples/
    ├── study_protocol_example.yaml     #   연구설계 프로토콜 템플릿 (핵심)
    ├── config_example.yaml             #   인증/DB 설정 템플릿
    ├── quick_start.py                  #   단계별 예제
    ├── new_study_from_scratch.py       #   새 연구 설계 예제
    └── download_results.py             #   결과 다운로드 예제
```

### 모듈별 역할

| 모듈 | 클래스/함수 | 역할 |
|------|-----------|------|
| `client.py` | `FedernetClient` | feedernet 포탈 로그인, 기관 연결, 코호트/Estimation CRUD, 결과 다운로드 |
| `builder.py` | `EstimationBuilder` | Estimation JSON 스펙을 프로그래밍 방식으로 구성 (TCO, PS, Cox 등) |
| `cohort_designer.py` | `CohortDesigner` | YAML 코호트 정의 → ATLAS CIRCE JSON 변환 |
| `protocol.py` | `StudyProtocol` | YAML 하나로 전체 파이프라인 오케스트레이션 |
| `runner.py` | `run_study()` | config.yaml 기반 본원+타기관 통합 실행 |
| `data/concepts.py` | `CONDITIONS`, `DRUGS`, ... | OMOP Standard Concept ID 레퍼런스 |

---

## 원클릭 실행: Study Protocol

### 1. 연구설계 YAML 작성

```yaml
# my_study.yaml
study:
  name: "Appendectomy vs Cholecystectomy CES"
  description: "충수절제술 vs 담낭절제술 임상결과 비교"

cohorts:
  target:
    name: "Appendectomy"
    domain: procedure
    concepts:
      - concept_id: 4198190
        include_descendants: true
    observation_window: {prior_days: 365}
    inclusion_rules:
      - {name: "age>=18", type: demographic, age: {op: gte, value: 18}}

  comparator:
    name: "Cholecystectomy"
    domain: procedure
    concepts:
      - concept_id: 4239323
        include_descendants: true
    observation_window: {prior_days: 365}

  outcomes:
    - name: "Ulcerative colitis"
      domain: condition
      concepts: [{concept_id: 81893, include_descendants: true}]
    - name: "Crohn's disease"
      domain: condition
      concepts: [{concept_id: 201606, include_descendants: true}]
    - name: "AMI"
      domain: condition
      concepts: [{concept_id: 4329847, include_descendants: true}]
      visit_type: inpatient

analysis:
  methods:
    - id: 1
      description: "PS stratification, Cox"
      ps_method: stratify
      ps_strata: 5
      model: cox
      risk_window: {start: 1, end: 0, add_exposure_days: true}
    - id: 2
      description: "PS 1:1 matching, Cox"
      ps_method: match
      match_ratio: 1
      match_caliper: 0.2
      model: cox

execution:
  config: "config.yaml"
  auto_download: true
```

> 전체 템플릿: [examples/study_protocol_example.yaml](examples/study_protocol_example.yaml)

### 2. 실행

```bash
# dry run (ATLAS 실행 없이 코호트 JSON + Estimation 스펙만 생성)
atlas-auto protocol --study my_study.yaml --dry-run

# 전체 실행 (코호트 생성 → Generate → Estimation → 결과 다운로드)
atlas-auto protocol --study my_study.yaml --config config.yaml
```

```python
# Python에서:
from atlas_auto import StudyProtocol

protocol = StudyProtocol.from_yaml("my_study.yaml")
print(protocol.summary())

# dry run
result = protocol.run(output_dir="./output", dry_run=True)
# → ./output/cohorts/target.json, comparator.json, outcome_*.json
# → ./output/estimation_spec.json

# 실제 실행
result = protocol.run(config_path="config.yaml")
# → ATLAS 업로드 → Generate → Estimation → 결과 다운로드
```

### 3. Claude와 함께 사용

Claude에게 연구 아이디어를 설명하면 `study_protocol.yaml`을 자동 생성할 수 있습니다:

> "충수절제술과 담낭절제술을 받은 환자에서 염증성 장질환 발생 위험을 비교하는 CES 연구를 설계해줘. PS stratification과 matching 두 가지 분석."

Claude는 `atlas_auto.data.concepts`의 concept ID를 참조하여 정확한 YAML을 생성합니다.

---

## Concept ID 검색

```bash
atlas-auto concepts diabetes
atlas-auto concepts appendectomy
atlas-auto concepts metformin
```

```python
from atlas_auto.data.concepts import search_concept, CONDITIONS, DRUGS, PROCEDURES, MEASUREMENTS

search_concept("diabetes")        # [("type_2_diabetes", 201826, "condition"), ...]
CONDITIONS["type_2_diabetes"]     # 201826
DRUGS["metformin"]                # 1503297
PROCEDURES["appendectomy"]        # 4198190
MEASUREMENTS["hba1c"]             # 3004410
```

수록된 카테고리: Conditions (50+), Procedures (10+), Drugs (50+), Measurements (25+)

---

## 코호트 설계 YAML 문법

### domain

| domain | ATLAS 기준 | 예시 |
|--------|-----------|------|
| `condition` | ConditionOccurrence | 진단 (당뇨, 심근경색, 크론병) |
| `procedure` | ProcedureOccurrence | 시술/수술 (충수절제, 담낭절제) |
| `drug` | DrugExposure | 약물 (메트포민, 아스피린) |
| `visit` | VisitOccurrence | 방문 (입원, 외래) |
| `measurement` | Measurement | 검사 (혈당, HbA1c) |

### inclusion_rules

```yaml
# 1. 연령/성별 필터
- name: "age >= 18"
  type: demographic
  age: {op: gte, value: 18}        # op: gt, gte, lt, lte, eq, bt

# 2. 배제 기준 (해당 이벤트가 없어야 함)
- name: "동시 대수술 제외"
  type: exclusion
  domain: procedure
  concepts: [{concept_id: 4301351}]
  window: {start: 0, end: 0}       # 인덱스 당일
  restrict_visit: true

# 3. 검사 값 기반
- name: "혈당 >= 126"
  type: measurement
  concepts: [{concept_id: 3004410}]
  value: {op: gte, value: 126}
  window: {start: -30, end: 30}

# 4. 특정 이벤트 존재 필수
- name: "이전 고혈압 진단"
  type: occurrence
  domain: condition
  concepts: [{concept_id: 316866}]
  window: {start: -365, end: -1}
  min_count: 1
```

### visit_type

```yaml
- name: "AMI (입원만)"
  domain: condition
  concepts: [{concept_id: 4329847}]
  visit_type: inpatient    # inpatient | outpatient | er
```

### end_strategy (약물 코호트용)

```yaml
target:
  name: "Metformin users"
  domain: drug
  concepts: [{concept_id: 1503297}]
  end_strategy:
    type: drug_era           # drug_era | fixed_offset
    concepts: [{concept_id: 1503297}]
    gap_days: 30
```

---

## 단계별 Python API

### 1. 로그인 & 기관 연결

```python
from atlas_auto import FedernetClient

client = FedernetClient()
client.login_portal("your@email.com", "YOUR_PW")

# 또는: client.login_with_cookie_string("JSESSIONID=abc; USER=xyz")
# 또는: client.login_with_bearer_token("eyJhbGciOiJIUzUxMiJ9...")

# 기관 연결 (ATLAS URL에서 group_id, site_id 확인)
client.connect_site(7, 203)
```

### 2. 탐색

```python
sources = client.get_sources()
cohorts = client.list_cohort_definitions()
estimations = client.list_estimations()
cdms = client.get_available_cdms()
```

### 3. 코호트 업로드 & Generate

```python
result = client.create_cohort_from_json_file("My Cohort", "target.json")
source_key = client.get_source_key()
client.generate_cohort(result["id"], source_key)
client.wait_for_cohort_generation(result["id"], source_key, timeout=600)
```

### 4. Estimation 설계 & 실행

```python
from atlas_auto import EstimationBuilder

builder = EstimationBuilder("My Study", "Drug A vs B")
builder.add_cohort_from_json(1, "Target", "target.json")
builder.add_cohort_from_json(2, "Comparator", "comparator.json")
builder.add_cohort_from_json(3, "Outcome", "outcome.json")
builder.add_target_comparator_outcomes(1, 2, [3])
builder.add_cm_analysis(analysis_id=1, ps_method="stratify", model_type="cox")

est = client.import_estimation(builder.build())
client.run_estimation(est["id"], source_key)
info = client.wait_for_estimation(est["id"])
client.download_estimation_results(info["id"], "results.zip")
```

### 5. feedernet 포탈 실행 & 다운로드

```python
# 실행 트리거
client.run_analysis_execution(project_id=2908, analysis_id=10858,
    research_name="E01_E04_clinical_ms_v6_nomatch", cdm_ids=[588, 273])

# 상태 확인
summary = client.get_analysis_execution_summary(2908, 10858)

# 결과 다운로드
client.download_execution_result(2908, 10858, execution_id=241515,
    output_path="result.zip")
```

---

## CLI 명령어

```bash
# 프로토콜 기반 전체 실행 (권장)
atlas-auto protocol --study my_study.yaml --config config.yaml
atlas-auto protocol --study my_study.yaml --dry-run

# Concept ID 검색
atlas-auto concepts diabetes

# config.yaml 기반 실행
atlas-auto run --config config.yaml --sites remote_only

# 실행 상태 확인
atlas-auto status --config config.yaml --project 2908 --analysis 10858

# 결과 일괄 다운로드
atlas-auto download --config config.yaml --project 2908 --analysis 10858 \
    --research "E01_E04_clinical_ms_v6_nomatch"
```

---

## config.yaml 설정

```bash
cp examples/config_example.yaml config.yaml
```

```yaml
portal:
  url: "https://www.feedernet.com"
  email: "your@email.com"
  password: "YOUR_PW"
  # 또는: cookie_string: "..."
  # 또는: bearer_token: "eyJ..."

remote_sites:
  - name: "SiteA"
    group_id: 7
    site_id: 203
    output_dir: "./output/SiteA"
```

> config.yaml에 비밀번호 포함 → `.gitignore`에 포함됨. 절대 커밋하지 마세요.

---

## feedernet API 구조

```
포탈 로그인:  POST /api/v1/auth/login
기관 목록:    GET  /api/v1/dashboard/organizations
기관 WebAPI:  GET  /api/v1/atlas/{group_id}/{site_id}/{endpoint}

ATLAS URL:  /atlas-resolve/v2.12.0/7/203/main
  → WebAPI: /api/v1/atlas/7/203
```

### 주요 엔드포인트

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /source/sources` | CDM 데이터 소스 목록 |
| `POST /cohortdefinition` | 코호트 생성 |
| `GET /cohortdefinition/{id}/generate/{sourceKey}` | 코호트 Generate |
| `POST /estimation/import` | Estimation Import |
| `POST /estimation/{id}/generation/{sourceKey}` | Estimation 실행 |
| `GET /estimation/generation/{genId}/result` | 결과 다운로드 |
| `POST /api/v1/project/{pid}/analysis/{aid}/execution` | 포탈 실행 트리거 |
| `GET .../execution/{eid}/files/{fid}/download` | 포탈 파일 다운로드 |

> 주의: 포탈 API에서 `project`(단수)와 `projects`(복수) 혼용

---

## 인증 방식

| 방법 | 코드 | 용도 |
|------|------|------|
| 이메일/PW | `login_portal(email, pw)` | 기본 |
| 쿠키 문자열 | `login_with_cookie_string("...")` | 자동 로그인 실패 시 |
| Bearer 토큰 | `login_with_bearer_token("eyJ...")` | API 토큰 |

쿠키/토큰 얻기: 브라우저 F12 → Network → XHR 요청 → Headers → Cookie 또는 Authorization 복사

---

## Pooled Analysis (R 메타분석)

다기관 result.zip 다운로드 후 R로 통합 분석합니다.

### 전체 워크플로우

```bash
# Step 1: Python - 다기관 estimation 실행 & 결과 다운로드
atlas-auto protocol --study my_study.yaml --config config.yaml
atlas-auto download --config config.yaml --project 2908 --analysis 10858

# Step 2: R - 메타분석 & Shiny 뷰어
Rscript R/run_pooled.R ./results
```

### R 환경 셋업 (최초 1회)

```r
source("R/install_dependencies.R")
```

필요 패키지: `meta`, `EvidenceSynthesis`, `EmpiricalCalibration`, `ParallelLogger`, `readr`, `SqlRender`

### R에서 직접 실행

```r
source("R/pooled_analysis.R")

run_pooled_analysis(
  results_folder = "./results",       # result.zip들이 있는 폴더
  method = "DL",                      # "DL" 또는 "BayesianNonNormal"
  max_cores = 4,
  launch_shiny = TRUE,                # Evidence Explorer 자동 실행
  blind = FALSE
)
```

### 메타분석 방법

| 방법 | 설명 | 장점 |
|------|------|------|
| `DL` | DerSimonian-Laird random effects | 빠름, 간단, 대부분 상황에 적합 |
| `BayesianNonNormal` | Bayesian non-normal likelihood (Schuemie 2021) | 소수/영 이벤트에 강건, 권장 |

### 출력 구조

```
results/
├── CAUHS_5.3.1_03_241515_result.zip      # 기관별 원본 결과
├── CHNUH_5.3.1_01_241528_result.zip
├── ...
├── staging/                               # 표준화된 이름 (자동 생성)
│   ├── Results_CAUHS_5.3.1_03.zip
│   └── Results_CHNUH_5.3.1_01.zip
├── meta_analysis/                         # 메타분석 결과
│   └── Results_MetaAnalysis.zip
└── shiny_data/                            # Evidence Explorer 데이터
    ├── CAUHS_5.3.1_03.rds
    ├── CHNUH_5.3.1_01.rds
    └── MetaAnalysis.rds
```

### Evidence Explorer

메타분석 완료 후 자동으로 Shiny 앱이 실행됩니다:
- 기관별 결과 비교
- Forest plot
- PS distribution
- Calibrated/uncalibrated 결과
- Negative control diagnostics

---

## 주의사항

1. **feedernet URL 비표준**: `/atlas-resolve/v2.12.0/7/203/` 구조 → `connect_site(group_id, site_id)` 사용
2. **토큰 만료**: 장시간 실행 시 `client.refresh_token()` 호출
3. **코호트 ID 매핑**: 타기관 코호트 생성 시 새 ID 부여 → `StudyProtocol`과 `run_remote_site()`가 자동 매핑
4. **보안**: config.yaml, 쿠키, 토큰은 `.gitignore`에 포함. 절대 커밋 금지
