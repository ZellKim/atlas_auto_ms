Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")

library(EmpiricalCalibration)

BASE_DIR <- "C:/Users/data1/Desktop/atlas_auto_cmdata"
OUTPUT_DIR <- file.path(BASE_DIR, "calibration_results")
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

# NC 결과 로드
nc <- read.csv(file.path(BASE_DIR, "pooled_10sites_nc", "ipd_10sites_nc_results.csv"),
               stringsAsFactors = FALSE)

# Clinical outcome 결과 로드
clinical_raw <- read.csv(file.path(BASE_DIR, "pooled_10sites_v7b",
                               "ipd_10sites_results.csv"),
                     stringsAsFactors = FALSE)
clinical <- clinical_raw[clinical_raw$time_window == "1_3650d", ]

# Biomarker outcome 결과 로드
biomarker_raw <- read.csv(file.path(BASE_DIR, "pooled_10sites_bio",
                                "ipd_10sites_results.csv"),
                      stringsAsFactors = FALSE)
biomarker <- biomarker_raw[biomarker_raw$time_window == "1_3650d", ]

# Time-window 결과는 10-site 전용 없음 — skip

comp_ids <- c(1074, 1076, 1121)
comp_names <- c("1074" = "vs_Chol", "1076" = "vs_GenPop", "1121" = "vs_Hernia")

all_calibrated <- data.frame()

for (cid in comp_ids) {
  cname <- comp_names[as.character(cid)]
  cat(sprintf("\n========== %s ==========\n", cname))

  # NC for this comparison - valid HRs only
  nc_comp <- nc[nc$comparator_id == cid & !is.na(nc$hr) & nc$hr > 0 & nc$hr < 100, ]

  if (nrow(nc_comp) < 5) {
    cat(sprintf("  Insufficient NCs: %d\n", nrow(nc_comp)))
    next
  }

  nc_logRr <- log(nc_comp$hr)
  nc_seLogRr <- (log(nc_comp$ci_upper) - log(nc_comp$ci_lower)) / (2 * 1.96)

  # Fit null distribution
  cat(sprintf("  Fitting null distribution with %d NCs...\n", length(nc_logRr)))
  null <- tryCatch(
    fitNull(nc_logRr, nc_seLogRr),
    error = function(e) { cat(sprintf("  fitNull failed: %s\n", e$message)); NULL }
  )

  if (is.null(null)) next

  cat(sprintf("  Null: mean=%.4f, SD=%.4f\n", null[1], null[2]))

  # Calibrate clinical outcomes
  clin_comp <- clinical[clinical$comparator_id == cid & !is.na(clinical$hr) & clinical$hr > 0, ]
  if (nrow(clin_comp) > 0) {
    cat(sprintf("\n  --- Clinical Outcomes (%d) ---\n", nrow(clin_comp)))
    for (i in seq_len(nrow(clin_comp))) {
      r <- clin_comp[i, ]
      logRr <- log(r$hr)
      seLogRr <- (log(r$ci_upper) - log(r$ci_lower)) / (2 * 1.96)

      calP <- calibrateP(null, logRr, seLogRr)
      calCi <- tryCatch(
        calibrateConfidenceInterval(logRr, seLogRr, null),
        error = function(e) c(NA, NA, NA)
      )

      calCiLo <- if (!is.na(calCi[2])) exp(calCi[2]) else NA
      calCiHi <- if (!is.na(calCi[3])) exp(calCi[3]) else NA

      sig_orig <- ifelse(r$p_value < 0.05, "*", "")
      sig_cal <- ifelse(!is.na(calP) && calP < 0.05, "*", "")

      cat(sprintf("  %-25s HR=%.3f p=%.4f%s -> calP=%.4f%s\n",
                  r$outcome_name, r$hr, r$p_value, sig_orig,
                  calP, sig_cal))

      row <- data.frame(
        study = "v7b", comparison = cname,
        outcome_name = r$outcome_name, outcome_id = r$outcome_id,
        hr = r$hr, ci_lower = r$ci_lower, ci_upper = r$ci_upper,
        p_value = r$p_value,
        cal_p = round(calP, 6),
        cal_ci_lower = round(calCiLo, 4),
        cal_ci_upper = round(calCiHi, 4),
        stringsAsFactors = FALSE
      )
      all_calibrated <- rbind(all_calibrated, row)
    }
  }

  # Calibrate biomarker outcomes
  bio_comp <- biomarker[biomarker$comparator_id == cid & !is.na(biomarker$hr) & biomarker$hr > 0, ]
  if (nrow(bio_comp) > 0) {
    cat(sprintf("\n  --- Biomarker Outcomes (%d) ---\n", nrow(bio_comp)))
    for (i in seq_len(nrow(bio_comp))) {
      r <- bio_comp[i, ]
      logRr <- log(r$hr)
      seLogRr <- (log(r$ci_upper) - log(r$ci_lower)) / (2 * 1.96)

      calP <- calibrateP(null, logRr, seLogRr)
      calCi <- tryCatch(
        calibrateConfidenceInterval(logRr, seLogRr, null),
        error = function(e) c(NA, NA, NA)
      )

      calCiLo <- if (!is.na(calCi[2])) exp(calCi[2]) else NA
      calCiHi <- if (!is.na(calCi[3])) exp(calCi[3]) else NA

      sig_orig <- ifelse(r$p_value < 0.05, "*", "")
      sig_cal <- ifelse(!is.na(calP) && calP < 0.05, "*", "")

      cat(sprintf("  %-25s HR=%.3f p=%.4f%s -> calP=%.4f%s\n",
                  r$outcome_name, r$hr, r$p_value, sig_orig,
                  calP, sig_cal))

      row <- data.frame(
        study = "biomarker", comparison = cname,
        outcome_name = r$outcome_name, outcome_id = r$outcome_id,
        hr = r$hr, ci_lower = r$ci_lower, ci_upper = r$ci_upper,
        p_value = r$p_value,
        cal_p = round(calP, 6),
        cal_ci_lower = round(calCiLo, 4),
        cal_ci_upper = round(calCiHi, 4),
        stringsAsFactors = FALSE
      )
      all_calibrated <- rbind(all_calibrated, row)
    }
  }
}

# Save
out_path <- file.path(OUTPUT_DIR, "calibrated_10sites.csv")
write.csv(all_calibrated, out_path, row.names = FALSE)
cat(sprintf("\n\nSaved: %s (%d results)\n", out_path, nrow(all_calibrated)))

# Summary: what changed
cat("\n=== Calibration Impact ===\n")
if (nrow(all_calibrated) > 0) {
  was_sig <- all_calibrated$p_value < 0.05
  still_sig <- all_calibrated$cal_p < 0.05
  cat(sprintf("  Originally significant: %d\n", sum(was_sig, na.rm=TRUE)))
  cat(sprintf("  Still significant after calibration: %d\n", sum(was_sig & still_sig, na.rm=TRUE)))
  cat(sprintf("  Lost significance: %d\n", sum(was_sig & !still_sig, na.rm=TRUE)))
  cat(sprintf("  Gained significance: %d\n", sum(!was_sig & still_sig, na.rm=TRUE)))
}
