# Estimation (CohortMethod) 연구 표준 산출물

> IPD pooled analysis 기반. 기관별 outcome N이 대부분 불충분하므로 기관별 HR은 미산출.

---

## Main Tables

| # | 이름 | 내용 |
|---|------|------|
| **Table 1** | Study Population | 기관별: CDM 기간, 총 환자수, Target N, Comparator N |
| **Table 2** | Baseline Characteristics | PS matching 전후: 주요 공변량 mean/%, SMD |
| **Table 3** | Main Results | Outcome별: Events(T/C), IPD pooled HR, 95% CI, calibrated HR |
| **Table 4** | Attrition | 단계별 N: Eligible → Covariate → Matched → Analyzed |

## Main Figures

| # | 이름 | 내용 |
|---|------|------|
| **Figure 1** | Study Flow | Attrition diagram (코호트 선정 흐름) |
| **Figure 2** | PS Distribution | Before/after matching PS overlap |
| **Figure 3** | Covariate Balance | Love plot (SMD scatter, target line 0.1) |
| **Figure 4** | Forest Plot | Outcome별 IPD pooled HR 요약 |
| **Figure 5** | KM Curves | 주요 outcome cumulative hazard + N at risk |
| **Figure 6** | NC Calibration | NC HR scatter + calibration curve |

## Supplementary

| # | 이름 | 내용 |
|---|------|------|
| **Table S1** | Cohort Definitions | concept ID, inclusion rules 상세 |
| **Table S2** | NC Outcome List | 전체 NC HR 목록 |
| **Table S3** | PS Model Covariates | Non-zero coefficients (top 50) |
| **Table S4** | Power + Time at Risk | 검정력, 추적 기간 분포 |
| **Table S5** | Sensitivity Analysis | matching ratio 변동, 기관 제외 leave-one-out |
| **Figure S1** | Calibrated vs Uncalibrated | Calibration 전후 HR 비교 |
| **Figure S2** | Time-window HR (해당 시) | 시간 구간별 HR trajectory |

---

## 데이터 소스 매핑

```
result.zip/export/
├── database.csv                  → Table 1
├── comparison_summary.csv        → Table 1
├── exposure_summary.csv          → Table S4
├── cohort_method_result.csv      → Table 3, Figure 4
├── covariate_balance.csv         → Table 2, Figure 3
├── covariate.csv                 → Table 2 covariate 이름
├── preference_score_dist.csv     → Figure 2
├── kaplan_meier_dist.csv         → Figure 5
├── attrition.csv                 → Table 4, Figure 1
├── negative_control_outcome.csv  → Table S2, Figure 6
├── propensity_model.csv          → Table S3
├── cm_follow_up_dist.csv         → Table S4
└── likelihood_profile.csv        → CI 계산
```

## R 스크립트 매핑

| 스크립트 | 산출물 |
|---------|--------|
| `ipd_pooled_*.R` | Table 3, Figure 4 |
| `make_baseline_*.R` | Table 2, Figure 3 |
| `make_km_curves_*.R` | Figure 5 |
| `run_calibration*.R` | Figure 6, calibrated Table 3 |
| `make_table1_*.R` | Table 1, Table 4, Figure 1 |
| `ipd_cyclops_timewindow*.R` | Figure S2 |

## 논문 풍부화 추가 분석 (선택)

| 분석 | 산출물 | 조건 |
|------|--------|------|
| E-value | Table 3 추가 컬럼 | 유의한 outcome |
| NNH | Table 3 추가 컬럼 | 유의한 outcome |
| Subgroup (성별, 연령군) | 별도 Table/Figure | outcome N 충분 시 |
| Leave-one-out sensitivity | Table S5 | 기본 수행 |
| Time-window HR | Figure S2 | 연구 설계에 따라 |
| Dose-response | 별도 Table | 연구 특이적 |

## 투고 전 체크리스트

- [ ] Table 2: 주요 공변량 SMD < 0.1
- [ ] Figure 2: PS overlap 충분 (equipoise)
- [ ] Figure 6: NC HR median ≈ 1.0, 유의 비율 ≈ 5%
- [ ] Sensitivity: 기관 제외해도 robust
- [ ] E-value: unmeasured confounding 논의
- [ ] STROBE/RECORD checklist
