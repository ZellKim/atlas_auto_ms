# Estimation (CohortMethod) 연구 표준 산출물 템플릿

> 모든 CohortMethod estimation 연구에서 동일하게 생성할 Tables/Figures 목록.
> 연구별 analysis_protocol.md에서 이 템플릿을 참조하여 산출물 계획.

---

## Main Tables

| # | 이름 | 내용 | 데이터 소스 |
|---|------|------|------------|
| Table 1 | Study Population | 기관별 CDM 기간, 코호트 N (T/C), 성별/연령 분포 | CohortCounts.csv, database.csv |
| Table 2 | Baseline Characteristics | PS matching 전후 공변량 비교 (mean/%, SMD) | covariate_balance.csv |
| Table 3 | Primary Outcomes | Outcome별 HR (95% CI), calibrated HR, events, TAR | cohort_method_result.csv |
| Table 4 | Attrition | 단계별 환자 수 (eligible → covariate → matched → analyzed) | attrition.csv |

## Main Figures

| # | 이름 | 유형 | 내용 | 생성 방법 |
|---|------|------|------|----------|
| Figure 1 | Study Flow | Attrition diagram | 코호트 선정 과정 | attrition.csv → R |
| Figure 2 | PS Distribution | Histogram/density | Before/after matching PS overlap | preference_score_dist.csv → R |
| Figure 3 | Covariate Balance | Love plot (scatter) | SMD before vs after matching | covariate_balance.csv → R |
| Figure 4 | Forest Plot | Forest plot | 전체 outcome HR 요약 (primary) | cohort_method_result.csv → R |
| Figure 5 | KM Curves | Kaplan-Meier | 주요 outcome의 cumulative hazard + risk table | kaplan_meier_dist.csv → R |
| Figure 6 | NC Calibration | Calibration plot | NC HR 분포 + calibration effect | negative_control_outcome.csv → R |

## Supplementary Tables

| # | 이름 | 내용 |
|---|------|------|
| Table S1 | Cohort Definitions | 코호트 정의 상세 (concept ID, inclusion rules) |
| Table S2 | NC Outcome List | 전체 negative control outcome 목록 + HR |
| Table S3 | Site-specific Results | 기관별 HR (heterogeneity 확인) |
| Table S4 | PS Model Covariates | PS model top covariates (non-zero coefficients) |
| Table S5 | Sensitivity Analyses | 기관 수 변동, matching ratio 변동 등 |

## Supplementary Figures

| # | 이름 | 내용 |
|---|------|------|
| Figure S1 | Site-specific Forest Plot | 기관별 HR forest plot |
| Figure S2 | Time-window HR | 시간 구간별 HR 변화 (해당 시) |
| Figure S3 | Calibrated vs Uncalibrated | Calibration 전후 비교 |

---

## CohortMethod 결과 파일 → 산출물 매핑

```
result.zip
└── export/
    ├── cohort_method_result.csv      → Table 3, Figure 4
    ├── covariate_balance.csv         → Table 2, Figure 3
    ├── preference_score_dist.csv     → Figure 2
    ├── kaplan_meier_dist.csv         → Figure 5
    ├── attrition.csv                 → Table 4, Figure 1
    ├── negative_control_outcome.csv  → Table S2, Figure 6
    ├── propensity_model.csv          → Table S4
    ├── comparison_summary.csv        → Table 1
    ├── exposure_summary.csv          → Table 1
    ├── database.csv                  → Table 1
    └── covariate.csv                 → Table 2 상세
```

## R 스크립트 → 산출물 매핑

| 스크립트 | 생성 산출물 |
|---------|-----------|
| `ipd_pooled_*.R` | Table 3 (HR), Figure 4 (forest) |
| `make_baseline_*.R` | Table 2 (baseline), Figure 3 (balance) |
| `make_km_curves_*.R` | Figure 5 (KM) |
| `run_calibration*.R` | Figure 6 (NC calibration), Table S2 |
| `ipd_cyclops_timewindow*.R` | Figure S2 (time-window) |

---

## 체크리스트 (논문 투고 전)

- [ ] Table 1: 기관별 N 확인 (최소 분석 기관 수 충족?)
- [ ] Table 2: SMD < 0.1 확인 (balance 충족?)
- [ ] Table 3: calibrated HR 사용 여부 결정
- [ ] Figure 2: PS overlap 충족 (equipoise?)
- [ ] Figure 6: NC median ≈ 1.0, 유의 비율 ≈ 5%
- [ ] Sensitivity: 기관 제외 시 결과 robust?
