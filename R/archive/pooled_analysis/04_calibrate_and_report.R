# ⚠️  DEPRECATED 2026-04-24 — 구형 4-step pipeline, R/lib/ipd_pooled.R 로 대체.
# Kept for reference only. See docs/system_knowledge_base.md §7.2.
# =============================================================================
# 04_calibrate_and_report.R
# Empirical calibration + Forest plot + 비교 테이블
# =============================================================================

source("00_config.R")

# -----------------------------------------------------------------------------
# 1. 결과 로드
# -----------------------------------------------------------------------------
loadAllResults <- function() {
  pooledFile <- file.path(outputFolder, "pooled_results_all.csv")
  metaFile <- file.path(outputFolder, "meta_results.csv")

  results <- data.frame()

  if (file.exists(pooledFile)) {
    pooled <- read.csv(pooledFile, stringsAsFactors = FALSE)
    results <- rbind(results, pooled)
  }

  if (file.exists(metaFile)) {
    meta <- read.csv(metaFile, stringsAsFactors = FALSE)
    # 컬럼 맞추기
    missingCols <- setdiff(colnames(results), colnames(meta))
    for (col in missingCols) meta[[col]] <- NA
    missingCols2 <- setdiff(colnames(meta), colnames(results))
    for (col in missingCols2) results[[col]] <- NA
    results <- rbind(results, meta[, colnames(results)])
  }

  if (nrow(results) == 0) stop("No results found. Run 02 and/or 03 first.")
  return(results)
}

# -----------------------------------------------------------------------------
# 2. Empirical Calibration
# -----------------------------------------------------------------------------
performCalibration <- function(results, strategyName) {
  stratResults <- results[results$strategy == strategyName, ]

  # NC 결과 분리
  ncResults <- stratResults[stratResults$outcomeId %in% negativeControlIds, ]
  ncValid <- ncResults[!is.na(ncResults$seLogRr) & ncResults$seLogRr > 0, ]

  if (nrow(ncValid) < 5) {
    message(sprintf("  [%s] Only %d valid NCs (need >=5). Skipping calibration.",
                    strategyName, nrow(ncValid)))
    stratResults$calibratedRr <- NA
    stratResults$calibratedCi95Lb <- NA
    stratResults$calibratedCi95Ub <- NA
    stratResults$calibratedP <- NA
    return(stratResults)
  }

  message(sprintf("  [%s] Calibrating with %d negative controls", strategyName, nrow(ncValid)))

  # Null distribution
  null <- EmpiricalCalibration::fitMcmcNull(
    logRr = ncValid$logRr,
    seLogRr = ncValid$seLogRr
  )

  # Calibrated p-value
  calP <- EmpiricalCalibration::calibrateP(
    null = null,
    logRr = stratResults$logRr,
    seLogRr = stratResults$seLogRr
  )
  stratResults$calibratedP <- calP$p

  # Calibrated CI
  model <- EmpiricalCalibration::convertNullToErrorModel(null)
  calCi <- EmpiricalCalibration::calibrateConfidenceInterval(
    logRr = stratResults$logRr,
    seLogRr = stratResults$seLogRr,
    model = model
  )
  stratResults$calibratedRr <- exp(calCi$logRr)
  stratResults$calibratedCi95Lb <- exp(calCi$logLb95Rr)
  stratResults$calibratedCi95Ub <- exp(calCi$logUb95Rr)

  # NC diagnostic plot
  tryCatch({
    ncPlotFile <- file.path(outputFolder, sprintf("nc_plot_%s.png", strategyName))
    png(ncPlotFile, width = 800, height = 600)
    EmpiricalCalibration::plotCalibrationEffect(
      logRrNegatives = ncValid$logRr,
      seLogRrNegatives = ncValid$seLogRr,
      title = sprintf("Negative Control Distribution (%s)", toupper(strategyName))
    )
    dev.off()
    message(sprintf("  NC plot saved: %s", ncPlotFile))
  }, error = function(e) {
    warning("NC plot failed: ", e$message)
  })

  return(stratResults)
}

# -----------------------------------------------------------------------------
# 3. Forest Plot
# -----------------------------------------------------------------------------
createForestPlot <- function(results, useCalibrated = FALSE, fileName = NULL) {
  # outcomes of interest만
  ooi <- results[results$outcomeId %in% outcomeIds, ]
  ooi$outcomeName <- outcomeNames[as.character(ooi$outcomeId)]

  if (useCalibrated && "calibratedRr" %in% colnames(ooi)) {
    ooi$hr <- ifelse(!is.na(ooi$calibratedRr), ooi$calibratedRr, ooi$rr)
    ooi$lb <- ifelse(!is.na(ooi$calibratedCi95Lb), ooi$calibratedCi95Lb, ooi$ci95Lb)
    ooi$ub <- ifelse(!is.na(ooi$calibratedCi95Ub), ooi$calibratedCi95Ub, ooi$ci95Ub)
    titleSuffix <- "(Calibrated)"
  } else {
    ooi$hr <- ooi$rr
    ooi$lb <- ooi$ci95Lb
    ooi$ub <- ooi$ci95Ub
    titleSuffix <- "(Uncalibrated)"
  }

  # NA 제거
  ooi <- ooi[!is.na(ooi$hr), ]

  if (nrow(ooi) == 0) {
    message("No estimable outcomes for forest plot.")
    return(NULL)
  }

  # strategy 라벨
  strategyLabels <- c(
    iptw = "IPTW",
    strat = "Stratification",
    match = "Matching",
    meta = "Meta-analysis"
  )
  ooi$strategyLabel <- strategyLabels[ooi$strategy]
  ooi$strategyLabel[is.na(ooi$strategyLabel)] <- ooi$strategy[is.na(ooi$strategyLabel)]

  p <- ggplot(ooi, aes(x = hr, y = reorder(outcomeName, -as.numeric(factor(outcomeName))),
                        color = strategyLabel, shape = strategyLabel)) +
    geom_point(position = position_dodge(width = 0.5), size = 3) +
    geom_errorbarh(aes(xmin = lb, xmax = ub),
                   position = position_dodge(width = 0.5), height = 0.2) +
    geom_vline(xintercept = 1, linetype = "dashed", color = "grey50") +
    scale_x_log10("Hazard Ratio (95% CI)", breaks = c(0.1, 0.25, 0.5, 1, 2, 4, 10)) +
    labs(y = "",
         color = "Method", shape = "Method",
         title = paste("Appendectomy vs Cholecystectomy", titleSuffix)) +
    theme_minimal(base_size = 12) +
    theme(
      legend.position = "bottom",
      panel.grid.minor = element_blank()
    )

  if (!is.null(fileName)) {
    ggsave(fileName, p, width = 12, height = max(4, length(unique(ooi$outcomeName)) * 0.8 + 2))
    message(sprintf("Forest plot saved: %s", fileName))
  }

  return(p)
}

# -----------------------------------------------------------------------------
# 4. Summary Table
# -----------------------------------------------------------------------------
createSummaryTable <- function(results) {
  ooi <- results[results$outcomeId %in% outcomeIds, ]
  ooi$outcomeName <- outcomeNames[as.character(ooi$outcomeId)]

  hasCalibrated <- "calibratedRr" %in% colnames(ooi)

  summaryRows <- list()
  for (i in seq_len(nrow(ooi))) {
    row <- ooi[i, ]
    entry <- data.frame(
      Outcome = row$outcomeName,
      Strategy = toupper(row$strategy),
      HR = if (!is.na(row$rr)) sprintf("%.2f", row$rr) else "NA",
      CI_95 = if (!is.na(row$ci95Lb)) sprintf("(%.2f-%.2f)", row$ci95Lb, row$ci95Ub) else "NA",
      P = if (!is.na(row$p)) sprintf("%.4f", row$p) else "NA",
      stringsAsFactors = FALSE
    )
    if (hasCalibrated) {
      entry$Cal_HR <- if (!is.na(row$calibratedRr)) sprintf("%.2f", row$calibratedRr) else "NA"
      entry$Cal_CI_95 <- if (!is.na(row$calibratedCi95Lb)) {
        sprintf("(%.2f-%.2f)", row$calibratedCi95Lb, row$calibratedCi95Ub)
      } else "NA"
      entry$Cal_P <- if (!is.na(row$calibratedP)) sprintf("%.4f", row$calibratedP) else "NA"
    }
    if ("targetOutcomes" %in% colnames(row)) {
      entry$T_Events <- row$targetOutcomes
      entry$C_Events <- row$comparatorOutcomes
    }
    summaryRows[[i]] <- entry
  }

  summaryTable <- do.call(rbind, summaryRows)
  summaryTable <- summaryTable[order(summaryTable$Outcome, summaryTable$Strategy), ]

  return(summaryTable)
}

# -----------------------------------------------------------------------------
# 5. PS 분포 플롯
# -----------------------------------------------------------------------------
plotPsDistribution <- function() {
  psFile <- file.path(outputFolder, "ps_distribution.csv")
  if (!file.exists(psFile)) {
    message("No PS distribution file found.")
    return(NULL)
  }

  psDist <- read.csv(psFile)
  psDist$group <- ifelse(psDist$treatment == 1, "Appendectomy", "Cholecystectomy")

  p <- ggplot(psDist, aes(x = preferenceScore, fill = group)) +
    geom_density(alpha = 0.5) +
    geom_vline(xintercept = c(0.3, 0.7), linetype = "dashed", color = "grey50") +
    scale_x_continuous("Preference Score", limits = c(0, 1)) +
    labs(fill = "Group", title = "Propensity Score Distribution (Pooled)") +
    theme_minimal(base_size = 12) +
    theme(legend.position = "bottom")

  fileName <- file.path(outputFolder, "ps_distribution_plot.png")
  ggsave(fileName, p, width = 8, height = 5)
  message(sprintf("PS distribution plot saved: %s", fileName))
  return(p)
}

# -----------------------------------------------------------------------------
# 6. 전체 실행
# -----------------------------------------------------------------------------
runCalibrateAndReport <- function() {
  message("=== Loading all results ===")
  allResults <- loadAllResults()

  strategies <- unique(allResults$strategy)
  message(sprintf("Found strategies: %s", paste(strategies, collapse = ", ")))

  # Calibration (전략별)
  message("\n=== Empirical Calibration ===")
  calibratedResults <- data.frame()
  for (strat in strategies) {
    calResults <- performCalibration(allResults, strat)
    calibratedResults <- rbind(calibratedResults, calResults)
  }

  # 저장
  write.csv(calibratedResults,
            file.path(outputFolder, "calibrated_results_all.csv"),
            row.names = FALSE)

  # Forest plots
  message("\n=== Creating Forest Plots ===")
  createForestPlot(calibratedResults, useCalibrated = FALSE,
                   fileName = file.path(outputFolder, "forest_uncalibrated.png"))
  createForestPlot(calibratedResults, useCalibrated = TRUE,
                   fileName = file.path(outputFolder, "forest_calibrated.png"))

  # Summary table
  message("\n=== Creating Summary Table ===")
  summaryTable <- createSummaryTable(calibratedResults)
  write.csv(summaryTable,
            file.path(outputFolder, "summary_table.csv"),
            row.names = FALSE)
  message(sprintf("Summary table saved: %s", file.path(outputFolder, "summary_table.csv")))

  # PS distribution
  message("\n=== PS Distribution ===")
  plotPsDistribution()

  # 최종 요약 출력
  message("\n========================================")
  message("        FINAL SUMMARY")
  message("========================================")
  ooiResults <- calibratedResults[calibratedResults$outcomeId %in% outcomeIds, ]
  for (strat in strategies) {
    stratOoi <- ooiResults[ooiResults$strategy == strat, ]
    nEstimable <- sum(!is.na(stratOoi$rr))
    message(sprintf("\n[%s] %d/%d outcomes with HR:", toupper(strat), nEstimable, length(outcomeIds)))
    for (j in seq_len(nrow(stratOoi))) {
      r <- stratOoi[j, ]
      name <- outcomeNames[as.character(r$outcomeId)]
      if (!is.na(r$rr)) {
        hrStr <- sprintf("HR=%.2f (%.2f-%.2f) p=%.4f", r$rr, r$ci95Lb, r$ci95Ub, r$p)
        calStr <- if (!is.na(r$calibratedP)) sprintf(" | cal.p=%.4f", r$calibratedP) else ""
        message(sprintf("  %s: %s%s", name, hrStr, calStr))
      } else {
        message(sprintf("  %s: NA", name))
      }
    }
  }

  message("\n=== Report Complete ===")
  message(sprintf("All outputs in: %s", outputFolder))
}

# =============================================================================
# 실행
# =============================================================================
runCalibrateAndReport()
