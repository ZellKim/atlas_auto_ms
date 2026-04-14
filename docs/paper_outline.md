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

### 3.2 Clinical Outcomes (v7b)

#### 3.2.1 vs Cholecystectomy (N=19,087 + 38,170 matched)
- Table 3: HR, 95% CI, p-value for 11 outcomes
- 유의한 결과: T2DM (HR 0.555), CDI (HR 0.605), Biliary calculus (HR 0.460), RA (HR 0.684)

#### 3.2.2 vs General Population (N=7,486 + 14,972 matched)
- T2DM (HR 0.468), Parkinson's (HR 0.366)

#### 3.2.3 vs Hernia Repair (N=8,442 + 16,875 matched)
- Crohn's (HR 3.247), Parkinson's (HR 0.526), T2DM (HR 0.745), CDI (HR 0.627), CRC (HR 0.655)

- Figure 2: Forest plot — 3개 비교군 × 11 outcomes

### 3.3 Biomarker Outcomes

#### 3.3.1 Immune Cell Markers (vs Hernia Repair)
- Table 4: 혈액세포 바이오마커 HR
- **급성 면역 감소**: WBC (0.529), Neutrophils (0.486), Lymphocytes (0.442)
- **알레르기 면역 증가**: Eosinophils (1.334), Monocytes (1.383), Basophils (1.423)
- Figure 3: Immune shift diagram

#### 3.3.2 Metabolic & Inflammatory Markers
- CRP (0.855), Glucose preDM (0.693)
- Triglyceride (1.546), ALT (1.233), Albumin (1.596)

### 3.4 Characterization (보조 근거)
- Table 5: 수술 전/후 시점별 바이오마커 mean, SD (KHNMC 기준)
- Figure 4: 시간에 따른 바이오마커 변화 트렌드

### 3.5 Negative Control Analysis
- Figure 5: Empirical calibration plot (if available)

---

## 4. Discussion

### 4.1 주요 발견 요약
- T2DM: 3개 비교 모두 유의한 감소 → 리뷰의 "unlikely" 반박
- Crohn's: 증가 확인 → 리뷰 지지
- Parkinson's: 감소 → Killinger(2018) 지지, 리뷰 논쟁 해소
- CDI: 감소 → "safe house" 가설 지지
- Immune shift: 새로운 바이오마커 근거

### 4.2 기존 문헌과의 비교

#### T2DM — 새로운 발견
- Wei(2015): positive correlation (HR 1.3)
- Lee(2018): neutral (일반인구), positive (<30세)
- **우리 결과: 반대 방향 (HR 0.47~0.75, 감소)**
- 가능한 설명: PS matching으로 교란 통제 후 실제 효과 드러남
- 충수 제거 → 만성 염증 감소 → 인슐린 저항성 감소?

#### Crohn's disease — 확인
- Kaplan(2007): SIR 1.52, Kaplan(2008) meta: RR 1.61
- **우리 결과: HR 3.25 (vs hernia repair)**
- 장 면역 조절 기능 상실 → 장 염증 취약

#### Parkinson's disease — 논쟁 해소
- Killinger(2018): -19.3% (52년 추적)
- Mohammed(20xx): HR 3.19 (반대 방향, 6개월 washout)
- **우리 결과: HR 0.37~0.53 → Killinger 지지**
- Gut-brain axis: 충수 제거 → α-synuclein 축적 부위 제거

### 4.3 면역 메커니즘 해석

```
충수 (lymphoid tissue, "priming station")
    ↓ 제거
급성 면역 반응 능력 ↓              알레르기/Th2 면역 경향 ↑
(WBC, Neutro, Lympho ↓)          (Eosino, Mono, Baso ↑)
    ↓                                ↓
T2DM ↓ (만성 염증 감소)          Crohn's ↑ (장 면역 조절 상실)
CDI ↓ (장내 세균총 변화)          
Parkinson's ↓ (α-syn 축적 감소)
```

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
