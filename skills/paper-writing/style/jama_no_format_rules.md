# JAMA Network Open — Format Rules

> 본 파일은 voice-rewriter / validator가 JAMA NO 투고 시 hard-check하는 포맷 규칙.
> 원문: https://jamanetwork.com/journals/jamanetworkopen/pages/instructions-for-authors
> 흡수 출처: studies/appendectomy/docs/jama_network_open_guidelines.md (2026-04-19 확인)

## 1. 분량 제한 (hard)

| 항목 | 제한 | validator check |
|---|---|---|
| **Main text** | **≤3,000 words** (abstract/refs/tables/figures/acknowledgments/supplement 제외) | hard reject if >3,000 |
| **Structured Abstract** | **≤350 words** | hard reject if >350 |
| **Key Points** (Question/Findings/Meaning) | **75-100 words total** | hard reject |
| **References** | **50-75개** | hard reject if <50 or >75 |
| **Tables + Figures 합계** | **5개** (5 each 아님) | hard reject |
| Title | ≤100 characters | hard reject |

## 2. 섹션 구조

```
Title Page (word counts 포함)
↓
Structured Abstract (≤350w)
↓
Key Points (75-100w)
↓
Introduction
↓
Methods
↓
Results
↓
Discussion
↓
References (AMA style)
↓
Tables / Figures (합계 5)
↓
Supplementary (eMethods / eTables / eFigures)
```

전통 IMRaD 순서 — Methods가 Results 앞에 (SR과 반대).

## 3. Structured Abstract — 필수 섹션 7개

```
Importance:                  [한 문장 — 왜 이 연구 필요한가]
Objective:                   [한 문장 — 검정할 hypothesis]
Design, Setting, and Participants:  [3-5 문장 — design + period + population + N]
Exposures:                   [target + active comparator(s)]
Main Outcomes and Measures:  [primary + secondary outcomes 정의]
Results:                     [N, matched pairs, primary HR (95% CI), key secondary]
Conclusions and Relevance:   [한 문장 결론 + 한 문장 임상적 의의]
```

**각 헤더 굵게 (bold)**. 총 ≤350 words.

## 4. Key Points (JAMA family 특징)

```
Question:  [한 문장 연구 질문]
Findings:  [1-2 문장 — N + key effect size + 95% CI 포함]
Meaning:   [한 문장 — clinical/scientific implication]
```

**총 75-100 words**. 3개 모두 필수.

## 5. 인용 스타일 — AMA

- **Numeric, 본문 superscript**
- 본문 출현 순서로 번호 매김
- 6명 이하 저자: **모두 열거**
- 7명 이상: **first 3 + et al**
- Journal 약어: PubMed 표준
- 예시: `Lee SH, Kim J, Park MJ, et al. Title. *J Korean Med Sci*. 2023;38(5):e123.`

## 6. Statistical Reporting (Section 3, 엄격)

### 6.1 P-values
- **단독 P-value 금지** — 항상 effect + 95% CI 동반:
  - 예: `HR 0.72 (95% CI 0.65–0.80); P=.001`
- 표기 format:
  - P ≥ .01: 소수점 2자리 (P=.02)
  - P < .01 and ≥ .001: 3자리 (P=.006)
  - P < .001: `P<.001`
- Exact P 권장, 범위 표기 지양
- canonical_terms.md "P-value 표기" 참조

### 6.2 Effect sizes
- Primary/secondary 모두 **95% CI** 필수
- Absolute numbers/rates + measure of uncertainty 우선, P는 2차

### 6.3 Visualization
- Forest plot, KM curve, violin — effect + uncertainty 동시 표기
- 색상 의존 안되게 (B&W readable)

## 7. Reporting Guideline (필수 첨부)

| Study type | Checklist | 우리 case |
|---|---|---|
| 관찰연구 | **STROBE** | ★ |
| RCT | CONSORT | — |
| 진단정확도 | STARD | — |
| Meta-analysis | PRISMA | — |

**STROBE checklist PDF 완성 후 supplement로 제출**. 본문 내 section 번호 인용.

## 8. 윤리 / IRB / Data Sharing (별도 제공 필수)

별도 섹션 (Article Information 묶음):
- IRB approval number + 기관 (예: KHNMC IRB 2025-10-009)
- Informed consent: CDM 2차 데이터 비식별화 → **waiver** (IRB 승인 사항 인용)
- Patient identifier 일체 노출 금지
- **Data Sharing Statement**: 다기관 federated 구조 → raw data 비공개 명시 (jama_network_open_guidelines.md §6 참조)
- **Code Availability Statement**
- **Author Contributions** (CRediT taxonomy, 14 역할)
- **Funding/Support** + Role of Funder
- **Conflict of Interest** (ICMJE Form, 모든 저자)

## 9. Figures 사양

- TIFF, EPS, PDF, PNG, JPG 허용
- **벡터 (EPS/PDF) 선호** for line art
- Raster: 최소 300 DPI (color/grayscale), 600-1200 DPI (line art/text)
- 최대 폭: 175mm (full page) / 85mm (single column)
- Sans-serif font (Helvetica/Arial), 최소 8pt
- 모든 label 명확, 약어 first mention full definition

## 10. Submission

- Portal: https://manuscripts.jamanetworkopen.com
- 파일 포맷: **Word document** (PDF 불가)
- 개별 파일 ≤500 KB / 전체 ≤5 MB / 각 Figure 별도 파일
- **APC**: $3,000 USD (accept 후)

## 11. Preprint 허용

- medRxiv 등 preprint 허용
- Cover letter에 disclosure 필수 (URL 포함)
- 투고 후 preprint update 허용 (버전 번호 구분)

## 12. Cover Letter 구조 (권장)

```
1. 연구 요지 (2-3 문장)
2. Key selling points
   - Novelty
   - Methodology rigor
   - Clinical implications
3. Fit with JAMA Network Open scope
4. Exclusivity statement ("not submitted elsewhere")
5. Suggested reviewers (optional, 3-5)
6. Conflicted/excluded reviewers (optional)
7. Previous review history (있으면)
```

## 13. Validator hard-check 항목 (이 파일에 묶음)

자동 reject 항목:
- [ ] Main text >3,000 words
- [ ] Abstract >350 words
- [ ] Key Points outside 75-100 words
- [ ] References <50 or >75
- [ ] Tables + Figures total ≠5
- [ ] Standalone P-value (without 95% CI)
- [ ] Author CRediT 누락
- [ ] STROBE checklist 미첨부
- [ ] Data Sharing Statement 누락
- [ ] IRB number 누락
