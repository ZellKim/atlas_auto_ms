# Prompt 05 — Skeleton First (Checkpoint ★)

> 호출자: `paper-orchestrator` (Step 3, paper-writer 호출 전)
> 목적: 6 섹션 각 1-paragraph skeleton 작성 → 사용자 review checkpoint
> 출력 위치: `studies/{study}/docs/skeleton_{version}.md`

## Why skeleton-first

5 agent 통일성 보장의 핵심 장치. 사실/framing/순서를 미리 합의해두면 paper-writer는 expansion만 담당 → 섹션 간 분기 최소화.

## Inputs

- `studies/{study}/docs/study_input_{version}.json`
- `studies/{study}/docs/results_{version}.json`
- `studies/{study}/docs/refpack_{version}.json`
- `skills/paper-writing/style/{jama_no|sr}_format_rules.md`
- `skills/paper-writing/style/canonical_terms.md`

## Output 구조

`skeleton_{version}.md`:

```markdown
# Skeleton — {study_code} v{version} ({journal_target})

## Section 1: Introduction (~4 문단 in full, 여기서는 1 문단 요약)

[1 paragraph, ~80-120 words]
- §1 Burden: [refpack:Park2023, Lee2020 — 한국 appendectomy 연간 N건, 입원 dominant 등]
- §2 Prior evidence: [refpack:Lee2024 — cellular immune disturbance; Kim2023 — postacute outcomes]
- §3 Gap: cellular-immune trajectory 다기관 federated cohort 부재
- §4 Objective: study_input.hypotheses.primary 한 문장 그대로

## Section 2: Methods (~600 words in full, 여기서는 1 문단)

- Design: study_input.design 한 문장
- Data source: federated OMOP CDM network of {n_sites} Korean tertiary hospitals, 기간 {period_start}–{period_end}, OMOP CDM v5.3.1
- Population: target = appendectomy patients (criteria from study_input.population.inclusion), comparators = chole (rationale), hernia (rationale). 365d washout. matching: 1:1 PSM (Cyclops LASSO + site dummy), caliper 0.2 SD logit PS.
- Outcomes: primary = 3 cellular-immune (Neutro%/Eos%/Lymph%) over 1-30 / 31-90 / 91-365 / 366-1095 / 1-3650 days. secondary = supportive CRP. NC = 54 conditions.
- Analysis: site-stratified Cox + empirical calibration (Schuemie 2014, fitNull method-of-moments).
- Sensitivity: σ-grid (0.10/0.20/0.30), LOSO 15 iterations.

## Section 3: Results (~700 words in full, 여기서는 1 문단)

- N matched: target 13,225 vs chole 13,225 + hernia 7,151 (Table 1 reference)
- Table 1 highlight: SMD < 0.1 across major covariates after matching
- Primary 3 cellular-immune (HRs with 95% CI from results.primary):
  - Neutro% elevated postacute: HR ... (... – ...)
  - Eos% reduced: HR ...
  - Lymph%: HR ...
- Secondary CRP: HR ...
- Calibration: NC median HR ≈ 1.0, σ=0.18; calibrated primary all retained sig at σ=0.30.
- Subgroup / sensitivity: 본문에서 detail.

## Section 4: Discussion (~900 words in full, 여기서는 1 문단)

- §1 Principal: 3 cellular-immune endpoints consistent direction across two comparators
- §2 Comparison:
  - Concordance: Lee2024 (cellular immune disturbance after appendectomy)
  - Discordance ★: Chen2022 (no T2D association in Korean cohort, 본 결과 elevated와 반대) — explain via different lookback / outcome 정의 차이
- §3 Mechanisms: appendix as secondary lymphoid organ; gut microbiota immune programming (1-2 mechanistic speculation 허용)
- §4 Strengths and limitations (본문 흐름에 녹임 — list 금지):
  - Strengths: multicenter, active-comparator design, NC calibration, σ-grid
  - Limitations: observational, federated raw-data 비공개, severity 미분류, coding ascertainment
- §5 Implications: postacute monitoring 필요, larger prospective immune cohort

## Section 5: Abstract (JAMA NO structured, ~300 words)

- Importance: appendix immune function 가설 → postappendectomy biomarker trajectory 연구 부재
- Objective: hypotheses.primary 한 문장
- Design/Setting/Participants: federated OMOP CDM network of 15 Korean tertiary hospitals, retrospective cohort 1993–2026
- Exposures: appendectomy vs cholecystectomy + hernia repair
- Main Outcomes: 3 cellular-immune (Neutro%/Eos%/Lymph%) + supportive CRP, time-to-event 1-30/31-90/91-365/366-1095 days
- Results: N + 3 HRs + calibration σ
- Conclusions: postacute cellular-immune signal; clinical implication

(SR target이면 unstructured 200w로 변환 — Importance/Objective 헤더 X)

## Section 6: Title

- JAMA NO ≤100 chars: "Appendectomy and Postacute Laboratory Abnormality Events in 15 Korean Hospitals"
- SR ≤200 chars: 동일 + 부제 가능
```

## 작성 룰

1. **수치 사용 금지** (skeleton 단계) — 정확한 effect size는 paper-writer expansion 시 results.json에서 추출. skeleton에는 `[refpack:...]` placeholder + 개념만.
2. **canonical_terms.md 준수** — `prespecified`, `postappendectomy`, `federated OMOP CDM network`
3. **refpack 인용 자리**는 모두 `[refpack:citation_key]` 마커
4. **저널별 분기** — JAMA NO이면 Abstract structured + Key Points, SR이면 unstructured

## 사용자 review checkpoint

skeleton 작성 후 paper-orchestrator가 AskUserQuestion:
```
"Skeleton OK? 어느 섹션 수정 필요?"
options:
  - "OK — paper-writer 호출"
  - "Intro 수정"
  - "Methods 수정"
  - "Results 수정"
  - "Discussion 수정"
  - "Abstract 수정"
  - "Title 수정"
  - "전체 재작성"
```

수정 요청 시 해당 섹션만 다시 작성 후 다시 review.

## 통일성 보장

- 모든 6 섹션에 같은 N, 같은 comparator, 같은 outcome 정의 사용
- Intro gap ↔ Methods novelty contribution ↔ Discussion implications 논리 연결
- Abstract = 본문 6 섹션 1-line summary 합집합 (별도 정보 추가 금지)
