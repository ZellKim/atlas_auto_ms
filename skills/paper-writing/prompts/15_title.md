# Prompt 15 — Title

> 호출자: `paper-writer` (Abstract 완료 후, 마지막 섹션)
> 목적: 본문 6 섹션 + abstract → 저널 제한 title
> 출력 위치: `studies/{study}/docs/draft/{version}/title.md`
> 대상: JAMA NO ≤100 chars / SR ≤200 chars

## ⚠️ Rule: 본문 키워드 추출 only

Title은 본문 / abstract의 키워드만 사용. 본문에 없는 새 framing 금지.

## 구조 원칙

1. **Neutral association framing** — 인과 표현 금지 ("X causes Y" 금지, "X and Y" / "X associated with Y" OK)
2. **핵심 4 요소**:
   - target intervention/exposure
   - outcome category
   - design hint (multicenter / cohort 등)
   - geographic scope (Korean / regional)
3. **약어 금지** — 가능한 한 풀어 쓰기 (title에 약어는 acceptance 후 typesetting에서 처리)
4. **콜론 활용 가능** — 주제: 디자인

## 저널 분기

### A) JAMA NO — ≤100 chars

format examples:
```
"Appendectomy and Postacute Laboratory Abnormality Events in 15 Korean Hospitals"
(79 chars — v9.4 actual title)

"Cellular Immune Trajectory After Appendectomy: A Multicenter Korean Cohort"
(78 chars)

"Active-Comparator Cohort of Appendectomy and Postacute Biomarker Outcomes"
(77 chars)
```

### B) SR — ≤200 chars

JAMA NO format + 부제 가능:
```
"Postacute Cellular Immune Trajectory After Appendectomy: A Multicenter
Federated Cohort Study of 15 Korean Tertiary Hospitals with Empirical
Calibration"
```

## Title 작성 워크플로우

### 1. 키워드 후보 추출

본문에서 자주 등장하는 명사구:
```bash
grep -oE "[A-Z][a-z]+( [a-z]+)*" {methods,results,abstract}.md | sort | uniq -c | sort -rn | head -20
```

후보 set (예시):
- appendectomy
- cellular immune / immune trajectory
- postacute / postappendectomy
- biomarker / laboratory
- multicenter / federated / Korean
- cohort / active-comparator
- calibration

### 2. 후보 3-5개 작성

각 후보:
- 길이 (chars) 명시
- neutral framing 확인
- canonical_terms.md 변종 없음 확인

예:
```
1. "Appendectomy and Postacute Cellular Immune Events in 15 Korean Hospitals" (74 chars)
2. "Postacute Cellular Immune Trajectory After Appendectomy: A 15-Site Korean Cohort" (84 chars)
3. "Appendectomy and Cellular Immune Biomarkers: A Multicenter Active-Comparator Cohort" (87 chars)
```

### 3. orchestrator에 후보 보고 + 선택

paper-orchestrator에게 candidates 보고 후 user 선택 (또는 orchestrator가 default 선택 = 길이 가장 짧고 keyword 핵심 잡은 것).

## 주의

- canonical_terms.md: "postappendectomy" (no hyphen), "prespecified" (no hyphen)
- "FeederNet" 명시 금지 — "Federated CDM" / "Multicenter Korean" 표현
- "Novel" / "Comprehensive" / "Robust" 금지 (banned_words)
- Title case (Each Word Capitalized) JAMA / SR 일반적 사용
- 콜론 후 첫 단어 capitalize OK
- 숫자 (15 hospitals) keep arabic — 본문 / abstract와 일치

## 출력 metadata

```
<!-- title: "Appendectomy and Postacute Cellular Immune Events in 15 Korean Hospitals" -->
<!-- char_count: 74 / target: ≤100 (JAMA NO) -->
<!-- canonical_terms_check: PASS -->
<!-- banned_words_check: PASS -->
<!-- candidates_considered: 5 -->
```
