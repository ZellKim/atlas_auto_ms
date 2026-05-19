# Prompt 13 — Discussion Section

> 호출자: `paper-writer` (Results 완료 후, voice-rich agent)
> 목적: 자기 결과 요약 + 문헌 비교 + 메커니즘 + 강점/한계 + implications
> 출력 위치: `studies/{study}/docs/draft/{version}/discussion.md`
> 대상 분량: JAMA NO ~700-900 words / SR ~900-1,200 words

## Voice (가장 voice-rich)

- narrative + cautious tone
- hedging 의도적 ("This is, admittedly, an indirect measure")
- mechanistic speculation 1-2개 허용 ("One possible explanation is...")
- limitations 별도 list 금지 — 본문 흐름에 녹임
- "In conclusion" 금지 — 마지막 문단이 결론임이 내용으로 드러나게
- "Taken together" 금지

## 구조 (5 문단 고정)

### §1 Principal findings (~120-150 words)

자기 결과 paraphrase + 패턴 강조.

format 예:
```
In this {study.design} across {n_sites} Korean tertiary hospitals,
{target} was associated with elevated postacute {outcome_category} compared
with {comparator 1} and {comparator 2}. Across the three prespecified
cellular-immune endpoints — neutrophil percentage, eosinophil percentage,
and lymphocyte percentage — the hazard ratios moved consistently in the
same direction against both active comparators, ranging from {min HR} to
{max HR}. Supportive {secondary_outcome} showed a smaller but directionally
concordant association. These associations were robust to empirical
calibration against 54 negative controls (calibrated HR within ±{tolerance}%
of crude).
```

수치는 results.md에서 paraphrase (새 숫자 추가 금지).

### §2 Comparison with literature (~150-200 words)

refpack `discussion/concordance` + `discussion/discordance` 사용.

format:
```
Our cellular-immune signal is concordant with prior smaller cohort studies.
Lee et al.[refpack:Lee2024] reported a similar postacute lymphocyte shift
in a single-center Korean cohort. Kim et al.[refpack:Kim2023] observed a
parallel pattern using laboratory event coding across {n} hospitals.

However, our findings differ from one published study. Chen et al.[refpack:Chen2022]
reported no association between {target} and {outcome} in a {design} cohort,
with HR {value} (95% CI, {l}-{u}). Several explanations are possible: their
{population} differed in {feature}; the lookback window was {different}; and
ascertainment relied on {different method}. The directional difference is
modest and overlaps in confidence intervals when our calibrated estimates
are used.
```

**discordance 인용 반드시 포함** — refpack의 `discussion/discordance` entries (1-2개) 무조건 사용. 본 결과 elevated인데 Chen2022 null → 차이 explain.

### §3 Mechanisms (~120-150 words)

refpack `discussion/mechanism` entries + 1-2 mechanistic speculation 허용.

format:
```
Several biological mechanisms could underlie the observed cellular-immune
trajectory. The appendix has been characterized as a secondary lymphoid
organ contributing to gut-associated immune programming and microbiota
reservoir function [refpack:Bollinger2007]. Loss of this tissue could,
in principle, alter circulating immune cell composition during the postacute
window — a mechanism supported by animal studies of immune homeostasis
[refpack:Smith2020]. One possible explanation for the eosinophil decline
specifically is shift in mucosal immune signaling after appendectomy, though
this is, admittedly, an indirect measure of immune function. Alternative
explanations — including residual confounding by perioperative care or
unmeasured comorbidity — cannot be excluded.
```

hedging 명시적 ("admittedly an indirect measure", "cannot be excluded").

### §4 Strengths and limitations (~150-200 words)

본문 흐름에 녹임 — 별도 bullet list 금지.

format:
```
The principal strengths of this study include the multicenter active-comparator
design, the prespecified analytic plan, and empirical calibration against 54
negative controls — features rarely combined in observational studies of
this question. The dual-comparator approach (cholecystectomy and hernia repair)
mitigates confounding by indication that single-comparator designs cannot
address. Leave-one-site-out sensitivity confirmed that the pooled effect
was not driven by any single hospital.

Several limitations should be noted. First, the analysis was observational;
unmeasured confounders such as perioperative anti-inflammatory exposure may
influence biomarker trajectories. Second, the data were drawn from federated
Korean CDM sites, with raw patient-level data unavailable for re-analysis.
Third, coding-based outcome ascertainment cannot capture clinical severity.
Fourth, severity stratification (perforated vs non-perforated) was not
available across all sites.
```

### §5 Implications + closing (~80-100 words)

결론 함의. "In conclusion" 금지.

format:
```
Postacute cellular-immune trajectory monitoring may be clinically warranted
after appendectomy, particularly in the 91-365 day window where the
association was strongest. Prospective immune cohorts with direct
inflammatory markers and microbiota sampling would help disentangle the
mechanism. For observational researchers, the dual-comparator + empirical
calibration framework demonstrated here offers a tractable approach to
postsurgical biomarker associations beyond the acute window.
```

## 인용 사용

- §2: concordance 2-3개 + discordance **1-2개 강제**
- §3: mechanism 2-3개
- §4: precedent 1개 (matching method, calibration method)
- §1, §5: 인용 최소 (자기 결과 + 함의)

## 수치 사용

- §1: 본문 results.md에서 paraphrase — 새 숫자 추가 금지
- §2: refpack entries effect_size_95CI 인용 가능
- §3, §4, §5: 수치 거의 없음

## 주의

- canonical_terms.md: "prespecified", "postappendectomy"
- 한 문장에 같은 단어 3회 이상 등장 시 voice-rewriter 대상
- "however" / "moreover" / "furthermore" 1 문단에 1회 (overuse = AI tell)
- hedging "admittedly", "cannot be excluded", "in principle"는 §3, §4에서 의도적
- 단정 → 유보 → 재단정 강도 변화 (디자인 doc §4-3)

## 출력 metadata

```
<!-- word_count: 832 / target: ~800 (Discussion, JAMA NO) -->
<!-- citations_used: 8 entries (concordance: 3, discordance: 2 ★, mechanism: 2, precedent: 1) -->
<!-- mechanism_speculation_count: 1 (limit 2) -->
<!-- markers: 0 -->
```
