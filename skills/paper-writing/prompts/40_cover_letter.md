# Prompt 40 — Cover Letter

> 호출자: `paper-orchestrator` (validator PASS 후, 어셈블 단계)
> 목적: 본문 6 섹션 + abstract + 저널 분기 → cover letter draft
> 출력 위치: `studies/{study}/docs/cover_letter_v{version}.md`

## When to run

- validator PASS 후 어셈블 직전
- 또는 사용자 명시 호출

## Inputs

- `studies/{study}/docs/draft/{version}/abstract.md`
- `studies/{study}/docs/draft/{version}/title.md`
- `studies/{study}/docs/study_input_{version}.json` — paper_meta + study highlights
- `skills/paper-writing/style/{jama_no|sr}_format_rules.md` §12 (Cover letter 구조)
- (있으면) `studies/{study}/docs/cover_letter_v{N-1}.md` — inherited base

## 구조 (저널 분기)

### A) JAMA NO Cover letter

format (jama_network_open_guidelines.md §12.2 따라):

```markdown
[Date]

[Editor name, if known]
JAMA Network Open

Dear Dr. [Editor Surname],

[Paragraph 1 — 연구 요지, 2-3 문장]
- "We are pleased to submit our manuscript titled '{title}' for consideration in JAMA Network Open."
- "This study {핵심 결과 요약 — abstract Importance + Conclusion 압축}."

[Paragraph 2 — Key selling points 3-4개]
- Novelty: e.g., "largest Korean CDM cohort for appendectomy biomarker outcomes"
- Methodology rigor: e.g., "active-comparator design with empirical calibration against 54 negative controls"
- Clinical implications: e.g., "supports postacute monitoring in routine practice"
- (있으면) Prior preprint: "An earlier version of this work was posted on medRxiv [DOI]"

[Paragraph 3 — Fit with JAMA Network Open]
- "This study fits the scope of JAMA Network Open as an observational cohort analysis in clinical medicine, addressing a question of substantial public health relevance."
- 본 paper 어떻게 JAMA NO 독자에게 유용한지

[Paragraph 4 — Exclusivity statement]
- "The manuscript has not been published elsewhere and is not under consideration by any other journal."
- (있으면) preprint disclosure

[Paragraph 5 — Optional: Suggested reviewers]
- 3-5 names + 1-line rationale each
- conflicted/excluded: 따로 list

[Paragraph 6 — Closing]
- "We thank you for considering our manuscript and look forward to your editorial decision."
- corresponding author signature + affiliation

Sincerely,
[Corresponding author name]
[Degree, affiliation, email]
```

word count: 500-800 words 권장.

### B) SR Cover letter

format (디자인 doc + Nature 표준):

```markdown
[Date]

Editor
Scientific Reports

Dear Editor,

[Paragraph 1 — 연구 요지]
[Paragraph 2 — Key findings + clinical/scientific relevance]
[Paragraph 3 — Why SR fit (broad scope + open access)]
[Paragraph 4 — Exclusivity + preprint disclosure if any]
[Paragraph 5 — Closing]

Sincerely,
[Corresponding author]
```

word count: 400-600 words 권장. JAMA NO보다 짧음.

## Key selling points 추출 룰

study_input.json에서:
- N sites + N target patients
- methodology (active-comparator + PSM + calibration)
- 핵심 결과 (HR direction + 95% CI)
- prior work / preprint (paper_meta.preprint_doi)

abstract.md의 Importance / Conclusions 그대로 paraphrase OK (사실 동일).

## 인용 사용

Cover letter는 references 없음 (외부 인용 없음). 본 paper 자체 referencing OK.

## 수치 사용

본문 / abstract에 등장한 수치만 사용. 새 수치 X.

## 주의

- canonical_terms.md: "prespecified", "postappendectomy", "federated OMOP CDM network"
- "FeederNet" 명시 금지
- Hyperbole 금지 (banned_words: "comprehensive", "groundbreaking", "robust" 등)
- Suggested reviewers는 사용자 입력 필요 (자동 추천 X — 사용자에게 AskUserQuestion)
- Corresponding author / affiliation / contact는 paper_meta + 사용자 입력

## 출력 metadata

```
<!-- word_count: 612 / target: 500-800 (JAMA NO) -->
<!-- selling_points: [novelty, rigor, implications, preprint] -->
<!-- suggested_reviewers: 0 (user input required) -->
```

## 사용자 인터랙션

- Suggested reviewers — orchestrator를 통해 AskUserQuestion (3-5 names)
- 결제 / authorship form / data sharing detail — cover letter 본문은 짧게 언급, supplement에서 full
