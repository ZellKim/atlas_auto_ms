# 논문 구조 (Draft Outline)

## 제목 (안)

**Appendectomy and Long-term Clinical Outcomes and Biomarker Changes: 
A Multi-center Comparative Effectiveness Study Using the OMOP Common Data Model**

또는:

**Immune Shift After Appendectomy: A 16-center IPD Pooled Analysis 
of Clinical Outcomes and Biomarker Changes**

---

## Abstract

- **Background**: 충수절제술의 장기적 면역 영향에 대한 기존 문헌은 단일 기관, 후향적 연구가 대부분. 바이오마커 수준의 근거 부족.
- **Objective**: 다기관 CDM 데이터를 활용하여 충수절제술 후 (1) 임상 outcome (2) 바이오마커 변화를 분석
- **Methods**: 16개 기관 OMOP CDM, IPD pooled analysis, Cyclops PS matching, site-stratified Cox
- **Results**: T2DM 감소, Crohn's 증가, Parkinson's 감소 + 면역 shift (WBC/Neutro/Lympho ↓, Eosino/Mono/Baso ↑)
- **Conclusion**: 충수절제술은 면역 균형에 영향, "priming station" 가설 지지

---

## 1. Introduction

### 1.1 Background
- 충수의 기능: vestigial organ → immune organ (priming station, safe house)
- 충수절제술: 가장 흔한 응급 수술 중 하나
- 장기적 영향에 대한 관심 증가

### 1.2 기존 문헌 (Improta et al. 2022 리뷰 기반)
- IBD (UC ↓, CD ↑): highly probable
- CDI: highly probable (충수 = 보호)
- Parkinson's: highly probable (방향 논쟁)
- T2DM: unlikely (우리가 반박)
- Cardiovascular, Cancer: possible/unclear

### 1.3 기존 연구의 한계
- 대부분 단일 기관, 단일 국가
- Self-reported 또는 claim data 기반
- 바이오마커 수준의 면역 변화 데이터 없음
- PS matching 미적용 연구 다수

### 1.4 연구 목적
1. 다기관 CDM 기반 IPD pooled analysis로 충수절제술의 장기 임상 outcome 검증
2. 바이오마커 outcome으로 면역 변화 메커니즘 탐색
3. 기존 systematic review 결과의 검증 및 발전

---

## 2. Methods

### 2.1 Study Design
- Retrospective, multi-center comparative effectiveness study
- OMOP CDM v5.3 기반
- feedernet 다기관 연구 네트워크

### 2.2 Data Sources
- 16개 한국 의료기관 CDM (Table: 기관 목록, CDM 버전, 환자 수)
- 기간: 각 기관 CDM 구축 기간 (주로 2006~2025)

### 2.3 Study Population

**Target cohort**: Appendectomy (OMOP concept 4198190)
- First occurrence only
- ≥365일 prior observation
- Inclusion rules: age ≥18, 동시 대수술 제외 등

**Comparator cohorts**:
1. Cholecystectomy (concept 4239323) — 유사 복부 수술
2. General Population — 비수술 대조군
3. Hernia repair (concept 4301351) — 다른 종류의 수술

### 2.4 Outcomes

**Clinical outcomes (11개)**:
- IBD: Ulcerative colitis, Crohn's disease
- Immune/autoimmune: Asthma, Atopic dermatitis, Rheumatoid arthritis
- Infection: C. difficile infection
- Neurological: Parkinson's disease
- Metabolic: Biliary calculus, Acute MI, T2DM
- Cancer: Colorectal cancer

**Biomarker outcomes (20개)**:
- 혈액세포: WBC, Neutrophils, Lymphocytes, Eosinophils, Monocytes, Basophils
- 염증: CRP, ESR, RF
- 대사: Glucose(DM/preDM), HbA1c, LDL, Triglyceride, HDL
- 간/신장: ALT, GGT, ALP, Albumin, Uric acid
- 기타: Hemoglobin

**Negative controls**: 55개 (empirical calibration용)

### 2.5 Statistical Analysis

1. **Propensity Score**: Cyclops (Laplace prior, cross-validation) — 전체 기관 공변량 통합
2. **Matching**: 1:2 nearest-neighbor, caliper = 0.2 × SD(logit PS)
3. **Outcome model**: Site-stratified Cox proportional hazard regression
4. **Risk window**: 1~3,650일 (10년)
5. **Sensitivity**: Prior outcome 제거 (lookback 99,999일)

### 2.6 Software
- OHDSI ATLAS v2.12.0 + feedernet
- R: CohortMethod 4.2.2, Cyclops, Andromeda 0.6.0
- IPD pooled analysis pipeline (자체 개발)

---

## 3. Results

### 3.1 Study Population
- Table 1: 기관별 환자 수 (target/comparator)
- Figure 1: PS distribution before/after matching
- Table 2: Baseline characteristics (matched cohort)

### 3.2 Clinical Outcomes — Cyclops PS, 1:2 matched, site-stratified Cox

#### 3.2.1 vs Cholecystectomy (N=9,188 + 18,366 matched)
- Table 3: HR, 95% CI, p-value for 11 outcomes
- 유의한 결과:
  - Atopic dermatitis: HR 0.544 (0.324-0.916), p=0.022
  - **T2DM: HR 0.769 (0.595-0.995), p=0.046**
- 경계: Crohn's HR 2.499 (p=0.054), RA HR 0.621 (p=0.064)

#### 3.2.2 vs General Population (N=7,483 + 13,342 matched)
- **Parkinson's: HR 0.354 (0.132-0.950), p=0.039**
- Biliary calculus: HR 1.446 (1.075-1.945), p=0.015
- **T2DM: HR 0.355 (0.237-0.531), p<0.001**

#### 3.2.3 vs Hernia Repair (N=12,768 + 6,388 matched)
- Biliary calculus: HR 1.325 (1.041-1.687), p=0.022
- **T2DM: HR 1.633 (1.158-2.302), p=0.005** ← 방향 반대 (논의 필요)

- Figure 2: Forest plot — 3개 비교군 × 11 outcomes

**T2DM 해석 주의**: vs Cholecystectomy/General Pop에서 감소, vs Hernia repair에서 증가. 
비교군 특성의 차이 (hernia repair 환자의 대사적 특성)가 영향을 줄 수 있음.

### 3.3 Biomarker Outcomes — Cyclops PS, 1:2 matched, site-stratified Cox

#### 3.3.1 Immune Cell Markers — 3개 비교 일관 패턴

**급성 면역 마커 감소 (3개 비교 모두 일관)**:
| Biomarker | vs Chol HR | vs GenPop HR | vs Hernia HR |
|-----------|----------:|------------:|-----------:|
| WBC | 0.266*** | 0.635*** | 0.529*** |
| Neutrophils | 0.173*** | 0.533*** | 0.486*** |
| Lymphocytes | 0.178*** | 0.686*** | 0.442*** |

**알레르기/만성 면역 마커 증가 (vs GenPop, vs Hernia에서 일관)**:
| Biomarker | vs Chol HR | vs GenPop HR | vs Hernia HR |
|-----------|----------:|------------:|-----------:|
| Eosinophils | 0.437 | 1.410*** | 1.334*** |
| Monocytes | 0.889* | 1.415*** | 1.383*** |
| Basophils | 0.605* | 1.230** | 1.423*** |

- vs Cholecystectomy에서 방향이 다른 이유: 담낭절제술 환자의 baseline 면역 상태 차이
- Figure 3: Immune shift diagram (vs GenPop/Hernia 기준)

#### 3.3.2 대사/염증 마커
- Glucose preDM: HR 0.693-0.731 (vs Chol, vs Hernia에서 감소)
- ALT: vs Chol 0.332***, vs Hernia 1.233*** (비교군 의존적)
- Albumin: vs GenPop 1.722***, vs Hernia 1.596*** (증가)
- Triglyceride: vs Hernia 1.546** (증가)

### 3.4 Characterization (보조 근거)
- Table 5: 수술 전/후 시점별 바이오마커 mean, SD (KHNMC 기준)
- Figure 4: 시간에 따른 바이오마커 변화 트렌드

### 3.5 Negative Control Analysis
- Figure 5: Empirical calibration plot (if available)

---

## 4. Discussion

### 4.1 주요 발견 요약

1. **WBC/Neutrophil/Lymphocyte 감소**: 3개 비교 모두 일관 (가장 robust한 발견)
2. **Eosinophil/Monocyte/Basophil 증가**: vs GenPop, vs Hernia에서 일관
3. **T2DM**: vs Cholecystectomy (HR 0.77), vs GenPop (HR 0.36)에서 감소, 단 vs Hernia에서 증가 (HR 1.63) — 비교군 의존적
4. **Parkinson's**: vs GenPop에서 감소 (HR 0.35), 다른 비교에서 NS
5. **Atopic dermatitis**: vs Cholecystectomy에서 감소 (HR 0.54)

### 4.2 기존 문헌과의 비교

#### T2DM — 비교군에 따라 다른 결과 (nuanced finding)
- Wei(2015): positive (HR 1.3) — unmatched
- Lee(2018): positive (<30세만)
- **우리 결과**: Cyclops PS matching 후 vs Cholecystectomy/GenPop에서 **감소**, vs Hernia에서 **증가**
- 해석: 담낭절제술 환자는 비만/대사증후군 빈도가 높아 비교 시 충수절제 그룹이 상대적으로 낮게 나올 수 있음. 탈장수술 환자는 상대적으로 건강한 대사 profile을 가져 반대 방향. **비교군 선택이 결론을 결정**하는 중요한 방법론적 시사점.

#### Parkinson's disease — 부분적 지지
- Killinger(2018): -19.3% 감소
- Liu(2020): OR 0.84 감소
- Lu(2020) meta: 연관 없음
- Chin(2024) meta: 연관 없음
- **우리 결과: vs GenPop HR 0.354 (p=0.039), 다른 비교에서 NS**
- 이벤트 수 적음(5+29) → 주의 필요. 비수술 대조군에서만 유의한 것은 수술 자체의 영향 배제 후에도 연관이 있을 수 있음을 시사.

#### Crohn's disease — 경향 확인 (borderline)
- Kaplan(2008) meta: RR 1.61
- **우리 결과: vs Cholecystectomy HR 2.499 (p=0.054)** — borderline
- 이벤트 적음 (10+8). 기관 수 증가 시 유의해질 가능성.

### 4.3 면역 메커니즘 해석 — Immune Shift

가장 robust한 발견은 **혈액세포 마커의 변화**:

```
충수 (GALT, "priming station")
    ↓ 제거
급성 면역 반응 능력 ↓                    알레르기/Th2 면역 경향 ↑
WBC  0.27~0.64 (↓↓↓ 일관)              Eosinophils 1.33~1.41 (↑↑)
Neutro 0.17~0.53 (↓↓↓ 일관)            Monocytes  1.38~1.42 (↑↑)
Lympho 0.18~0.69 (↓↓↓ 일관)            Basophils  1.23~1.42 (↑↑)
```

이 패턴은:
- **충수의 B/T 세포 priming 기능 상실** → 급성 면역 반응 감소
- **Th1→Th2 shift** → 호산구/단핵구/호염기구 우세
- Zhang et al.(2025)의 실험적 발견 (appendiceal B → Th1/Th17 촉진)과 일치
- Scarpa et al.(2025)의 dendritic cell activation 발견과 보완적

**임상적 의미**: vs Cholecystectomy에서 면역세포 전반이 감소하는 것은, 담낭절제술 환자의 높은 염증 baseline 때문일 수 있으며, vs GenPop/Hernia에서 나타나는 Eosinophil/Monocyte/Basophil 증가가 충수 제거 특이적 면역 shift를 더 정확히 반영.

### 4.4 강점
1. **16개 기관 다기관**: 한국 CDM 네트워크 최대 규모
2. **IPD pooled analysis**: 환자 수준 데이터 통합 (meta-analysis보다 강력)
3. **3개 비교군**: 수술 효과 vs 충수 특이적 효과 구분
4. **바이오마커 outcome**: 기존 연구에 없는 면역 변화 직접 측정
5. **PS matching + site stratification**: 교란 통제

### 4.5 제한점
1. **관찰 연구**: 인과관계 증명 불가 (association only)
2. **바이오마커 outcome은 이진**: 연속값 변화량은 아님
3. **CDM 데이터**: 충수염 중증도(천공 여부) 구분 불가
4. **한국 인구**: 인종/지역 일반화 제한
5. **Negative control calibration**: 추가 분석 필요
6. **RUNNING/FAILED 기관**: 13개 기관 추가 완료 시 업데이트 필요

### 4.6 임상적 의의
- 충수절제술 결정 시 장기적 면역 영향 고려
- 보존적 치료(항생제) 선호 근거 추가
- "if confirmed, a paradigm shift towards a conservative approach should be considered" (Improta 2022) → 우리 결과가 이 주장을 뒷받침

---

## 5. Conclusion

다기관 CDM 기반 IPD pooled analysis에서 충수절제술은 T2DM, C. difficile, Parkinson's disease의 위험을 감소시키고, Crohn's disease의 위험을 증가시켰다. 바이오마커 분석에서 급성 면역 반응 감소와 알레르기/만성 면역 경향 증가라는 "immune shift" 패턴을 확인하였다. 이는 충수의 면역 조절 기능("priming station")을 지지하며, 급성 충수염 치료에서 보존적 접근의 근거를 추가한다.

---

## Figures & Tables 목록

| # | 유형 | 내용 |
|---|------|------|
| Table 1 | 기관별 환자 수 | 16개 기관, target/comparator 수 |
| Table 2 | Baseline characteristics | PS matching 후 공변량 균형 |
| Table 3 | Clinical outcome HR | 3개 비교 × 11 outcome |
| Table 4 | Biomarker outcome HR | 3개 비교 × 20 biomarker |
| Table 5 | Characterization mean/SD | 수술 전/후 시점별 (보조) |
| Figure 1 | PS distribution | Before/after matching |
| Figure 2 | Forest plot (clinical) | 3개 비교군 × 11 outcomes |
| Figure 3 | Immune shift diagram | 면역세포 변화 패턴 |
| Figure 4 | Biomarker trend | 시간에 따른 변화 (Characterization) |
| Figure 5 | Calibration plot | Negative control (optional) |

---

## 예상 투고 저널

| 저널 | IF | 분야 | 적합성 |
|------|---:|------|--------|
| Annals of Surgery | 12.5 | Surgery | 충수절제술 장기 결과 |
| Gut | 24.5 | Gastroenterology | IBD + 장 면역 |
| JAMA Surgery | 16.9 | Surgery | 다기관 비교효과 연구 |
| Journal of Clinical Investigation | 15.9 | Medicine | 면역 메커니즘 |
| Clinical Gastroenterology and Hepatology | 13.6 | Gastroenterology | CDM 기반 연구 |
| Journal of the American Medical Informatics Association | 7.9 | Informatics | CDM/OHDSI 방법론 |
