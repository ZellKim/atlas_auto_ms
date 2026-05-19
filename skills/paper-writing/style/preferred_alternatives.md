# Preferred Alternatives — banned word 대체어

voice-rewriter가 banned_words 발견 시 본문 context 보고 아래 대체어 선택.
1:1 매핑이 아닌 *맥락 의존* 선택 — 단순 find/replace 금지.

## Filler verbs

| Banned | Use instead |
|---|---|
| delve into | examine / look at / study |
| leverage | use / draw on / rely on |
| underscore | show / point to / indicate |
| pivotal role / crucial role | role (또는 구체 메커니즘 명시) |
| unlock | enable / allow (또는 동사 자체 삭제) |
| emphasize | (대부분 삭제 — 본문 강도로 표현) |
| highlights | shows / illustrates |

## Transitional / connective filler

| Banned | Use instead |
|---|---|
| Taken together | (그냥 다음 문장으로 — 연결어 없이) |
| In conclusion | (내용으로 결론임이 드러나게) |
| Importantly / Notably / Remarkably | (대부분 삭제) |
| It is important to note that | (삭제 후 본문 직접 서술) |
| Furthermore / Moreover (overused) | And / Also / 또는 절단 (새 문장 시작) |

## Hyperbole / superlatives

| Banned | Use instead |
|---|---|
| comprehensive | (구체 서술 — "covered 35 biomarkers across 4 mechanistic axes") |
| robust | (effect size + CI로 표현 — "remained within ±5%") |
| novel insights | new finding / first to show |
| groundbreaking | (사용 금지 — 본문이 importance 입증) |

## Vague nouns

| Banned | Use instead |
|---|---|
| realm | field / area |
| landscape | (대부분 삭제 — "current evidence on X" 식으로) |
| intricacies | details / mechanism |
| multifaceted | (구체 dimension 명시) |
| holistic approach | (구체 components 명시) |

## Hedge / cliché

| Banned | Use instead |
|---|---|
| shed light on | clarify / explain / show |
| pave the way | enable / support |

## 적용 룰

- voice-rewriter는 단순 substitution 대신 *문장 구조 재작성* 우선.
- 대체어가 어색하면 문장 자체 재구성 (예: "Importantly, X." → "X." 또는 "X — a point that bears on Y.")
- 1 문단 내 동일 transitional 2회 이상 사용 시 alert.
