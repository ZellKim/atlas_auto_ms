# Prompt 10 — Methods Section

> 호출자: `paper-writer` (paper-writer Step 1, 다른 섹션 의존성 기반 source)
> 목적: study_input.json `study.analysis` + `study.population` → Methods 본문 markdown
> 출력 위치: `studies/{study}/docs/draft/{version}/methods.md`
> 대상 분량: JAMA NO ~500-650 words / SR ~700-900 words

## Voice

- 건조, 짧은 문장
- 수동태 허용 ("Patients were matched...", "The analysis was performed using...")
- 수식어 최소
- AI 냄새 (delve into, leverage, underscore) 금지
- 1인칭 ("we") JAMA family 일반적으로 허용. SR도 OK.

## 구조 (sub-section, 본문 헤더 없이 문단 흐름)

### §1 Data source and study design

- federated OMOP CDM network of {n_sites} Korean tertiary hospitals (study_input.data_source 그대로)
- 기간: {period_start} – {period_end}
- OMOP CDM v{cdm_version}
- 분석 유형: retrospective active-comparator cohort with PSM (study_input.study.design)
- IRB approval: {paper_meta.irb_number} (waiver of consent, deidentified data)

### §2 Population

- Inclusion (skeleton point 그대로): study.population.inclusion[] 한 문장 합성
- Exclusion: study.population.exclusion[] 한 문장 합성
- Index date 정의 (study.exposure.operationalization 참조)
- 365d washout (또는 사용자 정의 lookback)
- Target: study.exposure.target
- Comparators: study.exposure.comparators[] 각각 rationale 한 문장

### §3 Cohort definitions

OMOP cohort definition reference:
- target / each comparator에 대해 concept_id list 또는 외부 reference (studies/{study}/docs/cohort_definitions/ link)
- post-index follow-up window

### §4 Outcomes

- Primary outcomes: study.outcome.primary[] each
  - name + definition + endpoint_type + followup_days
- Secondary outcomes: study.outcome.secondary[]
- Negative controls: study.outcome.negative_controls.length 개 (예: "54 prespecified condition NC")

### §5 Statistical analysis

- Propensity score: study.analysis.matching ("Cyclops large-scale LASSO logistic regression with site dummy covariate")
- Matching: "1:1 nearest-neighbor PSM, caliper 0.2 SD of logit propensity score"
- Balance check: standardized mean difference (SMD) threshold (예: <0.1)
- Primary model: study.analysis.primary_model ("site-stratified Cox proportional hazards")
- Calibration: study.analysis.calibration ("empirical calibration of HR estimates against 54 NC outcomes; Schuemie 2014 fitNull method-of-moments to estimate null distribution mean and SD; calibrated HR = exp(logHR − null_mean), calibrated SE = sqrt(SE² + null_sd²)")
- Sensitivity: study.analysis.sensitivity[]
- Subgroups (있으면): study.analysis.subgroups[]
- 통계 software: R 4.x with packages (Cyclops, CohortMethod, EmpiricalCalibration, survival)

### §6 Reporting / ethics

- STROBE checklist 준수 (JAMA NO 필수)
- IRB number + waiver of consent
- Data sharing statement (별도 섹션 — 본문에 짧게 언급만)

## 인용 사용

methods/precedent intended_use refpack 우선 사용:
- empirical calibration: [refpack:Schuemie2014]
- large-scale PSM: [refpack:Suchard2013] (있으면)
- federated multicenter OMOP CDM: [refpack:Hripcsak2015] (있으면)
- site-stratified Cox: [refpack:Stuart2010] (있으면)

refpack에 없으면 `[CITATION NEEDED]` 마커.

## 수치 사용

- N target / N comparators / N matched pairs — study.population에서 그대로
- caliper / SMD threshold — study.analysis에서 그대로
- followup window — study.outcome에서 그대로
- 그 외 수치 — Methods에서는 결과 수치 X (Results 섹션에 들어감)

## 주의

- canonical_terms.md: "prespecified" (not "pre-specified"), "postappendectomy" (not "post-appendectomy")
- "federated OMOP CDM network of {N} Korean tertiary hospitals" 그대로 — FeederNet 명시 금지
- HR 표기: 본문에서 first mention "hazard ratio (HR)" full + 약어 도입
- statistical software 버전 number — study_input에 없으면 `[NUMBER?]` 마커

## 출력 metadata

```
<!-- word_count: 527 / target: ~600 (Methods, JAMA NO) -->
<!-- citations_used: [Schuemie2014, Suchard2013, Hripcsak2015] -->
<!-- markers: [CITATION NEEDED]=0, [NUMBER?]=0 -->
```
