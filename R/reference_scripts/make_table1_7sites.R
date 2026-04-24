Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
library(CohortMethod)
library(data.table)

BASE_DIR <- "C:/Users/data1/Desktop/atlas_auto_cmdata"
RESULT_DIR <- file.path(BASE_DIR, "results_v7b")
OUTPUT_DIR <- file.path(BASE_DIR, "table1_output")
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

KEEP_SITES <- c("AUMC_5.3.1_11", "GNUCH_5.3.1_06", "GNUH_5.3.1_07",
                "HUMC_DONGTAN_5.3.1_04", "JCMJ_5.3.1_04",
                "KDH_5.3.1_08", "KHNMC_5.3.1_08")

# target=1072(Appendectomy), comparator=1074(Chol)/1121(Hernia)
COMPARISONS <- list(
  list(target = 1072, comparator = 1074, name = "vs_Chol"),
  list(target = 1072, comparator = 1121, name = "vs_Hernia")
)

zips <- list.files(RESULT_DIR, pattern = "\\.zip$", full.names = TRUE)

for (comp in COMPARISONS) {
  cat(sprintf("\n========== %s ==========\n", comp$name))

  all_balance <- data.frame()
  all_attrition <- data.frame()

  for (site in KEEP_SITES) {
    zip_file <- zips[grep(site, zips)]
    if (length(zip_file) == 0) {
      cat(sprintf("  %s: zip not found\n", site))
      next
    }
    zip_file <- zip_file[1]

    # balance RDS 찾기
    zip_contents <- unzip(zip_file, list = TRUE)$Name
    balance_pattern <- sprintf("balance.*t%d_c%d.*_a1\\.rds$", comp$target, comp$comparator)
    balance_files <- grep(balance_pattern, zip_contents, value = TRUE)

    if (length(balance_files) == 0) {
      cat(sprintf("  %s: no balance file for %s\n", site, comp$name))
      next
    }

    # 첫 번째 balance 파일 사용
    tmp_dir <- tempdir()
    unzip(zip_file, files = balance_files[1], exdir = tmp_dir)
    balance <- readRDS(file.path(tmp_dir, balance_files[1]))
    balance$site <- site
    all_balance <- rbind(all_balance, balance)

    # attrition.csv
    attrition_file <- grep("attrition\\.csv$", zip_contents, value = TRUE)
    if (length(attrition_file) > 0) {
      unzip(zip_file, files = attrition_file[1], exdir = tmp_dir)
      attrition <- fread(file.path(tmp_dir, attrition_file[1]))
      attrition$site <- site
      all_attrition <- rbind(all_attrition, attrition)
    }

    cat(sprintf("  %s: %d covariates\n", site, nrow(balance)))
  }

  if (nrow(all_balance) == 0) {
    cat("  No balance data found\n")
    next
  }

  # 기관별 합산 (weighted mean by population size)
  # before matching: sum of target/comparator across sites
  pooled <- all_balance[, c("covariateId", "covariateName", "analysisId",
                            "beforeMatchingMeanTarget", "beforeMatchingMeanComparator",
                            "beforeMatchingStdDiff",
                            "afterMatchingMeanTarget", "afterMatchingMeanComparator",
                            "afterMatchingStdDiff")]

  # 중복 covariateId가 있으면 기관별 평균
  pooled_agg <- aggregate(
    cbind(beforeMatchingMeanTarget, beforeMatchingMeanComparator, beforeMatchingStdDiff,
          afterMatchingMeanTarget, afterMatchingMeanComparator, afterMatchingStdDiff) ~
      covariateId + covariateName + analysisId,
    data = pooled, FUN = mean, na.rm = TRUE
  )

  # createCmTable1 사용
  tryCatch({
    table1 <- createCmTable1(pooled_agg,
                             beforeLabel = "Before matching",
                             afterLabel = "After matching",
                             targetLabel = "Appendectomy",
                             comparatorLabel = ifelse(comp$comparator == 1074, "Cholecystectomy", "Hernia repair"))

    out_file <- file.path(OUTPUT_DIR, sprintf("table1_%s.csv", comp$name))
    write.csv(table1, out_file, row.names = FALSE)
    cat(sprintf("  Saved: %s (%d rows)\n", out_file, nrow(table1)))

    # 상위 항목 출력
    cat("\n  Preview:\n")
    print(head(table1, 20))
  }, error = function(e) {
    cat(sprintf("  createCmTable1 error: %s\n", e$message))

    # fallback: raw balance 저장
    out_file <- file.path(OUTPUT_DIR, sprintf("balance_pooled_%s.csv", comp$name))
    write.csv(pooled_agg, out_file, row.names = FALSE)
    cat(sprintf("  Saved raw balance: %s\n", out_file))
  })

  # attrition 요약
  if (nrow(all_attrition) > 0) {
    att <- as.data.table(all_attrition)
    att_comp <- att[comparator_id == comp$comparator & analysis_id == 1]
    if (nrow(att_comp) > 0) {
      cat("\n  Attrition summary:\n")
      att_sum <- att_comp[, .(total_subjects = sum(subjects, na.rm = TRUE)), by = description]
      print(att_sum)
    }
  }
}

cat("\nDone.\n")
