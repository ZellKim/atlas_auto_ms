# ============================================================
# 바이오마커 기술통계 테스트 (본원 KHNMC)
# 충수절제술 코호트 환자의 수술 전/후 바이오마커 값 기술통계
# ============================================================

library(DatabaseConnector)
library(dplyr)
library(tidyr)

# ── DB 접속 ──────────────────────────────────────────────
connectionDetails <- createConnectionDetails(
  dbms = "postgresql",
  connectionString = "jdbc:postgresql://192.168.53.10:5432/omop",
  user = "dbadmin",
  password = "INIT@1234"
)

cdmDatabaseSchema <- "cdmpv53_251128"
resultsDatabaseSchema <- "cdmpv53_251128_results_fnet_v2120"

conn <- connect(connectionDetails)

# ── 바이오마커 Concept ID 매핑 ────────────────────────────
# measurement_concept_id로 직접 조회
biomarker_concepts <- data.frame(
  name = c(
    "Leukocytes", "Neutrophils", "Lymphocytes", "Eosinophils",
    "Monocytes", "Basophils", "CRP", "ESR",
    "Rheumatoid_factor", "ANA",
    "Glucose", "HbA1c",
    "LDL", "Triglyceride", "HDL",
    "GFR", "Uric_acid",
    "ALT", "GGT", "ALP", "Albumin", "Hemoglobin"
  ),
  concept_id = c(
    3000905,  # Leukocytes [#/volume] in Blood
    3017732,  # Neutrophils [#/volume] in Blood
    3004327,  # Lymphocytes [#/volume] in Blood
    3013115,  # Eosinophils [#/volume] in Blood
    3002385,  # Monocytes [#/volume] in Blood
    3037575,  # Basophils [#/volume] in Blood
    3020460,  # C reactive protein [Mass/volume]
    3013707,  # Erythrocyte sedimentation rate
    3019971,  # Rheumatoid factor
    3024561,  # Antinuclear Ab
    3004501,  # Glucose [Mass/volume] in Serum or Plasma
    3004410,  # Hemoglobin A1c/Hemoglobin.total
    3028437,  # LDL Cholesterol
    3022192,  # Triglyceride
    3007070,  # HDL Cholesterol
    3030354,  # Glomerular filtration rate
    3000285,  # Urate [Mass/volume] in Serum or Plasma
    3006923,  # ALT [Enzymatic activity/volume]
    3004077,  # GGT [Enzymatic activity/volume]
    3035995,  # ALP [Enzymatic activity/volume]
    3024561,  # Albumin (재확인 필요)
    3000963   # Hemoglobin [Mass/volume] in Blood
  ),
  stringsAsFactors = FALSE
)

# ── Step 1: 충수절제술 코호트 확인 ────────────────────────
# cohort_definition_id = 1072 (E01_Appendectomy_ms)
cat("=== Step 1: 코호트 확인 ===\n")

cohort_count_sql <- "
SELECT cohort_definition_id, COUNT(*) as n
FROM @results_schema.cohort
WHERE cohort_definition_id IN (1072, 1074, 1121, 1076)
GROUP BY cohort_definition_id
ORDER BY cohort_definition_id
"

cohort_counts <- renderTranslateQuerySql(
  conn,
  cohort_count_sql,
  results_schema = resultsDatabaseSchema
)
print(cohort_counts)

# ── Step 2: 먼저 어떤 measurement concept이 실제 있는지 확인 ──
cat("\n=== Step 2: 사용 가능한 바이오마커 확인 ===\n")

available_sql <- "
SELECT m.measurement_concept_id, c.concept_name,
       COUNT(*) as n_records,
       COUNT(DISTINCT m.person_id) as n_persons,
       AVG(m.value_as_number) as mean_val,
       MIN(m.value_as_number) as min_val,
       MAX(m.value_as_number) as max_val
FROM @cdm_schema.measurement m
JOIN @cdm_schema.concept c ON m.measurement_concept_id = c.concept_id
WHERE m.measurement_concept_id IN (@concept_ids)
  AND m.value_as_number IS NOT NULL
GROUP BY m.measurement_concept_id, c.concept_name
ORDER BY n_records DESC
"

available <- renderTranslateQuerySql(
  conn,
  available_sql,
  cdm_schema = cdmDatabaseSchema,
  concept_ids = biomarker_concepts$concept_id
)
print(available)

# ── Step 3: 충수절제술 코호트 환자의 수술 전/후 바이오마커 ──
cat("\n=== Step 3: 수술 전/후 바이오마커 기술통계 ===\n")

# 실제 있는 concept만 사용
if (nrow(available) > 0) {
  valid_concepts <- available$MEASUREMENT_CONCEPT_ID

  biomarker_sql <- "
  SELECT
    co.cohort_definition_id,
    m.measurement_concept_id,
    c.concept_name,
    CASE
      WHEN m.measurement_date < co.cohort_start_date THEN 'pre'
      ELSE 'post'
    END as period,
    CASE
      WHEN m.measurement_date < co.cohort_start_date
        AND m.measurement_date >= co.cohort_start_date - 365 THEN 'pre_365d'
      WHEN m.measurement_date >= co.cohort_start_date
        AND m.measurement_date < co.cohort_start_date + 30 THEN 'post_30d'
      WHEN m.measurement_date >= co.cohort_start_date + 30
        AND m.measurement_date < co.cohort_start_date + 90 THEN 'post_90d'
      WHEN m.measurement_date >= co.cohort_start_date + 90
        AND m.measurement_date < co.cohort_start_date + 365 THEN 'post_365d'
      WHEN m.measurement_date >= co.cohort_start_date + 365 THEN 'post_1y_plus'
      ELSE 'other'
    END as time_window,
    COUNT(*) as n_records,
    COUNT(DISTINCT co.subject_id) as n_persons,
    AVG(m.value_as_number) as mean_val,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY m.value_as_number) as median_val,
    STDDEV(m.value_as_number) as sd_val,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY m.value_as_number) as q1_val,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY m.value_as_number) as q3_val,
    MIN(m.value_as_number) as min_val,
    MAX(m.value_as_number) as max_val
  FROM @results_schema.cohort co
  JOIN @cdm_schema.measurement m
    ON co.subject_id = m.person_id
  JOIN @cdm_schema.concept c
    ON m.measurement_concept_id = c.concept_id
  WHERE co.cohort_definition_id = 1072
    AND m.measurement_concept_id IN (@concept_ids)
    AND m.value_as_number IS NOT NULL
    AND m.measurement_date >= co.cohort_start_date - 365
    AND m.measurement_date <= co.cohort_start_date + 3650
  GROUP BY co.cohort_definition_id, m.measurement_concept_id, c.concept_name,
    CASE WHEN m.measurement_date < co.cohort_start_date THEN 'pre' ELSE 'post' END,
    CASE
      WHEN m.measurement_date < co.cohort_start_date
        AND m.measurement_date >= co.cohort_start_date - 365 THEN 'pre_365d'
      WHEN m.measurement_date >= co.cohort_start_date
        AND m.measurement_date < co.cohort_start_date + 30 THEN 'post_30d'
      WHEN m.measurement_date >= co.cohort_start_date + 30
        AND m.measurement_date < co.cohort_start_date + 90 THEN 'post_90d'
      WHEN m.measurement_date >= co.cohort_start_date + 90
        AND m.measurement_date < co.cohort_start_date + 365 THEN 'post_365d'
      WHEN m.measurement_date >= co.cohort_start_date + 365 THEN 'post_1y_plus'
      ELSE 'other'
    END
  ORDER BY m.measurement_concept_id, time_window
  "

  results <- renderTranslateQuerySql(
    conn,
    biomarker_sql,
    results_schema = resultsDatabaseSchema,
    cdm_schema = cdmDatabaseSchema,
    concept_ids = valid_concepts
  )

  cat(sprintf("\n총 %d행 결과\n", nrow(results)))
  print(results)

  # CSV 저장
  output_dir <- file.path(getwd(), "test_output")
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  write.csv(results, file.path(output_dir, "biomarker_descriptive_KHNMC.csv"),
            row.names = FALSE)
  cat(sprintf("\n저장: %s\n", file.path(output_dir, "biomarker_descriptive_KHNMC.csv")))
}

disconnect(conn)
cat("\n=== 완료 ===\n")
