# Prompt 14 — Abstract Section

> 호출자: `paper-writer` (본문 4 섹션 완료 후, Title보다 먼저)
> 목적: 본문 4 섹션 + Results JSON → 저널 분기 abstract
> 출력 위치: `studies/{study}/docs/draft/{version}/abstract.md`
> 대상 분량: JAMA NO 350 words / SR ≤200 words

## ⚠️ Rule: 본문 외 새 정보 금지

Abstract는 본문 6 섹션의 요약. 본문에 없는 사실 / 수치 / 인용 절대 추가 금지.

## 저널 분기

### A) JAMA NO — Structured (350 words)

각 헤더 **bold**, 7 섹션 필수:

```markdown
**Importance**  [한 문장 — 왜 이 연구 필요한가, 기존 한계]

**Objective**  [한 문장 — study_input.hypotheses.primary 그대로]

**Design, Setting, and Participants**
[3-5 문장]
- design: study_input.study.design 한 문장 요약
- setting: federated OMOP CDM network of N Korean tertiary hospitals
- period: study.data_source.period_start–period_end
- population: study.population 핵심 inclusion + N
- matching: study.analysis.matching 한 문장

**Exposures**
[1-2 문장]
- target: study.exposure.target
- comparators: study.exposure.comparators[] each rationale 한 단어 + N

**Main Outcomes and Measures**
[2-3 문장]
- primary: study.outcome.primary[] each name + endpoint type + window
- secondary: study.outcome.secondary[]
- NC: study.outcome.negative_controls.length count
- calibration: "empirical calibration against negative controls"

**Results**
[3-5 문장, 핵심 수치]
- N matched: total
- Primary HR: each outcome + 95% CI (results.primary에서)
- Calibration: nc median HR, σ
- Sensitivity headline: σ-grid pass, LOSO stable

**Conclusions and Relevance**
[1-2 문장]
- 본 연구 결론
- clinical 함의 한 문장
```

word count: 350 hard limit. 350 초과 시 reject.

### B) Scientific Reports — Unstructured (≤200 words)

헤더 없음, 1-2 문단 자연 흐름:

```markdown
[1 문장 background/motivation]

[2-3 문장 design/setting/population/matching]

[3-4 문장 primary results — HR + 95% CI + calibration headline]

[1-2 문장 conclusion + clinical/scientific relevance]
```

word count: 200 hard limit. 초과 시 reject.

## Key Points (JAMA NO 한정, abstract 다음 위치)

별도 box (`abstract.md` 끝에 `## Key Points` 헤더로 분리):

```markdown
## Key Points

**Question**  [한 문장 연구 질문]

**Findings**  [1-2 문장 — N + key effect size + 95% CI 포함]

**Meaning**  [한 문장 — clinical/scientific implication]
```

word count: 75-100 total (3 box 합) hard limit.

## 수치 사용

- 모든 수치는 본문 results.md → results.json 경로로 검증 (`[NUMBER?]` 마커 잔존 X)
- 본문에 없는 정확한 수치 추가 금지 (예: 본문에서 HR=1.34인데 abstract에서 1.35 작성 금지)
- 본문 round를 그대로 유지

## 인용 사용

Abstract에는 일반적으로 인용 없음 (JAMA NO / SR). 본문이 cite하는 references는 본문 안에만.

## Reduction strategy (분량 초과 시)

본문 → abstract 압축 우선순위:
1. Results 핵심 effect 3개 유지, secondary는 한 문장 합쳐
2. Setting 핵심만 (N sites, period, data source name)
3. Methods는 design + matching + calibration 3 keyword만
4. Implications는 한 문장
5. Importance는 한 문장

## 출력 metadata

```
<!-- word_count: 348 / target: ≤350 (JAMA NO structured) -->
<!-- key_points_word_count: 92 / target: 75-100 -->
<!-- numbers_used: 8 from results.json (all cross-checked vs body) -->
<!-- new_facts: 0 (must equal 0 — abstract from body only) -->
```

## 주의

- canonical_terms.md: HR format `HR {value} (95% CI, {l}–{u})` 통일
- P-value 표기: JAMA NO §3.1 (`P<.001`, `P=.02`)
- "We" / "this study" 본문과 통일
- "FeederNet" 명시 금지 (canonical_terms)
- structured headers (Importance / Objective / 등) JAMA NO에만, SR은 헤더 X
