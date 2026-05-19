# Scientific Reports — Format Rules

> 본 파일은 voice-rewriter / validator가 SR 투고 시 hard-check하는 포맷 규칙.
> 원문: https://www.nature.com/srep/author-instructions/submission-guidelines

## 1. 분량 제한

| 항목 | 제한 | hard check |
|---|---|---|
| Main text (Intro+Results+Discussion+Methods) | ~4,500 words (typical) | warning if >5,000 |
| Abstract | **≤200 words, unstructured** | reject if >200 |
| References | **≤60개** (typical) | warning if >60 |
| Title | ≤200 characters | hard reject if > |

## 2. 섹션 순서 (⚠️ 전통 IMRaD와 다름)

```
Title
↓
Abstract (≤200w, unstructured)
↓
Introduction
↓
Results        ← Results가 Methods 앞에
↓
Discussion
↓
Methods        ← Methods가 Discussion 뒤
↓
References
↓
Figures / Tables / Supplementary
```

**Methods 위치가 가장 중요한 SR 특이점**. paper-writer는 본문 작성 시 이 순서로 출력.

## 3. 인용 스타일

- **Numeric, superscript** (Vancouver-like)
- 본문 안: "as Lee et al.¹² reported..."
- 동일 참조 재인용: 같은 번호 유지
- Reference list: 본문 출현 순서 (alphabetical 아님)

## 4. 필수 추가 섹션 (References 뒤, Article Information 묶음)

Nature 스타일 묶음 (디자인 doc §3 참조):
- Data availability
- Code availability
- Acknowledgements
- Author contributions
- Competing interests
- Additional information

## 5. Abstract — unstructured (JAMA NO와 결정적 차이)

```
[1 문장 background/motivation]
[2-3 문장 design/population/intervention]
[3-4 문장 results — primary effect size + CI]
[1-2 문장 conclusion + clinical relevance]
```

**Structured headings 금지** (Importance/Objective/Methods/Results/Conclusions 헤더 X).

## 6. Discussion 구조 (디자인 doc §4 L3)

5 문단 고정:
1. Principal findings
2. Comparison with literature (refpack discussion/concordance + 1-2 discordance)
3. Mechanisms (mechanistic speculation 1-2개 허용 — "One possible explanation is...")
4. Strengths and limitations (본문 흐름에 녹임 — 별도 list X)
5. Implications

## 7. Methods 톤

- 건조, 짧은 문장
- 수동태 허용 ("Patients were matched...")
- 수식어 최소
- 분석 spec → SAP/study_input.json 그대로

## 8. 인용 위치 다양화 규칙

- 인용을 문장 *중간*에 배치 허용: `...Lee et al.¹² reported a 23% reduction, though the population differed.`
- 한 문장에 인용 5개 이상 묶기 금지 — 분산
