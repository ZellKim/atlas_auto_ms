# Prompt 00 — Normalize Input

> 호출자: `paper-orchestrator`
> 목적: 자유형식 SAP / PROGRESS.md / study_knowledge_base.md → `contracts/study_input.schema.json` 통과하는 JSON으로 정규화
> 출력 위치: `studies/{study}/docs/study_input_{version}.json`

## When to run

- 사용자 trigger 시 `studies/{study}/docs/study_input_{version}.json`이 없을 때
- 또는 사용자가 새 spec으로 v(N+1) 만들 때 명시적 호출

## Inputs

primary:
- `studies/{study}/study_knowledge_base.md`
- `studies/{study}/PROGRESS.md`
- `studies/{study}/docs/irb_protocol.md` (있으면)
- `studies/{study}/docs/paper_draft_v{N-1}_*.md` Methods 섹션 (참고)

secondary (results 정규화):
- `studies/{study}/docs/eTable*.csv` (event_rates, full_biomarker, sigma_grid 등)
- `studies/{study}/docs/followup_summary.csv`
- R/IPD 분석 결과 디렉토리 (Desktop/atlas_auto_cmdata/ 등)

## Procedure

### 1. study_input.json scaffolding

`contracts/study_input.schema.json` 읽어서 빈 instance 생성:
- `paper_meta`: study_code, version, language, irb_number 채움 (사용자 확인)
- `journal_target`: 사용자에게 AskUserQuestion (`jama_network_open` / `scientific_reports`)
- `study` / `results` / `hypotheses`: 다음 단계

### 2. study 필드 정규화

study_knowledge_base.md 읽고 mapping:
- design → `study.design` 한 문장 (예: "retrospective multicenter active-comparator cohort with site-stratified propensity score matching and empirical calibration")
- 기관 / 기간 → `study.data_source` (예: "federated OMOP CDM network of 15 Korean tertiary hospitals", n_sites, period_start, period_end, cdm_version)
- 코호트 정의 → `study.population.inclusion[]`, `study.population.exclusion[]`
- 매칭 후 N → `study.population.n_target`, `study.population.n_comparators{}`, `study.population.n_matched_pairs{}`
- exposure target/comparator → `study.exposure`
- outcome primary/secondary/NC → `study.outcome.{primary, secondary, negative_controls}`
- covariates → `study.covariates` (LASSO 같으면 단축 표현 OK: "large-scale Cyclops LASSO with site dummy + Charlson Index")
- analysis (matching/primary_model/calibration/sensitivity/subgroups) → `study.analysis`

### 3. results 필드 정규화

primary outcomes CSV 직접 읽기 (예: `event_rates_per_1000PY.csv`, `eTable8b_event_rates.csv`):
- outcome 이름 정확히 (study_input 대로)
- comparator 명시
- metric (HR), value, ci_lower, ci_upper, p_value
- events {target: N, comparator: N}
- person_years {target: PY, comparator: PY}

`results.calibration`:
- NC summary CSV에서 nc_median_hr, nc_proportion_significant, null_mean, null_sd
- calibrated_primary 각 primary outcome에 대해

`results.table1`:
- baseline_table1.csv 읽어서 자유형식 dict (paper-writer가 Table 1 본문 생성 시 사용)

### 4. hypotheses

- `hypotheses.primary`: 한 문장 (Abstract Objective + Intro 마지막 문단에 그대로 들어감)
- `hypotheses.secondary`: array

## Validation

작성 후 `contracts/study_input.schema.json` 통과 확인:
```bash
python -c "import json, jsonschema; s=json.load(open('contracts/study_input.schema.json')); d=json.load(open('study_input_v10.json')); jsonschema.validate(d, s)"
```

(jsonschema 패키지 없으면 manual key check)

## Output

`studies/{study}/docs/study_input_{version}.json` 저장 후 orchestrator에 보고:

```
Normalize 완료:
- study.design: "..."
- study.population.n_target: 13225
- study.outcome.primary: 3 items
- results.primary: 9 effect sizes
- results.calibration.null_sd: 0.18
- Schema validation: PASS
```

## 사용자 인터랙션

- journal_target 모호하면 AskUserQuestion (jama_network_open / scientific_reports)
- inclusion/exclusion 정확하지 않으면 사용자 확인
- results CSV 위치 모호하면 사용자 path 입력 요청

## 주의

- canonical_terms.md "federated OMOP CDM network of N Korean tertiary hospitals" 표현 사용 — `FeederNet` 직접 금지 (memory feedback_no_feedernet_in_papers)
- 모든 숫자는 source CSV에서 직접 read — 추측 금지 (memory feedback_no_guessing)
