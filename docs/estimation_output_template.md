# Estimation (CohortMethod) 연구 표준 산출물 템플릿

> 모든 CohortMethod estimation 연구에서 생성할 Tables/Figures.
> Shiny Evidence Explorer 10개 탭 + 추가 분석 포함.

---

## A. Shiny Evidence Explorer 탭 → 산출물 매핑

| Shiny 탭 | Table/Figure | 논문 위치 | 데이터 소스 |
|----------|-------------|----------|------------|
| **Power** | Power table + Time at Risk table | Supplementary | comparison_summary.csv, exposure_summary.csv |
| **Attrition** | Figure: Attrition diagram | Main Figure 1 | attrition.csv |
| **Population characteristics** | Table: Baseline (matching 전후) | Main Table 2 | covariate_balance.csv + Table1Specs.csv |
| **Propensity model** | Table: PS model top covariates | Supplementary | propensity_model.csv |
| **Propensity scores** | Figure: PS distribution (before/after) | Main Figure 2 | preference_score_dist.csv |
| **Covariate balance** | Figure: Love plot (SMD scatter) | Main Figure 3 | covariate_balance.csv |
| **Systematic error** | Figure: NC calibration plot | Main Figure 6 | negative_control_outcome.csv |
| **Forest plot** | Figure: Outcome별 IPD pooled HR | Main Figure 4 | site-stratified Cox |
| **Kaplan-Meier** | Figure: KM curves + risk table | Main Figure 5 | kaplan_meier_dist.csv |
| **Subgroups** | Table: Subgroup HR | Supplementary (해당 시) | subgroup analysis |

---

## B. 전체 산출물 목록

### Main Tables

| # | 이름 | 내용 | 소스 |
|---|------|------|------|
| **Table 1** | Study Population | 기관별: CDM 기간, 총 환자수, Target N, Comparator N, Outcome events | database.csv, comparison_summary.csv |
| **Table 2** | Baseline Characteristics | Matching 전후: 인구통계, 진단, 약물, 의료이용 (mean/%, SMD) | covariate_balance.csv, Table1Specs.csv |
| **Table 3** | Main Results (HR) | Outcome별: Events(T/C), HR, 95% CI, p-value, calibrated HR | cohort_method_result.csv + calibration |
| **Table 4** | Attrition | 단계별 N: Eligible → Covariate → Matched → Analyzed (이유별) | attrition.csv |

### Main Figures

| # | 이름 | 내용 | 소스 |
|---|------|------|------|
| **Figure 1** | Study Flow (Attrition) | 코호트 선정 흐름도 | attrition.csv |
| **Figure 2** | PS Distribution | Before/after matching, preference score | preference_score_dist.csv |
| **Figure 3** | Covariate Balance | Love plot: SMD before vs after (target line 0.1) | covariate_balance.csv |
| **Figure 4** | Forest Plot | Outcome별 IPD pooled HR 요약 | site-stratified Cox |
| **Figure 5** | Kaplan-Meier | 주요 outcome cumulative hazard + N at risk | kaplan_meier_dist.csv |
| **Figure 6** | NC Calibration | NC HR scatter + calibration curve, 유의 비율 | negative_control_outcome.csv |

### Supplementary Tables

| # | 이름 | 내용 |
|---|------|------|
| **Table S1** | Cohort Definitions | 코호트 정의 상세 (concept ID, inclusion rules, concept set) |
| **Table S2** | NC Outcome List | 전체 NC 목록 + 개별 HR |
| **Table S3** | PS Model Covariates | PS model non-zero coefficients (top 50) |
| **Table S4** | Power + Time at Risk | 통계 검정력, 추적 기간 분포 (min, Q1, median, Q3, max) |
| **Table S5** | ~~Site-specific Results~~ | 기관별 outcome N이 대부분 불충분하여 기관별 HR 미산출. outcome N 충분 시에만 고려 |
| **Table S6** | Sensitivity Analysis | 기관 제외/추가, matching ratio 변동 결과 |
| **Table S7** | Time-window HR (해당 시) | 시간 구간별 HR 변화 |

### Supplementary Figures

| # | 이름 | 내용 |
|---|------|------|
| **Figure S1** | ~~Site-specific Forest Plot~~ | 기관별 outcome N 불충분 시 제외. N 충분 시에만 생성 |
| **Figure S2** | Calibrated vs Uncalibrated | Calibration 전후 HR 비교 scatter |
| **Figure S3** | Time-window HR Plot (해당 시) | 시간 구간별 HR trajectory |
| **Figure S4** | Subgroup Forest Plot (해당 시) | 성별, 연령 등 하위군 HR |

---

## C. CohortMethod result.zip → 산출물 매핑

```
result.zip/export/
├── database.csv                  → Table 1 (기관 정보)
├── comparison_summary.csv        → Table 1 (코호트 N, events)
├── exposure_summary.csv          → Table 1, Table S4 (TAR 분포)
├── cohort_method_result.csv      → Table 3 (HR), Figure 4 (forest)
├── covariate_balance.csv         → Table 2 (baseline), Figure 3 (love plot)
├── covariate.csv                 → Table 2 상세 covariate 이름
├── preference_score_dist.csv     → Figure 2 (PS distribution)
├── kaplan_meier_dist.csv         → Figure 5 (KM curves)
├── attrition.csv                 → Table 4, Figure 1 (attrition)
├── negative_control_outcome.csv  → Table S2, Figure 6 (NC calibration)
├── propensity_model.csv          → Table S3 (PS model coefficients)
├── cm_follow_up_dist.csv         → Table S4 (follow-up 분포)
├── cohort_method_analysis.csv    → analysis settings 참조
├── exposure_of_interest.csv      → exposure 정의 참조
├── outcome_of_interest.csv       → outcome 정의 참조
└── likelihood_profile.csv        → CI 계산용
```

## D. R 스크립트 → 산출물 매핑

| 스크립트 | 입력 | 산출물 |
|---------|------|--------|
| `ipd_pooled_*.R` | CmData (SQLite) | Table 3 (HR), Figure 4 (forest) |
| `make_baseline_*.R` | CmData | Table 2 (baseline), Figure 3 (balance) |
| `make_km_curves_*.R` | CmData + matched cohort | Figure 5 (KM) |
| `run_calibration*.R` | NC HR + primary HR | Figure 6 (calibration), calibrated Table 3 |
| `ipd_cyclops_timewindow*.R` | CmData | Table S7, Figure S3 (time-window) |
| `make_table1_*.R` | attrition.csv from zip | Table 1, Table 4 |

## E. 논문 풍부화를 위한 추가 분석

| 분석 | 내용 | 추가 산출물 |
|------|------|-----------|
| **Subgroup** | 성별, 연령군(4-8, 9-12, 13-17)별 HR | Figure S4 |
| **Sensitivity: matching ratio** | 1:1 vs 1:4 비교 | Table S6 |
| **Sensitivity: 기관 제외** | leave-one-out (1기관씩 제외하며 반복) | Table S6 |
| **Heterogeneity** | I² statistic, Cochran Q test | Table S5에 포함 |
| **E-value** | Unmeasured confounding 영향 평가 | Table 3에 추가 컬럼 |
| **Number Needed to Harm** | HR → NNH 변환 (유의한 outcome) | Table 3에 추가 컬럼 |
| **Time-window** | Lag period 변동 (30d, 60d, 90d, 180d) | Table S7 |
| **Dose-response** (해당 시) | 알레르기 질환 개수별 HR | 별도 Table/Figure |

## F. 체크리스트 (논문 투고 전)

- [ ] Table 1: 기관별 CDM 기간 + 총 환자수 확인
- [ ] Table 2: 모든 주요 공변량 SMD < 0.1 (balance 충족)
- [ ] Table 3: calibrated HR 사용 여부 결정 (NC 결과에 따라)
- [ ] Figure 2: PS overlap 확인 (equipoise — 양쪽 분포 겹침 충분?)
- [ ] Figure 3: 빨간 점(SMD > 0.1) 없는지 확인
- [ ] Figure 6: NC HR median ≈ 1.0, 유의 비율 ≈ 5%
- [ ] Sensitivity: 기관 제외해도 결과 robust?
- [ ] E-value: unmeasured confounding 가능성 논의
- [ ] STROBE/RECORD checklist 확인 (관찰 연구 보고 가이드라인)
