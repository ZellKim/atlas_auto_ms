# Prompt 01 — Build Reference Pack

> 호출자: `researcher-pubmed`
> 목적: study JSON 기반 PubMed 검색 → 30-60 references → intended_use 분류 → refpack.json
> 출력 위치: `studies/{study}/docs/refpack_{version}.json`

## When to run

- orchestrator Step 2 (refpack 빌드)
- 또는 사용자 명시 호출 (예: "refpack 보강해줘")

## Inputs

- `studies/{study}/docs/study_input_{version}.json` — 핵심 키워드 추출 source
- (선택) `studies/{study}/docs/omop_cdm_papers_2021-2026.csv` — methods/precedent seed
- (선택) `studies/{study}/docs/refpack_v{N-1}.json` — inherit base

## Procedure

### 1. Search keyword 추출

study_input.json에서:
```
target_terms = study.exposure.target + 동의어 (예: "appendectomy" + "appendicectomy")
comparator_terms = study.exposure.comparators[].name (각각)
outcome_terms = study.outcome.primary[].name (1-2 핵심)
population_terms = study.population.inclusion[] 핵심 명사구
method_terms = study.design + study.analysis 키워드 (예: "propensity score matching", "site-stratified Cox", "empirical calibration")
geo_terms = data_source 국적 (예: "Korean", "Asian")
```

검색 쿼리 5-7개 조합:
1. 임상 main: `(target OR target_synonym) AND (outcome) AND ("cohort study" OR "retrospective")` — top 15
2. 임상 secondary: `target AND (outcome_secondary) AND population` — top 8
3. Background/burden: `target AND (epidemiology OR burden OR incidence) AND geo` — top 6
4. Method precedent: `("empirical calibration" OR "negative control") AND observational` — top 4
5. Method precedent 2: `"propensity score" AND "site-stratified" AND multicenter` — top 4
6. Discordance 보강: `target AND outcome AND ("no association" OR "null" OR "conflicting")` — top 5
7. Gap 명시: `target AND (("unclear" OR "limited evidence")) AND outcome` — top 3

### 2. WebSearch / WebFetch 실행

각 쿼리:
1. esearch URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax=20&sort=relevance`
2. PMID list 추출
3. esummary: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmids}&retmode=json` → title, authors, journal, year, volume, pages
4. efetch (abstract): `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmids}&rettype=abstract&retmode=text`

기존 seed (omop_cdm_papers_2021-2026.csv) 우선 후보로 활용.

### 3. 중복 / 후보 정리

PMID 기준 dedupe. 후보 ~50건 정리.

각 entry 필드 채움 (contracts/reference.schema.json):
- citation_key: `{FirstAuthorSurname}{Year}{a|b|c if collision}`
- pmid, doi, title, authors (AMA: 6 이하 all, 7 이상 first 3 + et al), journal, year
- design: abstract / publication type에서 추출 ("RCT", "retrospective cohort", "systematic review", "methodological note")
- population: abstract → "adults aged ≥18 undergoing appendectomy (n=12,345)"
- exposure / outcome: abstract → 짧게
- effect_size_95CI: abstract에서 primary effect 추출 ("HR 0.85 (0.72-1.01)" or null)
- key_finding: 1-2 문장 요약
- limitations: abstract / discussion에서 (있으면)
- quotable_claim: **원문 한 문장 quote** (paper-writer가 그대로 사용 가능)

### 4. intended_use 분류

각 entry에 enum 할당:
- `intro/burden` — incidence/prevalence/burden 통계
- `intro/prior_evidence` — 기존 효과 추정
- `intro/gap` — limitation / "remain unclear" / 알려지지 않은 부분
- `discussion/concordance` — 본 연구 결과 방향 ↔ 일치
- `discussion/discordance` — **불일치 (최소 1, 권장 2 — 강제)**
- `discussion/mechanism` — 메커니즘 가설
- `methods/precedent` — 같은 방법론 선례

분류 기준은 study_input.json `hypotheses.primary` + `results.primary` direction과 비교.

### 5. Discordance 강제

discordance 후보 0건이면:
- 추가 검색: `target AND outcome AND ("no significant" OR "null association" OR "opposing direction")`
- 1건이라도 못 찾으면 orchestrator 통해 사용자에 알리고 manual entry 옵션 제공

### 6. 저장 + 보고

`refpack_{version}.json` JSON array.

paper-orchestrator에게 보고:
```
Refpack 완료 N=42:
- intro/burden: 4
- intro/prior_evidence: 8
- intro/gap: 5
- discussion/concordance: 12
- discussion/discordance: 2 ★ (Chen2022, Patel2023)
- discussion/mechanism: 6
- methods/precedent: 5

Top picks for skeleton 작성 시 use:
- intro/burden: Park2023 (Korean appendectomy incidence)
- discussion/concordance: Lee2024 (cellular immune disturbance)
- discussion/discordance: Chen2022 (no T2D association — 본 결과 elevated와 반대)
- methods/precedent: Schuemie2014 (empirical calibration)
```

## 주의

- 한국 데이터 검색 시 `("Korea" OR "Korean" OR "Republic of Korea")` 필수
- Preprint (medRxiv, bioRxiv) 별도 marking — `added_by: "preprint_manual"` 후 사용
- WebFetch / esearch rate limit (3 req/sec without API key) — `sleep 0.5s` 사이.
- 모르는 effect / population은 `null` — 추측 금지
- `quotable_claim`은 abstract 원문 quote, paraphrase 금지
