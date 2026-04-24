# R/archive — Deprecated IPD Pooled Scripts

2026-04-24에 보관된 구형 IPD pooled analysis 스크립트. 모두 `R/lib/ipd_pooled.R`으로 대체됨.

## 이동 사유

v4 + allergic + 구형 4-step pipeline까지 4가지 평행 파이프라인이 8,000+ 라인으로 공존. 공통 로직 ~70% 중복, 버그픽스 누락 리스크. Regression test (v4 Chole 30 outcome bit-for-bit 일치) 통과한 `R/lib/ipd_pooled.R`로 통합.

## 파일 분류

| 파일 | 원 목적 |
|---|---|
| `v4_main_365d_analysis_v3_clinicalstate.R` | **v4 canonical** (421줄). lib regression 기준. |
| `v4_main_365d_analysis{,_v2_combined}.R` | v4 main analysis 이전 버전 (dual-unit 조합 전) |
| `v4_loso_sensitivity{,_v3}.R` | LOSO (leave-one-site-out) sensitivity |
| `v4_ipd_pooled_analysis.R` | v4 초기 IPD pool |
| `v4_ipd_supplemental.R` | supplementary analyses (eTable 등) |
| `v4_ipd_lookback_compare.R` | 365d vs unlimited lookback 비교 |
| `v4_ipd_inspect.R` | CmData 검사 helper |
| `v4_clinical_365d_analysis.R` | clinical state 이전 변형 |
| `v4_debug_{calibrate,null}.R` | calibration/null 디버그 |
| `allergic_ipd_pilot.R` | 3-site allergic pilot (v1, 단순화된 censoring) |
| `pooled_analysis/` | 구형 4-step pipeline (00-04 stages + cyclops 올인원) |
| `pooled_analysis.R`, `run_pooled.R` | 구형 monolithic entry |

## 신규 연구 시

`R/archive/`에서 **복사하지 말 것**. `R/lib/driver_template.R` 복사 후 config만 채워서 `run_ipd_pooled(config)` 호출.

참조: `docs/system_knowledge_base.md` §7.2
