# Prompt 12 — Introduction Section

> 호출자: `paper-writer` (Methods 의존성 없이 병렬 가능)
> 목적: refpack `intro/*` + study_input.hypotheses → 4 문단 Introduction
> 출력 위치: `studies/{study}/docs/draft/{version}/intro.md`
> 대상 분량: JAMA NO ~350-450 words / SR ~500-600 words

## Voice

- 약간 narrative — Methods보다 부드러움, Discussion보다 단조
- 1인칭 ("we hypothesized that...") 마지막 문단에 OK
- AI 냄새 금지: delve / leverage / underscore / pivotal / "It is important to note"

## 구조 (4 문단 고정)

### §1 Burden (~80-100 words)

질병 / target 임상 절차 burden, 한국/Asian 통계 우선.

inputs:
- refpack `intro/burden` entries (Park2023 같은 incidence/prevalence)
- study.population에서 target 명시

format 예:
```
{Target} is one of the most common {category} surgical procedures, with
approximately {incidence_n} cases annually in {region} [refpack:Park2023].
{Target} accounts for {pct}% of {category} hospitalizations, with mean
hospital stay of {days} days [refpack:Lee2020].
```

수치는 refpack의 entry.effect_size_95CI / key_finding에서 추출. paraphrase OK이지만 출처 명시.

### §2 Prior evidence (~100-130 words)

target / outcome 기존 연구 — 효과 추정, association, 메커니즘.

inputs:
- refpack `intro/prior_evidence` entries
- 2-4 references 정도. 한 문장에 인용 5개 이상 금지.

format 예:
```
Prior cohort studies have linked {target} to {outcome category}
[refpack:Lee2024, Kim2023]. Lee et al. reported a {effect} in {biomarker}
among {population} over {window} of follow-up [refpack:Lee2024]. Animal
data suggest {mechanism gist} [refpack:Smith2020]. However, evidence on
the trajectory of {outcome} beyond {acute window} remains sparse, especially
in multicenter Asian cohorts.
```

### §3 Gap (~80-100 words)

기존 연구 한계 + 본 연구 contribution.

inputs:
- refpack `intro/gap` entries
- study_input.study.design 의 novelty (multicenter / federated / active-comparator / NC calibration 등)

format 예:
```
Three gaps remain. First, prior studies have largely been single-center,
limiting generalizability across surgical practice patterns [refpack:...]. Second,
active-comparator designs that account for confounding by indication are
uncommon in this setting [refpack:...]. Third, postacute trajectories beyond
30 days have rarely been examined in a uniform OMOP CDM cohort. Empirical
calibration with negative controls is also infrequent.
```

### §4 Objective + Hypothesis (~60-80 words)

study_input.hypotheses.primary 한 문장 그대로 + 디자인 가벼운 한 문장.

format:
```
We therefore conducted a {study.design} comparing {target} with {comparators}
across {n_sites} Korean tertiary hospitals using federated OMOP CDM data,
with site-stratified Cox regression and empirical calibration against
{n_NC} negative controls. We hypothesized that {hypotheses.primary}.
```

## 인용 사용

- refpack의 `intro/*` intended_use entry만 인용
- citation_key 마커: `[refpack:Lee2024]`
- 한 문장에 5+ 인용 묶기 금지 — 분산
- discordance 인용은 Intro에 사용 X (Discussion §2에 reserve)

## 수치 사용

- §1 burden: refpack entry의 incidence / N — 추측 금지, refpack의 key_finding / effect_size_95CI에 있는 것만
- §4 objective: study_input.data_source.n_sites, study.outcome.negative_controls.length 정확히

## 주의

- canonical_terms.md: "federated OMOP CDM network of N Korean tertiary hospitals"
- "FeederNet" 명시 금지
- §3 gap은 본 연구가 채우는 것만 명시 — 다른 연구 비판조 금지
- §4 objective는 hypotheses.primary를 그대로 쓰되, 동사 자연스럽게 ("We hypothesized that..." or "We aimed to...")

## 출력 metadata

```
<!-- word_count: 408 / target: ~400 (Intro, JAMA NO) -->
<!-- citations_used: [Park2023, Lee2020, Lee2024, Kim2023, Smith2020] -->
<!-- markers: 0 -->
```
