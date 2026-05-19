# ms voice profile

> 출처: v9.4 paper draft + paper_draft_CHANGELOG.md (v0→v9.4)
> voice-rewriter가 이 profile을 강제하여 *ms-like* 문체 유지

## 1. 평균 문장 길이 / 분산

- Methods/Results: 평균 22-28 words, SD 8-12 (긴 nominal phrase 많음 — OMOP / CDM / 통계 spec)
- Intro/Discussion: 평균 24-30 words, SD 14-18 (긴 분석문 + 짧은 단언문 혼합)
- Abstract: 평균 22-26 words, 압축형

## 2. 자주 쓰는 접속어 / 연결어 (보존)

- "yet", "though", "however" (overuse 주의 — 1 paragraph 1회)
- 종속절 시작: "Because", "Given that", "Although"
- 대조 도입: "In contrast,", "By contrast,"
- 추가 도입: "Beyond {...}", "In addition,"
- Sequential: "First, ..., Second, ..., Third, ..." (Limitations 흐름에서 자주 쓰임)

## 3. 회피 어휘 (banned_words 보강)

- "delve into", "leverage", "underscore", "pivotal", "crucial role" — 절대 금지
- "Importantly", "Notably", "Remarkably" — Methods/Results에 등장 시 삭제
- "It is important to note that" — 삭제 후 직접 서술
- "Taken together" — 삭제 후 다음 문장으로 연결
- "In conclusion" — Discussion 마지막 문단은 내용으로 결론 표현
- "Furthermore" / "Moreover" — 1 문단 1회 이하 (분산 권장)

## 4. Hedging 빈도 / 위치

Discussion §3-4에 의도적 hedging 1-2회:
- "admittedly", "in principle", "cannot be excluded"
- "may", "suggests", "could" (단정 → 유보 변화)
- "hypothesis-generating rather than ..." 패턴 — v9.4 Discussion 마지막 문단

특히 "Findings are hypothesis-generating; replication ... is needed" 정형 closing phrase.

## 5. Limitations 서술 방식

별도 bullet list **금지**. 본문 흐름에 녹임:
- 한 문단 시작 "Several limitations should be noted." 한 줄 (선택)
- 그 다음 "First, ... Second, ... Third, ..." sequential
- 마지막 "Replication is needed to ..." 식 closing

v9.4 §Strengths and limitations 그대로:
```
Limitations include the observational design (causal inference precluded).
Cholecystectomy-comparator estimates reflect ... The Cox model used standard
partial-likelihood variance rather than sandwich variance clustered by matched
pair; because inference focused on endpoints with large effects, ... the core
conclusions are unlikely to be sensitive to this choice. ... Only 3 of 11
clinical endpoints reached individual significance (one a surgical-indication
artifact), reflecting limited power for sparse incident-disease outcomes.
```

## 6. 인용 위치 선호도

- 문장 끝 위치 비율 ~60% (default)
- 문장 중간 위치 ~30% — "Lee et al.¹² reported X, though Y"
- 문장 시작 위치 ~10% — "Andersson et al.¹⁰ first reported ..."

## 7. 숫자 표현 다양화

같은 HR 표기 강제 X — 본문 흐름에 따라:
- "the hazard ratio was 1.34 (95% CI, 1.18–1.52)"
- "HR 1.34 (95% CI, 1.18–1.52; *P* <.001)"
- "with a hazard ratio of 1.34 (95% CI, 1.18–1.52)"

Table 안에서는 정형 (cHR 1.34 [1.18–1.52])

## 8. 약어 도입 패턴

First mention full + parenthetical:
- "propensity-score matching (PSM)" — 단 v9.4에서는 "1:1 nearest-neighbor matching" 풀어 씀 (PSM 도입 안 함)
- "leave-one-site-out (LOSO)" — methods/sensitivity에서 first mention
- "common data model (CDM)" — Methods §Data sources first mention

이후 약어만 사용.

## 9. 정착어 (canonical_terms.md 참조)

- prespecified (not pre-specified)
- postappendectomy (not post-appendectomy)
- first/second active comparator (not "comparator 1"/"comparator 2")
- α primary window / β secondary window (Greek letters)
- federated OMOP common data model network of N Korean tertiary hospitals (not FeederNet)
- cellular-immune core (defined term — bold first use)
- cross-comparator core (cross-comparator hyphenated)
- hypothesis-generating (closing 정형)

## 10. 1-인칭 사용

- "We" 허용: Methods §Statistical inference, Methods §Data sources ("We applied ..."), Discussion §Implications ("We report ..."), Intro §Objective ("We therefore conducted ...")
- "Our" 허용: Discussion §Comparison ("Our findings ..."), Discussion §Strengths ("Our results ...")
- "I" 금지

## 11. 패턴 — 단정 → 유보 → 재단정

Discussion §3 mechanism 예시:
```
[1] These associations are consistent with a role for appendix-related
    immunological function. (단정)
[2] Mechanistic interpretation is limited by observational design and by
    laboratory testing being itself part of outcome ascertainment. (유보)
[3] The hernia-comparator and the cross-comparator core therefore carry
    primary interpretive weight. (재단정)
```

이 패턴 1-2회 Discussion에서 보존.

## 12. Conclusion closing patterns (v9.4)

- "Findings are hypothesis-generating"
- "Replication with harmonized outcome definitions and explicit measurement-process adjustment is needed"
- 절대 "We conclude that ..." 또는 "In conclusion, ..." 금지

## 13. Adjective economy

- 명사 앞 형용사 최대 2개 ("prespecified cellular-immune cohort" OK; "comprehensive multifaceted novel cross-comparator cohort" 금지)
- 추정 / 정량 표현 우선 ("calibrated HR 0.59-0.66" not "robust 또는 substantial association")

## 14. Voice metrics target (validator 측정 기준)

| metric | target |
|---|---|
| 평균 문장 길이 | 20-30 words |
| 문장 길이 SD | > 10 |
| 문단 시작 패턴 distinct | > 3 |
| 연속 같은 transitional ("however") | ≤ 1 per 문단 |
| hedging 출현 (Discussion 전체) | 3-6회 |
| mechanism speculation (Discussion §3) | 1-2회 |
| 1인칭 사용 비율 | 5-10% (Methods/Discussion 전체) |

voice-rewriter는 각 6 섹션에서 위 metrics 측정 → 편차 큰 곳 재구성.
