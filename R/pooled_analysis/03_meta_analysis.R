# =============================================================================
# 03_meta_analysis.R
# 메타분석 — 가능한 outcome/사이트에 대해서만 수행 (Secondary)
# BayesianNonNormal (likelihood profile 기반) 또는 DL
# =============================================================================

source("00_config.R")

# -----------------------------------------------------------------------------
# 1. 각 사이트의 export 결과 로드
# -----------------------------------------------------------------------------
loadSiteResults <- function(resultFolder, siteName) {
  exportFolder <- file.path(resultFolder, "export")

  # cohort_method_result.csv
  resultFile <- file.path(exportFolder, "cohort_method_result.csv")
  if (!file.exists(resultFile)) {
    warning(sprintf("No cohort_method_result.csv for %s", siteName))
    return(NULL)
  }

  results <- readr::read_csv(resultFile, col_types = readr::cols(), show_col_types = FALSE)
  colnames(results) <- SqlRender::snakeCaseToCamelCase(colnames(results))
  results$siteName <- siteName

  # likelihood_profile.csv
  profileFile <- file.path(exportFolder, "likelihood_profile.csv")
  profiles <- NULL
  if (file.exists(profileFile)) {
    profiles <- readr::read_csv(profileFile, col_types = readr::cols(), show_col_types = FALSE)
    colnames(profiles) <- SqlRender::snakeCaseToCamelCase(colnames(profiles))
    profiles$siteName <- siteName
  }

  # negative_control_outcome.csv
  ncFile <- file.path(exportFolder, "negative_control_outcome.csv")
  ncs <- NULL
  if (file.exists(ncFile)) {
    ncs <- readr::read_csv(ncFile, col_types = readr::cols(), show_col_types = FALSE)
    colnames(ncs) <- SqlRender::snakeCaseToCamelCase(colnames(ncs))
  }

  return(list(results = results, profiles = profiles, ncs = ncs))
}

# -----------------------------------------------------------------------------
# 2. 단일 outcome 메타분석
# -----------------------------------------------------------------------------
computeSingleMeta <- function(outcomeId, allResults, allProfiles, method = "BayesianNonNormal") {
  rows <- allResults[allResults$outcomeId == outcomeId, ]

  if (nrow(rows) == 0) return(NULL)

  # HR 산출 가능한 사이트
  validRows <- rows[!is.na(rows$seLogRr) & rows$seLogRr > 0, ]

  maRow <- rows[1, ]
  maRow$databaseId <- "Meta-analysis"
  maRow$siteName <- "Meta-analysis"

  # 합산 통계
  maRow$targetSubjects <- sum(abs(rows$targetSubjects), na.rm = TRUE)
  maRow$comparatorSubjects <- sum(abs(rows$comparatorSubjects), na.rm = TRUE)
  maRow$targetOutcomes <- sum(abs(rows$targetOutcomes), na.rm = TRUE)
  maRow$comparatorOutcomes <- sum(abs(rows$comparatorOutcomes), na.rm = TRUE)

  # 유효 사이트가 2개 미만이면 메타분석 불가
  if (nrow(validRows) < 2) {
    if (nrow(validRows) == 1) {
      # 1개 사이트만 있으면 그대로 반환
      maRow$rr <- validRows$rr[1]
      maRow$ci95Lb <- validRows$ci95Lb[1]
      maRow$ci95Ub <- validRows$ci95Ub[1]
      maRow$logRr <- validRows$logRr[1]
      maRow$seLogRr <- validRows$seLogRr[1]
      maRow$p <- validRows$p[1]
      maRow$nSitesWithHr <- 1
      maRow$metaMethod <- "single_site"
    } else {
      maRow$rr <- NA; maRow$ci95Lb <- NA; maRow$ci95Ub <- NA
      maRow$logRr <- NA; maRow$seLogRr <- NA; maRow$p <- NA
      maRow$nSitesWithHr <- 0
      maRow$metaMethod <- "none"
    }
    return(maRow)
  }

  maRow$nSitesWithHr <- nrow(validRows)

  # BayesianNonNormal 시도
  if (method == "BayesianNonNormal" && !is.null(allProfiles)) {
    profileRows <- allProfiles[allProfiles$outcomeId == outcomeId, ]
    profileSites <- unique(profileRows$siteName)

    if (length(profileSites) >= 2) {
      tryCatch({
        # likelihood profile을 행렬로 변환
        profiles <- profileRows[profileRows$siteName %in% profileSites, ]
        # profile 데이터를 사이트별로 분리하여 EvidenceSynthesis 형식으로 변환
        siteProfiles <- split(profiles, profiles$siteName)

        # 각 사이트의 profile을 grid 형태로 변환
        gridProfiles <- lapply(siteProfiles, function(sp) {
          sp <- sp[order(sp$logHazardRatio), ]
          ll <- sp$logLikelihood
          names(ll) <- sp$logHazardRatio
          return(ll)
        })

        # grid를 data.frame으로 변환 (1000 points)
        gridPoints <- seq(log(0.1), log(10), length.out = 1000)
        profileMatrix <- do.call(rbind, lapply(gridProfiles, function(ll) {
          origPoints <- as.numeric(names(ll))
          origValues <- as.numeric(ll)
          interpolated <- approx(origPoints, origValues, xout = gridPoints, rule = 2)$y
          return(interpolated)
        }))
        profileDf <- as.data.frame(profileMatrix)
        colnames(profileDf) <- as.character(gridPoints)

        estimate <- EvidenceSynthesis::computeBayesianMetaAnalysis(profileDf)

        maRow$rr <- exp(estimate$mu)
        maRow$ci95Lb <- exp(estimate$mu95Lb)
        maRow$ci95Ub <- exp(estimate$mu95Ub)
        maRow$logRr <- estimate$logRr
        maRow$seLogRr <- estimate$seLogRr
        maRow$p <- EmpiricalCalibration::computeTraditionalP(estimate$logRr, estimate$seLogRr)
        maRow$metaMethod <- "BayesianNonNormal"

        return(maRow)
      }, error = function(e) {
        message(sprintf("  BayesianNonNormal failed for o=%d, falling back to DL: %s",
                        outcomeId, e$message))
      })
    }
  }

  # DL (DerSimonian-Laird) fallback
  tryCatch({
    meta <- meta::metagen(
      TE = validRows$logRr,
      seTE = validRows$seLogRr,
      sm = "RR",
      hakn = FALSE
    )
    s <- summary(meta)
    rnd <- s$random
    maRow$rr <- exp(rnd$TE)
    maRow$ci95Lb <- exp(rnd$lower)
    maRow$ci95Ub <- exp(rnd$upper)
    maRow$p <- rnd$p
    maRow$logRr <- rnd$TE
    maRow$seLogRr <- rnd$seTE
    maRow$metaMethod <- "DL"
  }, error = function(e) {
    warning(sprintf("  DL meta-analysis also failed for o=%d: %s", outcomeId, e$message))
    maRow$rr <- NA; maRow$ci95Lb <- NA; maRow$ci95Ub <- NA
    maRow$logRr <- NA; maRow$seLogRr <- NA; maRow$p <- NA
    maRow$metaMethod <- "failed"
  })

  return(maRow)
}

# -----------------------------------------------------------------------------
# 3. 전체 메타분석 실행
# -----------------------------------------------------------------------------
runMetaAnalysis <- function() {
  message("=== Loading site-level results for meta-analysis ===")

  allResults <- list()
  allProfiles <- list()

  for (siteName in siteNames) {
    siteData <- loadSiteResults(resultFolders[[siteName]], siteName)
    if (!is.null(siteData)) {
      allResults[[siteName]] <- siteData$results
      if (!is.null(siteData$profiles)) {
        allProfiles[[siteName]] <- siteData$profiles
      }
    }
  }

  if (length(allResults) == 0) {
    stop("No site results found.")
  }

  combinedResults <- do.call(rbind, allResults)
  combinedProfiles <- if (length(allProfiles) > 0) do.call(rbind, allProfiles) else NULL

  message(sprintf("Loaded results from %d sites", length(allResults)))
  if (!is.null(combinedProfiles)) {
    message(sprintf("Likelihood profiles available from %d sites", length(allProfiles)))
  }

  # 사이트별 HR 산출 현황 요약
  message("\n--- Site-level HR availability ---")
  for (oid in outcomeIds) {
    rows <- combinedResults[combinedResults$outcomeId == oid, ]
    nValid <- sum(!is.na(rows$seLogRr) & rows$seLogRr > 0)
    label <- outcomeNames[as.character(oid)]
    message(sprintf("  %s: %d/%d sites with HR", label, nValid, nrow(rows)))
  }

  # Outcome별 메타분석
  message("\n=== Running meta-analysis ===")
  maResults <- list()

  for (oid in allOutcomeIds) {
    isOOI <- oid %in% outcomeIds
    label <- if (isOOI) outcomeNames[as.character(oid)] else paste0("NC_", oid)

    maRow <- computeSingleMeta(oid, combinedResults, combinedProfiles)
    if (!is.null(maRow)) {
      maResults[[length(maResults) + 1]] <- maRow
      if (isOOI) {
        hrStr <- if (!is.na(maRow$rr)) sprintf("%.2f (%.2f-%.2f)", maRow$rr, maRow$ci95Lb, maRow$ci95Ub) else "NA"
        message(sprintf("  %s: HR=%s [%s, %d sites]",
                        label, hrStr, maRow$metaMethod, maRow$nSitesWithHr))
      }
    }
  }

  metaResults <- do.call(rbind, lapply(maResults, function(x) {
    as.data.frame(x[c("outcomeId", "rr", "ci95Lb", "ci95Ub",
                       "logRr", "seLogRr", "p",
                       "targetSubjects", "comparatorSubjects",
                       "targetOutcomes", "comparatorOutcomes",
                       "nSitesWithHr", "metaMethod")],
                  stringsAsFactors = FALSE)
  }))
  metaResults$strategy <- "meta"

  # 저장
  write.csv(metaResults, file.path(outputFolder, "meta_results.csv"), row.names = FALSE)

  # 사이트별 개별 결과도 저장
  write.csv(combinedResults, file.path(outputFolder, "site_level_results.csv"), row.names = FALSE)

  message(sprintf("\nMeta-analysis results saved: %s",
                  file.path(outputFolder, "meta_results.csv")))
  message("=== Meta-Analysis Complete ===")

  return(metaResults)
}

# =============================================================================
# 실행
# =============================================================================
metaResults <- runMetaAnalysis()
