# data/measurement/ — Measurement 연구 시작 키트

측정치(biomarker/lab/vital) 기반 다기관 연구를 위한 **기관별 concept/unit/value 정보**의 단일 진입점.

## 빠른 찾기

| 필요한 것 | 파일 |
|---|---|
| 이 biomarker를 **어느 기관·어느 concept으로 써야 하나** | `site_concept_matrix.csv` |
| 이 biomarker를 몇 기관이 안정적으로 갖고 있나 (INCLUDE 판정) | `stability_summary.csv` |
| 같은 biomarker의 대체 concept ID (alt IDs) | `concept_mapping.csv` |
| 기관별 lab 값 분포 (p10/p25/median/p75/p90) | `unit_survey_full.csv` |
| 특정 concept을 **어느 기관이 어느 unit으로** 리포트하나 | `by_site/units_by_site.csv` |
| 기관별 value 분포 (v4 appendectomy provenance) | `v4_surveys/all_outcomes_value_survey.csv` |
| FA preset characterization (cohort × concept × stats) | `characterization/char_preset_all.csv` |
| Achilles drilldown **원본 응답** | `raw_drilldown/*.json` (gitignored, 재수집 가능) |

## 파일 상세

### 최종 결정 (paper·분석 직접 사용)

- **`site_concept_matrix.csv`** (705 rows)
  columns: `biomarker, site, used_concept_id, count, median, unit, status`
  `status = USABLE / EXCLUDED` — 기관별 biomarker 사용 여부·선택된 concept ID.

- **`stability_summary.csv`** (33 rows)
  columns: biomarker 단위로 n_usable_sites, include_decision 등.
  22-site 연구에서 **몇 기관에서 돌릴 수 있는지 빠르게 확인**.

- **`concept_mapping.csv`** (17 rows)
  canonical concept ID ↔ alt IDs. 같은 측정치를 여러 concept ID로 보고하는 기관 대응.

### 기관별 drilldown 파생

- **`by_site/concept_by_site.csv`** — wide: biomarker × site 사용 count 매트릭스
- **`by_site/units_by_site.csv`** — long: `site, concept_id, unit_concept_id, unit_name, count`
- **`by_site/unit_summary_by_site.csv`** — 기관별 unit 요약

### Value 분포

- **`unit_survey_full.csv`** — 통합 p10/p25/median/p75/p90 (모든 measurement)
- **`v4_surveys/`** — appendectomy v4 provenance 유지된 분포 데이터
  - `all_outcomes_value_survey.csv` — 35 primary outcome
  - `biomarker_unit_survey.csv` — 32 biomarker unit
  - `extension11_value_survey.csv` — extension 11 outcome
  - `tsh_vitd_survey.csv` — TSH/VitD 별도

### Characterization (FA preset)

- **`characterization/char_preset_all.csv`** (47,141 rows)
  columns: `site, window, cohort_id, concept_id, concept_name, count, mean, sd, median, p25, p75, min, max`
  FA preset 기반 cohort characterization 전체.

### Raw drilldown (gitignored)

- `raw_drilldown/v4_biomarker.json` — Achilles API 원본 응답
- `raw_drilldown/v4_all_outcomes.json`
- `raw_drilldown/v4_extension11.json`
- `raw_drilldown/v4_tsh_vitd.json`

필요 시 `data/scripts/collect_v4_*.py` 스크립트로 재수집 가능.

## 수집·가공 스크립트 (data/scripts/)

| 스크립트 | 산출 |
|---|---|
| `collect_v4_biomarker_units.py` | `v4_surveys/biomarker_unit_survey.csv` + `raw_drilldown/v4_biomarker.json` |
| `collect_v4_value_survey.py` | `v4_surveys/all_outcomes_value_survey.csv` + `raw_drilldown/v4_all_outcomes.json` |
| `collect_v4_extension_11.py` | `v4_surveys/extension11_value_survey.csv` + `raw_drilldown/v4_extension11.json` |
| `collect_v4_tsh_vitd_correct.py` | `v4_surveys/tsh_vitd_survey.csv` + `raw_drilldown/v4_tsh_vitd.json` |
| `collect_measurement_units.py` | `unit_survey_full.csv` |
| `biomarker_stability_summary.py` | `site_concept_matrix.csv` + `stability_summary.csv` |

## 신규 연구 시

1. `site_concept_matrix.csv` + `stability_summary.csv` 먼저 확인 — 이미 수집된 biomarker면 바로 사용 가능
2. 신규 biomarker면 `collect_v4_biomarker_units.py`를 복제해서 TARGET_CONCEPTS 수정 후 재수집
3. Value 기반 threshold cohort 빌드 시 `v4_surveys/*_value_survey.csv` 또는 `unit_survey_full.csv`의 p25/p75 사용

## 관련 데이터

- `data/concept_frequency/` — 23 site × 5 domain Achilles frequency (cross-domain, 측정 전용 아님)
- `data/biomarker/` → **deprecated 2026-04-24**, 모두 이곳으로 이동
