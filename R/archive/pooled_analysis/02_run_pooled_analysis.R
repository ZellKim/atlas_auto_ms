# ⚠️  DEPRECATED 2026-04-24 — 구형 4-step pipeline, R/lib/ipd_pooled.R 로 대체.
# Kept for reference only. See docs/system_knowledge_base.md §7.2.
# =============================================================================
# 02_run_pooled_analysis.R
# Pooled CmData에서 PS 재추정 → IPTW/Stratification/Matching → Cox regression
# =============================================================================

source("00_config.R")

# -----------------------------------------------------------------------------
# 1. Pooled CmData 로드
# -----------------------------------------------------------------------------
loadPooledData <- function() {
  pooledPath <- file.path(outputFolder, "CmData_pooled.zip")
  if (!file.exists(pooledPath)) {
    stop("Pooled CmData not found. Run 01_pool_cmdata.R first.")
  }
  cmData <- CohortMethod::loadCohortMethodData(pooledPath)
  siteMappings <- read.csv(file.path(outputFolder, "siteMappings.csv"),
                           stringsAsFactors = FALSE)
  return(list(cmData = cmData, siteMappings = siteMappings))
}

# -----------------------------------------------------------------------------
# 2. PS 추정 (pooled 전체에서 1회)
# -----------------------------------------------------------------------------
estimatePooledPs <- function(cmData) {
  psFile <- file.path(outputFolder, "ps_pooled.rds")

  if (file.exists(psFile)) {
    message("Loading existing PS from: ", psFile)
    return(readRDS(psFile))
  }

  message("Estimating propensity scores on pooled data...")
  ps <- CohortMethod::createPs(
    cohortMethodData = cmData,
    createPsArgs = CohortMethod::createCreatePsArgs(
      excludeCovariateIds = c(),
      maxCohortSizeForFitting = 500000,
      errorOnHighCorrelation = FALSE,
      stopOnError = FALSE,
      prior = Cyclops::createPrior("laplace",
                                   useCrossValidation = TRUE),
      control = Cyclops::createControl(
        noiseLevel = "silent",
        cvType = "auto",
        tolerance = 2e-7,
        maxIterations = 1000,
        cvRepetitions = 10
      )
    )
  )

  # PS 수렴 확인
  psError <- attr(ps, "metaData")$psError
  if (!is.null(psError) && psError != "") {
    warning("PS model error: ", psError)
  } else {
    message("PS model converged successfully.")
  }

  saveRDS(ps, psFile)
  message(sprintf("PS saved. N=%d, mean PS (T)=%.3f, mean PS (C)=%.3f",
                  nrow(ps),
                  mean(ps$propensityScore[ps$treatment == 1]),
                  mean(ps$propensityScore[ps$treatment == 0])))
  return(ps)
}

# -----------------------------------------------------------------------------
# 3. siteId 매핑 테이블 (cohorts에서 추출)
# -----------------------------------------------------------------------------
getSiteMap <- function(cmData) {
  cohorts <- cmData$cohorts %>% collect()
  siteMap <- cohorts[, c("rowId", "siteId")]
  return(siteMap)
}

# -----------------------------------------------------------------------------
# 4. 단일 outcome에 대한 분석 실행
# -----------------------------------------------------------------------------
runOutcomeAnalysis <- function(outcomeId, cmData, ps, siteMap,
                                strategy, strategyName, outputSubFolder) {
  # Study population 생성
  studyPop <- tryCatch({
    CohortMethod::createStudyPopulation(
      cohortMethodData = cmData,
      population = ps,
      outcomeId = outcomeId,
      createStudyPopulationArgs = CohortMethod::createCreateStudyPopulationArgs(
        riskWindowStart = riskWindowStart,
        riskWindowEnd = riskWindowEnd,
        minDaysAtRisk = minDaysAtRisk,
        removeSubjectsWithPriorOutcome = removeSubjectsWithPriorOutcome,
        priorOutcomeLookback = priorOutcomeLookback,
        addExposureDaysToStart = FALSE,
        addExposureDaysToEnd = FALSE
      )
    )
  }, error = function(e) {
    warning(sprintf("  [%s] createStudyPopulation failed for o=%d: %s",
                    strategyName, outcomeId, e$message))
    return(NULL)
  })

  if (is.null(studyPop) || nrow(studyPop) == 0) return(NULL)

  # 이벤트 수 확인
  nEvents <- sum(studyPop$outcomeCount > 0)
  if (nEvents == 0) return(NULL)

  # 전략별 처리
  adjustedPop <- tryCatch({
    strategy(studyPop, cmData, siteMap)
  }, error = function(e) {
    warning(sprintf("  [%s] adjustment failed for o=%d: %s",
                    strategyName, outcomeId, e$message))
    return(NULL)
  })

  if (is.null(adjustedPop) || nrow(adjustedPop) == 0) return(NULL)

  # Outcome model
  om <- tryCatch({
    fitArgs <- if (strategyName == "iptw") {
      CohortMethod::createFitOutcomeModelArgs(
        modelType = "cox",
        stratified = TRUE,
        useCovariates = FALSE,
        inversePtWeighting = TRUE
      )
    } else {
      CohortMethod::createFitOutcomeModelArgs(
        modelType = "cox",
        stratified = TRUE,
        useCovariates = TRUE,
        inversePtWeighting = FALSE,
        prior = Cyclops::createPrior("laplace", useCrossValidation = TRUE),
        control = Cyclops::createControl(noiseLevel = "quiet")
      )
    }

    CohortMethod::fitOutcomeModel(
      population = adjustedPop,
      cohortMethodData = cmData,
      fitOutcomeModelArgs = fitArgs
    )
  }, error = function(e) {
    warning(sprintf("  [%s] fitOutcomeModel failed for o=%d: %s",
                    strategyName, outcomeId, e$message))
    return(NULL)
  })

  if (is.null(om)) return(NULL)

  # 결과 저장
  omFile <- file.path(outputSubFolder, sprintf("om_%s_o%d.rds", strategyName, outcomeId))
  saveRDS(om, omFile)

  return(om)
}

# -----------------------------------------------------------------------------
# 5. 보정 전략 정의
# -----------------------------------------------------------------------------

# Strategy A: IPTW + 사이트 층화
strategyIptw <- function(studyPop, cmData, siteMap) {
  pop <- merge(studyPop, siteMap, by = "rowId", all.x = TRUE)
  pop$stratumId <- pop$siteId
  return(pop)
}

# Strategy B: PS Stratification + 사이트 교차 층화
strategyStratification <- function(studyPop, cmData, siteMap) {
  stratPop <- CohortMethod::stratifyByPs(
    population = studyPop,
    stratifyByPsArgs = CohortMethod::createStratifyByPsArgs(
      numberOfStrata = 5,
      baseSelection = "all"
    )
  )
  stratPop <- merge(stratPop, siteMap, by = "rowId", all.x = TRUE)
  # 교차 층화: (siteId - 1) * 5 + psStratumId
  stratPop$stratumId <- (stratPop$siteId - 1) * 5 + stratPop$stratumId
  return(stratPop)
}

# Strategy C: PS Matching
strategyMatching <- function(studyPop, cmData, siteMap) {
  matchPop <- CohortMethod::matchOnPs(
    population = studyPop,
    matchOnPsArgs = CohortMethod::createMatchOnPsArgs(
      caliper = 0.2,
      caliperScale = "standardized logit",
      maxRatio = 1
    )
  )
  return(matchPop)
}

# -----------------------------------------------------------------------------
# 6. 결과 수집
# -----------------------------------------------------------------------------
collectResults <- function(outputSubFolder, strategyName, outcomeIds) {
  results <- data.frame()

  for (oid in outcomeIds) {
    omFile <- file.path(outputSubFolder, sprintf("om_%s_o%d.rds", strategyName, oid))

    if (!file.exists(omFile)) {
      row <- data.frame(
        outcomeId = oid, rr = NA, ci95Lb = NA, ci95Ub = NA,
        logRr = NA, seLogRr = NA, p = NA,
        targetSubjects = NA, comparatorSubjects = NA,
        targetOutcomes = NA, comparatorOutcomes = NA,
        strategy = strategyName, stringsAsFactors = FALSE
      )
    } else {
      om <- readRDS(omFile)

      # outcomeModel 객체에서 결과 추출
      logRr <- tryCatch(coef(om), error = function(e) NA)
      ci <- tryCatch(confint(om), error = function(e) c(NA, NA))
      seLogRr <- tryCatch({
        (ci[2] - ci[1]) / (2 * qnorm(0.975))
      }, error = function(e) NA)

      # population에서 이벤트 수 추출
      pop <- om$population
      if (is.null(pop)) pop <- data.frame(treatment = integer(), outcomeCount = integer())

      row <- data.frame(
        outcomeId = oid,
        rr = if (!is.na(logRr)) exp(logRr) else NA,
        ci95Lb = if (!is.na(ci[1])) exp(ci[1]) else NA,
        ci95Ub = if (!is.na(ci[2])) exp(ci[2]) else NA,
        logRr = logRr,
        seLogRr = seLogRr,
        p = tryCatch(2 * pnorm(-abs(logRr / seLogRr)), error = function(e) NA),
        targetSubjects = sum(pop$treatment == 1),
        comparatorSubjects = sum(pop$treatment == 0),
        targetOutcomes = sum(pop$outcomeCount[pop$treatment == 1] > 0),
        comparatorOutcomes = sum(pop$outcomeCount[pop$treatment == 0] > 0),
        strategy = strategyName,
        stringsAsFactors = FALSE
      )
    }
    results <- rbind(results, row)
  }
  return(results)
}

# -----------------------------------------------------------------------------
# 7. 전체 실행
# -----------------------------------------------------------------------------
runPooledAnalysis <- function() {
  data <- loadPooledData()
  cmData <- data$cmData
  siteMappings <- data$siteMappings
  siteMap <- getSiteMap(cmData)

  # PS 추정
  ps <- estimatePooledPs(cmData)

  # PS 분포 저장
  psDist <- data.frame(
    propensityScore = ps$propensityScore,
    preferenceScore = ps$preferenceScore,
    treatment = ps$treatment
  )
  write.csv(psDist, file.path(outputFolder, "ps_distribution.csv"), row.names = FALSE)

  # 전략별 실행
  strategies <- list(
    list(name = "iptw", fn = strategyIptw),
    list(name = "strat", fn = strategyStratification),
    list(name = "match", fn = strategyMatching)
  )

  allResults <- data.frame()

  for (strat in strategies) {
    stratFolder <- file.path(outputFolder, strat$name)
    if (!dir.exists(stratFolder)) dir.create(stratFolder, recursive = TRUE)

    message(sprintf("\n=== Running Strategy: %s ===", toupper(strat$name)))

    for (oid in allOutcomeIds) {
      isOOI <- oid %in% outcomeIds
      label <- if (isOOI) outcomeNames[as.character(oid)] else paste0("NC_", oid)
      message(sprintf("  Processing: %s (id=%d)", label, oid))

      runOutcomeAnalysis(
        outcomeId = oid,
        cmData = cmData,
        ps = ps,
        siteMap = siteMap,
        strategy = strat$fn,
        strategyName = strat$name,
        outputSubFolder = stratFolder
      )
    }

    # 결과 수집
    stratResults <- collectResults(stratFolder, strat$name, allOutcomeIds)
    allResults <- rbind(allResults, stratResults)

    # 전략별 요약
    ooi <- stratResults[stratResults$outcomeId %in% outcomeIds, ]
    nEstimable <- sum(!is.na(ooi$rr))
    message(sprintf("  [%s] %d/%d outcomes with estimable HR",
                    strat$name, nEstimable, length(outcomeIds)))
  }

  # 전체 결과 저장
  write.csv(allResults, file.path(outputFolder, "pooled_results_all.csv"), row.names = FALSE)
  message(sprintf("\nAll results saved: %s", file.path(outputFolder, "pooled_results_all.csv")))

  # Covariate balance (IPTW primary)
  message("\nComputing covariate balance for IPTW strategy...")
  tryCatch({
    iptwPop <- merge(ps, siteMap, by = "rowId", all.x = TRUE)
    iptwPop$stratumId <- iptwPop$siteId
    balance <- CohortMethod::computeCovariateBalance(
      population = iptwPop,
      cohortMethodData = cmData
    )
    saveRDS(balance, file.path(outputFolder, "covariateBalance_iptw.rds"))
    maxSmd <- max(abs(balance$afterMatchingStdDiff), na.rm = TRUE)
    message(sprintf("  Max absolute SMD after IPTW: %.4f", maxSmd))
  }, error = function(e) {
    warning("Covariate balance computation failed: ", e$message)
  })

  Andromeda::close(cmData)
  message("\n=== Pooled Analysis Complete ===")
}

# =============================================================================
# 실행
# =============================================================================
runPooledAnalysis()
