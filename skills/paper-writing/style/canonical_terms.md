# Canonical Terms — 정착어 ledger

paper-writing harness 전체에 걸쳐 같은 개념을 **같은 단어로** 부르기 위한 1-source 사전.
voice-rewriter가 이 사전에 어긋난 변형을 발견하면 canonical로 통일.

## 채우는 방법

`studies/appendectomy/docs/paper_draft_CHANGELOG.md` (83KB, v0~v9_4 결정 이력) 에서 추출.
Step 4 (dry-run seed) 단계에서 paper-orchestrator가 자동 추출 후 user가 확정.

## 형식

```
| concept | canonical | banned variants | source |
|---|---|---|---|
| 후속 관찰 기간 | follow-up | followup / follow up | CHANGELOG v8.1 |
| 사전지정 | prespecified | pre-specified | CHANGELOG v9.4 |
```

## 현재 등록된 항목 (v9.4 confirmed)

| concept | canonical | banned variants | source |
|---|---|---|---|
| 사전지정 | prespecified | pre-specified | v9.4 integrity fix |
| 충수절제술 후 | postappendectomy | post-appendectomy / post appendectomy | v9.4 integrity fix |
| 평균 추적기간 | follow-up | follow up / followup | v9.4 Methods §Data Sources |
| 사후 분석 | post hoc | post-hoc / posthoc | (관행) |
| Cox 비례위험 | Cox proportional hazards | Cox PH (only after first mention) | v9.4 Methods |
| Korean tertiary hospital network | federated OMOP common data model network of N Korean tertiary hospitals | FeederNet / feedernet 직접 명시 금지 | memory: feedback_no_feedernet_in_papers + v9.4 |
| HR 표기 (본문) | HR {value} (95% CI, {l}–{u}); *P* = .### | HR=##, 95%CI: ## to ## | JAMA NO format §3.1 |
| HR 표기 (Table) | cHR {value} ({l}–{u}) | (정형) | v9.4 Table 2/3 |
| P-value 표기 | *P* = .### (italicized P, en-dash) — 단독 금지, effect+CI 동반 | p=## / P value=## / P<0.001 (without italics) | JAMA NO format §3.1 |
| 1차 / 2차 비교군 | first active comparator (cholecystectomy) / second active comparator (hernia repair) | comparator 1 / comparator 2 | v9.4 integrity fix |
| 1차 위험 구간 | α primary window (31–3,650 days postacute) | "primary window" 단독 | v9.4 risk window 분기 |
| 2차 위험 구간 | β secondary window (1–3,650 days, including 1–30-day acute interval) | "secondary window" 단독 | v9.4 risk window 분기 |
| 세포면역 core 3 endpoint | cross-comparator cellular-immune core (low lymphocyte percentage, neutrophilia, elevated WBC) | "immune triad" / "cellular triad" (banned) | v9.4 Results / Discussion 정형 |
| 보조 염증 endpoint | supportive inflammatory endpoint (CRP elevated) | "secondary CRP" / "auxiliary CRP" | v9.4 Results §Biomarker Findings |
| Filter 이름 | 365-to-30-day prior-abnormality-exclusion filter | "lookback filter" 단독 / "exclusion period" | v9.4 Methods §PSM and Cox |
| LOSO retention | 15/15 protective LOSO retention | LOSO 15 (단축) — first mention full | v9.4 Results §Sensitivity |
| 결과 framing | hypothesis-generating | "conclusive" / "definitive" 금지 (banned hyperbole) | v9.4 Conclusions closing pattern |
| Replication call | "replication with harmonized outcome definitions ... is needed" | (정형 closing) | v9.4 Conclusions |

## 한자/한글 표기 (en+ko 모드)

| concept | en | ko |
|---|---|---|
| 충수절제술 | appendectomy | 충수절제술 |
| 담낭절제술 | cholecystectomy | 담낭절제술 |
| 탈장 (active comparator) | hernia repair | 탈장 수술 |

## 적용 룰

- canonical 외 variant 발견 시 voice-rewriter alert + 자동 substitution
- 약어 정책: **first mention full + parenthetical 약어, 이후 약어만**. 예: "Cox proportional hazards (Cox PH)"
- 새 abbreviation 도입 시 본 문서에 등록
