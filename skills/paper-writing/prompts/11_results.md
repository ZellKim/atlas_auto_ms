# Prompt 11 — Results Section

> 호출자: `paper-writer` (Methods 완료 후)
> 목적: results.json 수치 → Results 본문 markdown (해석 없이 수치만)
> 출력 위치: `studies/{study}/docs/draft/{version}/results.md`
> 대상 분량: JAMA NO ~500-700 words / SR ~700-900 words

## Voice

- **해석 없이 수치만** — 한 effect size = 한 문장
- 단어: "X was higher in target than comparator", "the HR was Y"
- 금지: "interestingly", "as expected", "consistent with prior reports" (이 표현은 Discussion으로)
- Table / Figure 인용은 본문 안에서 자연스럽게

## 구조

### §1 Cohort characteristics (Table 1 reference)

- Pre-match N: study.population.n_target + n_comparators[] (자유롭게 본문 합성)
- Matching outcome: results.table1 또는 study.population.n_matched_pairs 그대로
- "Of {n_pre_match} target patients, {n_matched} were 1:1 PSM-matched to comparator cohort {comparator_name} ({n_matched} pairs)..."
- Table 1 인용: "Baseline characteristics after matching showed SMD <0.1 across all covariates (Table 1)."
- Median age / sex / 핵심 covariates 1-2개 본문에 paraphrase

### §2 Primary outcomes

results.primary[] 순회. 각 outcome × comparator pair 한 문장:

format (JAMA NO):
```
For {outcome_name}, the hazard ratio comparing {target} to {comparator} was
{value} (95% CI, {ci_lower}–{ci_upper}; P{=|<}{p_value}).
```

예시:
```
For postacute neutrophil percentage elevation (91–365 days), the hazard ratio
comparing appendectomy to cholecystectomy was 1.34 (95% CI, 1.18–1.52; P<.001).
The corresponding hazard ratio against hernia repair was 1.27 (95% CI, 1.09–1.48;
P=.002).
```

또는 효율 (3 outcomes × 2 comparators = 6 HR이면 2 문단으로 분산):
- §2a Neutrophil%
- §2b Eosinophil%
- §2c Lymphocyte% (또는 한 문단)

### §3 Secondary outcomes

results.secondary[] 동일 format. 한 문단 묶음 가능:
"Secondary outcomes (CRP, ESR) showed directionally similar but smaller associations: ..."

### §4 Sensitivity / subgroup

results.sensitivity[] 요약:
- σ-grid: "At null SD σ=0.30, all three primary cellular-immune endpoints retained statistical significance (eTable {N})."
- LOSO 15-iteration: "Leave-one-site-out sensitivity showed pooled HR within ±5% of main estimate across all 15 iterations (eTable {N})."
- lookback (90d / 365d / unlimited): 영향 minor면 한 문장

### §5 Negative control calibration

results.calibration:
- "Among 54 negative control outcomes, median observed HR was {nc_median_hr} (expected 1.0), with {nc_proportion_significant}% reaching statistical significance (expected 5%)."
- Null distribution (Schuemie 2014 method-of-moments): "null mean log HR was {null_mean}, null SD was {null_sd}."
- "After empirical calibration, primary HR estimates ranged: ..." (calibrated_primary[] 요약)

### §6 Time-window analysis (있으면)

results.primary[] time bin별 (예: 1-30, 31-90, 91-365, 366-1095, 1-3650 days):
- 한 문단 / 또는 eFigure 인용
- 예: "The association was concentrated in the postacute window (91–365 days), with attenuated HRs in earlier (1–30 days) and later (>1,095 days) intervals (eFigure {N})."

## 수치 사용 규칙

- 모든 숫자는 `results.json`에서 *직접* lookup. 없으면 `[NUMBER?]` 마커.
- HR rounding: 소수점 2자리 (예: HR 1.34)
- CI: 같은 자릿수
- P-value (JAMA NO format §3.1):
  - P ≥ .01: 소수점 2자리 (`P=.02`)
  - P < .01 and ≥ .001: 3자리 (`P=.006`)
  - P < .001: `P<.001`
- Sample size: thousand separator (13,225 not 13225)
- Person-years: optional 본문 (또는 Table만)

## 인용 사용

Results는 일반적으로 인용 거의 없음 (자기 결과 보고). 단, comparison 표현 시:
- "Concordant with [refpack:Lee2024]" — 금지 (Discussion으로). Results는 사실만.

eTable / eFigure inline citation:
- "(eTable 4)"
- "(eFigure 3)"

## Table 1 본문 처리

- 본문은 "Baseline characteristics after matching are shown in Table 1." 한 줄
- 핵심 covariate 1-2개 본문 paraphrase
- SMD threshold pass 명시
- Detail은 Table 1 자체에 위임

## 출력 metadata

```
<!-- word_count: 612 / target: ~600 -->
<!-- numbers_used: 18 unique values from results.json -->
<!-- markers: [NUMBER?]=0 -->
<!-- table_refs: [Table 1, eTable 4, eTable 8b, eFigure 3] -->
```

## 주의

- canonical_terms.md: HR 표기 `HR {value} (95% CI, {l}–{u})` 형식 통일
- P-value 단독 금지 — 항상 effect + 95% CI 동반 (JAMA NO §3.1)
- Results는 해석 X — "Interestingly elevated" 같은 표현 금지. voice-rewriter가 다시 잡지만 처음부터 안 쓰는 게 best.
- 본문 길이 hard limit 신경 — primary 3 outcome × 2 comparator = 6 HR이 본문 메인. secondary / sensitivity는 짧게.
