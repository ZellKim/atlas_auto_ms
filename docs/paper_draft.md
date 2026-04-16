# Immune Shift After Appendectomy: A Multi-center IPD Pooled Analysis of Clinical and Biomarker Outcomes Using the OMOP Common Data Model

---

## Abstract

**Background**: The vermiform appendix is increasingly recognized as a gut-associated lymphoid tissue (GALT) with immune-modulatory and microbial reservoir functions. Although appendectomy is one of the most common emergency procedures worldwide, its long-term immunological consequences remain poorly characterized, particularly at the biomarker level.

**Objective**: To comprehensively evaluate the association between appendectomy and clinical disease outcomes and immunological biomarker changes using multi-center individual patient-level data (IPD) pooled analysis.

**Methods**: We conducted a retrospective comparative effectiveness study across [TBD] Korean healthcare institutions using the OMOP Common Data Model (CDM) and the Federated Network (feedernet). Appendectomy patients were compared with cholecystectomy and hernia repair cohorts. Propensity scores were estimated using Cyclops (regularized logistic regression) with 1:1 nearest-neighbor matching. Site-stratified Cox proportional hazard regression was used to estimate hazard ratios (HR) for [TBD] clinical outcomes and [TBD] biomarker outcomes over a 10-year risk window. Time-window stratified analysis (1–30, 31–90, 91–365, 366–1095, 1096–3650 days) was performed to distinguish acute surgical effects from appendix-specific immune changes. Empirical calibration using [TBD] negative control outcomes was applied to adjust for systematic error.

**Results**: Among [TBD] matched patients from [TBD] institutions, [TBD — 결과 나오면 작성].

**Conclusions**: [TBD — 결과 나오면 작성].

**Keywords**: appendectomy, immune shift, OMOP CDM, multi-center, propensity score matching, biomarker, leukocytes, CRP, gut-associated lymphoid tissue

---

## 1. Introduction

The vermiform appendix has long been characterized as a vestigial organ since Charles Darwin's description in 1871. However, accumulating evidence from comparative anatomy, immunology, and microbiology has fundamentally challenged this view, revealing the appendix as a functionally significant component of the gut-associated lymphoid tissue (GALT).

Histologically, the appendix is densely infiltrated with lymphoid tissue analogous to Peyer's patches and the avian bursa of Fabricius. It harbors abundant B lymphocytes, T lymphocytes, and natural killer cells, and serves as a major site of immunoglobulin A (IgA) induction. IgM⁺IgD⁻ B cells constitute approximately 30% of appendiceal B cells—substantially higher than in circulation—and exhibit memory features with class-switching capacity to IgA. The appendix is thus positioned as a critical organ for the maturation and dissemination of B lymphocytes throughout the intestinal mucosal immune system.

Beyond its immunological role, the appendix has been proposed to function as a "safe house" for commensal gut bacteria, maintaining a biofilm reservoir of the intestinal microbiome that facilitates re-colonization following perturbations such as antibiotic use or infectious colitis.

Several lines of epidemiological evidence have linked appendectomy to the subsequent development of various diseases. A substantial body of evidence suggests that appendectomy is protective against ulcerative colitis, particularly when performed before age 20. In contrast, appendectomy has been consistently associated with an increased risk of Crohn's disease (meta-analysis RR 1.61). The discovery that the appendix contains abundant α-synuclein aggregates has implicated the appendix in Parkinson's disease pathogenesis, though meta-analyses have yielded conflicting results. The association between appendectomy and type 2 diabetes has been categorized as "unlikely" by a recent systematic review, though this conclusion was based on limited evidence.

Despite substantial epidemiological investigation, critical gaps persist. First, existing studies examine single disease outcomes in isolation, precluding comprehensive assessment of overall immunological impact. Second, biomarker-level evidence is virtually absent—no study has simultaneously measured immune and metabolic biomarker changes following appendectomy in a large-scale, multi-center setting. Third, most studies are limited by single-center designs and inability to distinguish surgical stress from appendix-specific effects.

To address these gaps, we conducted a multi-center comparative effectiveness study leveraging the OMOP CDM across [TBD] Korean healthcare institutions. Using IPD pooled analysis with propensity score matching and time-window stratified Cox regression, we aimed to: (1) evaluate [TBD] clinical outcomes and [TBD] biomarker outcomes across two active comparator groups; (2) distinguish acute surgical stress from appendix-specific immune changes through time-window analysis; and (3) validate findings through empirical calibration with [TBD] negative control outcomes.

---

## 2. Methods

### 2.1 Study Design and Data Sources

This was a retrospective, multi-center comparative effectiveness study using the Observational Medical Outcomes Partnership (OMOP) Common Data Model (CDM) version 5.3. Data were obtained from [TBD] Korean healthcare institutions participating in the Federated Network (feedernet) research network. Each institution maintained its own CDM database, and analyses were conducted using a distributed research model where individual patient-level data (IPD) were pooled after extraction.

Institutions were included based on two criteria: (1) successful completion of both clinical and biomarker estimation packages, and (2) availability of all biomarker measurement concepts in the institutional CDM, verified through Achilles data quality reports. Institutions with missing key measurement concepts (e.g., C-reactive protein) were excluded to ensure consistency across sites.

The remaining [TBD] institutions contributed data spanning [TBD]–2025, with observation periods ranging from [TBD] to [TBD] years.

### 2.2 Study Population

**Target cohort**: Patients who underwent appendectomy, identified by OMOP Standard Concept ID 4198190 (Appendectomy) and its descendants. First occurrence only, with a minimum 365-day prior observation period. Patients with concurrent neoplasm of appendix or major abdominal surgery were excluded.

**Comparator cohorts**:
1. **Cholecystectomy** (primary): Similar abdominal surgery, controlling for surgical stress. Patients with neoplasm of gallbladder and major abdominal surgery excluded.
2. **Hernia repair** (primary): Different type of surgery with distinct demographic profile (older, predominantly male). Patients with concurrent major abdominal surgery excluded.
3. **General population** (supplementary): Non-surgical comparator, capped at 50,000 per institution for computational feasibility.

### 2.3 Outcomes

**Clinical outcomes ([TBD])**: Ulcerative colitis, Crohn's disease, asthma, atopic dermatitis, rheumatoid arthritis, Clostridioides difficile infection, Parkinson's disease, biliary calculus, acute myocardial infarction, type 2 diabetes mellitus (lab-confirmed), and colorectal cancer.

**Biomarker outcomes ([TBD])**: Defined as first-onset laboratory abnormality after index date, requiring: (1) at least one normal value within 365 days prior to index in any available measurement concept (ANY criterion), and (2) no prior abnormal values in entire history across all measurement concepts (ALL criterion). This design captures exclusively *de novo* post-surgical abnormalities.

For biomarkers with multiple measurement concepts across institutions (e.g., segmented neutrophils vs. total neutrophils), all variant concepts were included as OR conditions with appropriate unit-specific cutoffs. For biomarkers with different units across institutions (e.g., CRP in mg/dL vs. mg/L), separate outcome cohorts were created for each unit, and site-appropriate results were selected during analysis.

| Biomarker | Abnormality Criterion | Reference |
|-----------|----------------------|-----------|
| Leukocytes (WBC) | > 11 ×10³/μL | WHO standard |
| Neutrophils (%) | > 70% | CBC differential |
| Neutrophils (#) | > 7.7 ×10³/μL or > 7700 /μL | CBC differential |
| Lymphocytes | < 20% | CBC differential |
| Eosinophils | > 7% | Normal range 1–7% |
| Monocytes | > 12% or > 0.8 ×10³/μL | Normal range 2–12% |
| Basophils | > 1% | Normal range 0–1% |
| CRP | > 0.8 mg/dL or > 8 mg/L | Clinical reference |
| ESR | > 20 mm/hr | Clinical reference |
| Rheumatoid factor | > 13 IU/mL | Clinical reference |
| ANA | Positive (ValueAsConcept) | Clinical reference |
| Glucose (DM) | ≥ 126 mg/dL | ADA criteria |
| Glucose (preDM) | 100–125 mg/dL | ADA criteria |
| HbA1c | ≥ 6.5% | ADA criteria |
| LDL | ≥ 160 mg/dL | ATP III |
| Triglyceride | ≥ 200 mg/dL | ATP III |
| HDL | < 40 mg/dL | ATP III |
| Uric acid | > 7 mg/dL | Clinical reference |
| ALT | > 40 U/L | Clinical reference |
| GGT | > 50 U/L | Clinical reference |
| ALP | > 120 U/L | Clinical reference |
| Albumin | < 3.5 g/dL | Clinical reference |
| Hemoglobin | < 12 g/dL | Clinical reference |

**Negative control outcomes ([TBD])**: Conditions with no known causal relationship to appendectomy, used for empirical calibration.

### 2.4 Statistical Analysis

**Propensity score estimation**: Cyclops (Cyclic coordinate descent for logistic, Poisson, and survival analysis) with Laplace prior and 10-fold cross-validation was used to estimate propensity scores using all available baseline covariates including demographics (gender, age group), conditions (long-term), drugs (long-term), and site indicators.

**Matching**: 1:1 nearest-neighbor matching with caliper = 0.2 × SD(logit PS).

**Outcome model**: Site-stratified Cox proportional hazard regression (treatment + site as covariates). Risk window: 1–3,650 days. Prior outcome removal: lookback 99,999 days. Minimum 1 day at risk required.

**Time-window stratified analysis**: Using the same matched cohort, Cox regression was performed separately for six time windows: 1–30 days (acute), 31–90 days (subacute), 91–365 days (short-term chronic), 366–1,095 days (medium-term), 1,096–3,650 days (long-term), and 1–3,650 days (overall reference). This landmark-style approach enables distinction between general surgical stress and appendix-specific immune effects.

**Empirical calibration**: Hazard ratios for [TBD] negative control outcomes were computed using the identical analytical pipeline. The null distribution of systematic error was estimated using the fitNull function from the EmpiricalCalibration R package, and calibrated p-values and confidence intervals were obtained for all outcomes of interest.

### 2.5 Supplementary Descriptive Analysis

ATLAS Cohort Characterization using PRESET MeasurementValueLongTerm feature analysis was deployed across [TBD] institutions to obtain pre- and post-surgical measurement value distributions (mean, SD, median, Q1, Q3) for key biomarkers at five time points (Pre 365d, Post 1–30d, 31–90d, 91–365d, 1y–3y). Time window parameters were overridden for each characterization to achieve the desired intervals.

### 2.6 Software and Reproducibility

OHDSI ATLAS v2.12.0 via feedernet distributed research network; R 4.5.2 with CohortMethod 4.2.2, Cyclops, Andromeda 0.6.0, FeatureExtraction 3.2.0, EmpiricalCalibration; Python 3.13 with atlas_auto package for API automation and data management. Cloud monitoring was implemented using Google Cloud Functions for real-time execution tracking.

---

## 3. Results

### 3.1 Study Population

[TBD] institutions met inclusion criteria. A total of [TBD] appendectomy patients, [TBD] cholecystectomy patients, and [TBD] hernia repair patients were identified.

**Table 1**: Institutional characteristics (to be generated from final data)

After 1:1 propensity score matching:
- vs Cholecystectomy: [TBD] matched pairs
- vs Hernia repair: [TBD] matched pairs

Covariate balance after matching: maximum standardized difference [TBD], number of covariates with StdDiff > 0.1: [TBD].

### 3.2 Clinical Outcomes

[TBD — Table 2: Clinical outcome HRs with calibrated p-values]

### 3.3 Biomarker Outcomes

[TBD — Table 3: Biomarker outcome HRs with calibrated p-values]

### 3.4 Time-Window Stratified Analysis

[TBD — Table 4: Time-window specific HRs for significant biomarkers]

### 3.5 Characterization (Descriptive Statistics)

[TBD — Table 5: Pre/post-surgical biomarker mean, SD, median by time window]

### 3.6 Negative Control Analysis

[TBD — NC null distribution parameters, calibration impact summary]

---

## 4. Discussion

### 4.1 Principal Findings

[TBD — summarize key findings based on results]

### 4.2 Comparison with Previous Literature

**Inflammatory bowel disease**: [TBD]
**Type 2 diabetes**: [TBD]
**Parkinson's disease**: [TBD]
**Cardiovascular disease**: [TBD]

### 4.3 Immune Shift Mechanism

[TBD — interpret biomarker patterns in context of appendix immunology]

The time-window analysis is critical for distinguishing surgical stress from appendix-specific effects. If immune cell changes were solely due to surgical trauma, similar patterns would be expected across all surgical comparators and would resolve within the acute phase (1–30 days). The persistence of changes beyond 91 days, coupled with their specificity to appendectomy versus other surgeries, supports an appendix-specific immunological mechanism.

### 4.4 Strengths

1. Multi-center design using standardized OMOP CDM across [TBD] institutions
2. IPD pooled analysis with Cyclops propensity score matching — more powerful than meta-analysis
3. Two active surgical comparators enabling distinction of surgical stress vs. appendix-specific effects
4. Comprehensive biomarker outcomes — first study to simultaneously assess [TBD] biomarkers
5. Time-window stratified analysis — novel approach to temporal characterization
6. Empirical calibration with [TBD] negative controls — rigorous bias assessment
7. Pre-study data validation — institutional concept availability verified via Achilles reports

### 4.5 Limitations

1. Retrospective observational design — association, not causation
2. Biomarker outcomes are binary (first abnormality) — does not capture continuous value changes directly (supplementary characterization provides this)
3. Measurement concept heterogeneity — different institutions use different LOINC codes for the same laboratory test, requiring multi-concept OR cohort design
4. Unit heterogeneity — CRP measured in mg/dL at some institutions and mg/L at others, requiring dual-cutoff approach
5. Korean population — generalizability to other ethnicities requires further study
6. Appendicitis severity (perforated vs. non-perforated) not distinguishable in CDM
7. General population comparator excluded from primary analysis due to maxCohortSize capping and substantial negative control bias

### 4.6 Clinical Implications

[TBD — discuss conservative management implications, shared decision-making]

---

## 5. Conclusion

[TBD — to be written after results are finalized]

---

## Figures and Tables

| # | Type | Content | Status |
|---|------|---------|--------|
| Table 1 | Institutional characteristics | Site, period, N by cohort | TBD |
| Table 2 | Clinical outcome HRs | Calibrated HR, CI, p for [TBD] outcomes × 2 comparators | TBD |
| Table 3 | Biomarker outcome HRs | Calibrated HR, CI, p for [TBD] outcomes × 2 comparators | TBD |
| Table 4 | Time-window HRs | 6 windows × significant outcomes | TBD |
| Table 5 | Characterization | Pre/post biomarker mean ± SD by time window | TBD |
| Figure 1 | PS distribution | Before/after matching | TBD |
| Figure 2 | KM curves | Cumulative hazard for significant outcomes | TBD |
| Figure 3 | Calibration plot | NC distribution + calibrated outcomes | TBD |
| Figure 4 | Immune shift diagram | Time-window HR pattern | TBD |

---

## References

[To be added]

---

## Supplementary Materials

- General population comparison results
- Full negative control outcome list and HRs
- Institution-specific biomarker concept mapping
- Unit-specific CRP and Neutrophil results by institution
