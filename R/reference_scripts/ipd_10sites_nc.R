# =============================================================================
# IPD Pooled Analysis - CohortMethod/Cyclops 기반 1:2 PS Matching
#
# 7개 기관 CmData를 통합하여:
#   1. Cyclops로 PS 적합 (Laplace prior, cross-validation)
#   2. 1:2 nearest-neighbor matching (caliper=0.2*SD(logit PS))
#   3. Site-stratified Cox regression
# =============================================================================

Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
library(CohortMethod)
library(Cyclops)
library(Andromeda)
library(survival)

# --- 설정 ---
BASE_DIR <- "C:/Users/data1/Desktop/atlas_auto_cmdata"
CMDATA_DIR <- file.path(BASE_DIR, "cmData_v7")
OUTPUT_DIR <- file.path(BASE_DIR, "pooled_10sites_nc")
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

SITES <- sort(list.dirs(CMDATA_DIR, recursive = FALSE, full.names = FALSE))
SITES <- SITES[!SITES %in% c("CAUHS_5.3.1_03", "DAEGU_DONGSAN_5.3.1_06", "ISH_5.3.1_05", "JCMJ_5.3.1_04", "SCHGM_5.3.3_03", "GNUCH_5.3.1_06")]

COMPARISONS <- list(
  list(target = 1072, comparator = 1074, name = "vs_Cholecystectomy"),
  list(target = 1072, comparator = 1076, name = "vs_General_Population"),
  list(target = 1072, comparator = 1121, name = "vs_Hernia_repair")
)

OUTCOME_IDS <- c(73008, 74855, 75354, 75911, 76786, 77965, 78619, 81378, 81878,
  133141, 133228, 134461, 136368, 139099, 140641, 140648, 192606, 196168, 200775,
  373478, 374375, 374923, 375552, 376707, 377572, 378424, 379805, 380038, 380094,
  381581, 436634, 438329, 441818, 443285, 444132, 4030042, 4033858, 4050747,
  4134455, 4156115, 4169984, 4170770, 4215978, 4254542, 4329707, 4344500,
  40481632, 40568467)
OUTCOME_NAMES <- setNames(paste0("NC_", OUTCOME_IDS), as.character(OUTCOME_IDS))

# --- 함수: SQLite에서 데이터 로드 및 통합 ---
loadAndPoolData <- function(targetId, comparatorId) {
  allCohorts <- data.frame()
  allOutcomes <- data.frame()
  allCovariates <- data.frame()
  allCovariateRef <- data.frame()
  allAnalysisRef <- data.frame()

  for (site in SITES) {
    cmName <- sprintf("CmData_l1_t%d_c%d", targetId, comparatorId)
    cmDir <- file.path(CMDATA_DIR, site, cmName)
    if (!dir.exists(cmDir)) next

    sqliteFiles <- list.files(cmDir, pattern = "\\.sqlite$", full.names = TRUE)
    if (length(sqliteFiles) == 0) next

    con <- DBI::dbConnect(RSQLite::SQLite(), sqliteFiles[1])

    cohorts <- DBI::dbReadTable(con, "cohorts")
    outcomes <- DBI::dbReadTable(con, "outcomes")
    covariates <- DBI::dbReadTable(con, "covariates")
    covariateRef <- DBI::dbReadTable(con, "covariateRef")
    analysisRef <- DBI::dbReadTable(con, "analysisRef")

    DBI::dbDisconnect(con)

    # site별 rowId 오프셋 (유니크하게)
    siteIdx <- which(SITES == site)
    offset <- (siteIdx - 1) * 10000000

    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$site <- site
    outcomes$rowId <- as.integer(outcomes$rowId) + offset
    covariates$rowId <- as.integer(covariates$rowId) + offset

    nT <- sum(cohorts$treatment == 1)
    nC <- sum(cohorts$treatment == 0)
    cat(sprintf("  %s: T=%d, C=%d\n", site, nT, nC))

    allCohorts <- rbind(allCohorts, cohorts)
    allOutcomes <- rbind(allOutcomes, outcomes)
    allCovariates <- rbind(allCovariates, covariates)
    allCovariateRef <- rbind(allCovariateRef, covariateRef)
    allAnalysisRef <- rbind(allAnalysisRef, analysisRef)
  }

  # 중복 covariateRef 제거
  allCovariateRef <- unique(allCovariateRef)
  allAnalysisRef <- unique(allAnalysisRef)

  # site dummy 공변량 추가
  siteLevels <- sort(unique(allCohorts$site))
  if (length(siteLevels) > 1) {
    maxCovId <- max(allCovariateRef$covariateId, na.rm = TRUE)
    siteRefs <- data.frame()
    siteCovs <- data.frame()

    for (i in 2:length(siteLevels)) {
      newCovId <- maxCovId + i
      s <- siteLevels[i]
      siteRows <- allCohorts[allCohorts$site == s, ]

      siteCovs <- rbind(siteCovs, data.frame(
        rowId = siteRows$rowId,
        covariateId = newCovId,
        covariateValue = 1
      ))
      siteRefs <- rbind(siteRefs, data.frame(
        covariateId = newCovId,
        covariateName = paste0("site: ", s),
        analysisId = 999,
        conceptId = 0
      ))
    }

    allCovariates <- rbind(allCovariates, siteCovs)
    allCovariateRef <- rbind(allCovariateRef, siteRefs)

    if (!"999" %in% as.character(allAnalysisRef$analysisId)) {
      allAnalysisRef <- rbind(allAnalysisRef, data.frame(
        analysisId = 999,
        analysisName = "Site",
        domainId = "Site",
        startDay = NA, endDay = NA,
        isBinary = "Y", missingMeansZero = "Y"
      ))
    }
  }

  return(list(
    cohorts = allCohorts,
    outcomes = allOutcomes,
    covariates = allCovariates,
    covariateRef = allCovariateRef,
    analysisRef = allAnalysisRef
  ))
}

# --- 함수: Cyclops PS 적합 ---
fitPsWithCyclops <- function(pooledData, maxComparatorForFit = 250000) {
  cohorts <- pooledData$cohorts
  covariates <- pooledData$covariates

  nTarget <- sum(cohorts$treatment == 1)
  nComp <- sum(cohorts$treatment == 0)

  # 대규모 comparator 서브샘플링
  if (nComp > maxComparatorForFit) {
    cat(sprintf("  Comparator 서브샘플링: %d -> %d\n", nComp, maxComparatorForFit))
    compRows <- cohorts$rowId[cohorts$treatment == 0]
    sampledComp <- sample(compRows, maxComparatorForFit)
    fitRowIds <- c(cohorts$rowId[cohorts$treatment == 1], sampledComp)
    fitCohorts <- cohorts[cohorts$rowId %in% fitRowIds, ]
    fitCovariates <- covariates[covariates$rowId %in% fitRowIds, ]
  } else {
    fitCohorts <- cohorts
    fitCovariates <- covariates
  }

  # sparse matrix 준비
  rowIds <- fitCohorts$rowId
  y <- fitCohorts$treatment

  rowIdMap <- setNames(seq_along(rowIds), as.character(rowIds))

  validCovs <- fitCovariates[as.character(fitCovariates$rowId) %in% names(rowIdMap), ]
  rowIdx <- rowIdMap[as.character(validCovs$rowId)]

  covIds <- sort(unique(validCovs$covariateId))
  covIdMap <- setNames(seq_along(covIds), as.character(covIds))
  colIdx <- covIdMap[as.character(validCovs$covariateId)]

  nRows <- length(rowIds)
  nCols <- length(covIds)

  cat(sprintf("  Cyclops 데이터 준비: %d patients x %d covariates\n", nRows, nCols))

  # convertToCyclopsData (long format)
  outcomes <- data.frame(rowId = rowIds, y = y)
  covLong <- data.frame(
    rowId = validCovs$rowId,
    covariateId = validCovs$covariateId,
    covariateValue = validCovs$covariateValue
  )

  cat("  Cyclops fitting (Laplace prior, cross-validation)...\n")
  t0 <- proc.time()

  cyclopsData <- Cyclops::convertToCyclopsData(
    outcomes = outcomes,
    covariates = covLong,
    modelType = "lr",
    addIntercept = TRUE
  )

  prior <- Cyclops::createPrior(
    "laplace",
    useCrossValidation = TRUE,
    variance = 1,
    exclude = 0,
    forceIntercept = FALSE
  )

  control <- Cyclops::createControl(
    maxIterations = 1000,
    tolerance = 2e-7,
    convergenceType = "gradient",
    cvType = "auto",
    fold = 10,
    lowerLimit = 0.01,
    upperLimit = 20,
    seed = 42,
    noiseLevel = "quiet"
  )

  fit <- Cyclops::fitCyclopsModel(cyclopsData, prior = prior, control = control)

  elapsed <- (proc.time() - t0)[3]
  cat(sprintf("  Cyclops 완료: %.1f초\n", elapsed))

  # PS 예측
  predictions <- predict(fit, type = "response")
  fitCohorts$ps <- predictions

  # 서브샘플링 한 경우: 매칭 대상에 PS 적용
  if (nComp > maxComparatorForFit) {
    cat("  매칭 대상 PS 예측 중...\n")
    matchCohorts <- rbind(
      cohorts[cohorts$treatment == 1, ],
      cohorts[cohorts$rowId %in% sampledComp, ]
    )
    matchCovs <- covariates[covariates$rowId %in% matchCohorts$rowId, ]
    # 학습에 사용한 공변량만 유지
    matchCovs <- matchCovs[matchCovs$covariateId %in% covIds, ]

    matchOutcomes <- data.frame(rowId = matchCohorts$rowId, y = matchCohorts$treatment)
    matchCovLong <- data.frame(
      rowId = matchCovs$rowId,
      covariateId = matchCovs$covariateId,
      covariateValue = matchCovs$covariateValue
    )

    matchCyclops <- Cyclops::convertToCyclopsData(
      outcomes = matchOutcomes,
      covariates = matchCovLong,
      modelType = "lr",
      addIntercept = TRUE
    )

    matchPs <- predict(fit, newCyclopsData = matchCyclops, type = "response")
    matchCohorts$ps <- matchPs
    cat(sprintf("  완료 (%s명)\n", format(nrow(matchCohorts), big.mark = ",")))

    return(list(cohorts = matchCohorts, model = fit, covIdMap = covIdMap))
  }

  return(list(cohorts = fitCohorts, model = fit, covIdMap = covIdMap))
}

# --- 함수: 1:2 PS Matching ---
matchPairs <- function(psCohorts, nMatches = 1, caliper = 0.2) {
  psCohorts$logitPs <- log(pmax(psCohorts$ps, 1e-8) / pmax(1 - psCohorts$ps, 1e-8))

  sdLogit <- sd(psCohorts$logitPs)
  caliperVal <- caliper * sdLogit
  cat(sprintf("  Caliper: %.2f x SD(%.4f) = %.4f\n", caliper, sdLogit, caliperVal))

  targets <- psCohorts[psCohorts$treatment == 1, ]
  comparators <- psCohorts[psCohorts$treatment == 0, ]

  # 소수군 기준 매칭
  if (nrow(targets) <= nrow(comparators)) {
    anchor <- targets
    pool <- comparators
    anchorLabel <- "Target"
    reversed <- FALSE
  } else {
    anchor <- comparators
    pool <- targets
    anchorLabel <- "Comparator"
    reversed <- TRUE
    cat(sprintf("  ** T(%d) > C(%d): Comparator 기준 매칭으로 전환 **\n",
                nrow(targets), nrow(comparators)))
  }

  cat(sprintf("  매칭: %d %s x %d from %d pool...\n",
              nrow(anchor), anchorLabel, nMatches, nrow(pool)))

  # 랜덤 순서
  set.seed(42)
  anchorOrder <- sample(nrow(anchor))

  matchedAnchorIdx <- c()
  matchedPoolIdx <- c()
  usedPool <- logical(nrow(pool))

  poolLogit <- pool$logitPs

  for (ai in anchorOrder) {
    aLogit <- anchor$logitPs[ai]
    dists <- abs(poolLogit - aLogit)

    # caliper 내 & 미사용 후보
    candidates <- which(dists <= caliperVal & !usedPool)
    if (length(candidates) == 0) next

    # 가장 가까운 nMatches개 선택
    candidateDists <- dists[candidates]
    nPick <- min(nMatches, length(candidates))
    bestIdx <- candidates[order(candidateDists)[1:nPick]]

    for (bi in bestIdx) {
      matchedAnchorIdx <- c(matchedAnchorIdx, ai)
      matchedPoolIdx <- c(matchedPoolIdx, bi)
      usedPool[bi] <- TRUE
    }
  }

  nMatchedAnchors <- length(unique(matchedAnchorIdx))
  nMatchedPools <- length(matchedPoolIdx)

  if (reversed) {
    cat(sprintf("  결과: %d comparators matched, %d targets (%.1f:1)\n",
                nMatchedAnchors, nMatchedPools, nMatchedPools / max(nMatchedAnchors, 1)))
    matched <- rbind(pool[unique(matchedPoolIdx), ], anchor[unique(matchedAnchorIdx), ])
  } else {
    cat(sprintf("  결과: %d targets matched, %d comparators (%.1f:1)\n",
                nMatchedAnchors, nMatchedPools, nMatchedPools / max(nMatchedAnchors, 1)))
    matched <- rbind(anchor[unique(matchedAnchorIdx), ], pool[unique(matchedPoolIdx), ])
  }

  return(matched)
}

# --- 함수: Cox 분석 ---
runCoxAnalysis <- function(matchedCohorts, allOutcomes, outcomeIds, targetId, comparatorId) {
  results <- data.frame()

  for (oid in outcomeIds) {
    oc <- allOutcomes[allOutcomes$outcomeId == oid & allOutcomes$daysToEvent > 0, ]
    firstEvent <- aggregate(daysToEvent ~ rowId, data = oc, FUN = min)
    names(firstEvent) <- c("rowId", "timeToEvent")

    analysisDf <- merge(
      matchedCohorts[, c("rowId", "treatment", "daysToObsEnd", "site")],
      firstEvent, by = "rowId", all.x = TRUE
    )
    analysisDf$maxFollow <- pmin(analysisDf$daysToObsEnd, 3650)
    analysisDf <- analysisDf[analysisDf$maxFollow > 0, ]

    analysisDf$event <- 0
    hasEvent <- !is.na(analysisDf$timeToEvent) & analysisDf$timeToEvent <= analysisDf$maxFollow
    analysisDf$event[hasEvent] <- 1

    analysisDf$time <- analysisDf$maxFollow
    analysisDf$time[hasEvent] <- analysisDf$timeToEvent[hasEvent]
    analysisDf$time <- pmax(analysisDf$time, 0.5)

    nT <- sum(analysisDf$treatment == 1)
    nC <- sum(analysisDf$treatment == 0)
    evT <- sum(analysisDf$event[analysisDf$treatment == 1])
    evC <- sum(analysisDf$event[analysisDf$treatment == 0])

    oName <- OUTCOME_NAMES[as.character(oid)]

    if (evT + evC < 2) {
      results <- rbind(results, data.frame(
        target_id = targetId, comparator_id = comparatorId,
        outcome_id = oid, outcome_name = oName,
        n_target = nT, n_comparator = nC,
        events_target = evT, events_comparator = evC,
        hr = NA, ci_lower = NA, ci_upper = NA, p_value = NA,
        note = "insufficient events", stringsAsFactors = FALSE
      ))
      next
    }

    tryCatch({
      nSites <- length(unique(analysisDf$site))
      if (nSites > 1) {
        # site를 공변량으로 보정 (strata가 아닌 fixed effect)
        # PS 모델에서 기관 간 매칭을 허용했으므로 strata 대신 covariate 사용
        analysisDf$site <- as.factor(analysisDf$site)
        fit <- coxph(Surv(time, event) ~ treatment + site, data = analysisDf)
      } else {
        fit <- coxph(Surv(time, event) ~ treatment, data = analysisDf)
      }

      hr <- exp(coef(fit)["treatment"])
      ci <- exp(confint(fit)["treatment", ])
      p <- summary(fit)$coefficients["treatment", "Pr(>|z|)"]

      sig <- ifelse(p < 0.05, "*", "")
      cat(sprintf("  %-30s HR=%.3f (%.3f-%.3f) p=%.4f%s  events=%d+%d\n",
                  oName, hr, ci[1], ci[2], p, sig, evT, evC))

      results <- rbind(results, data.frame(
        target_id = targetId, comparator_id = comparatorId,
        outcome_id = oid, outcome_name = oName,
        n_target = nT, n_comparator = nC,
        events_target = evT, events_comparator = evC,
        hr = round(hr, 4), ci_lower = round(ci[1], 4),
        ci_upper = round(ci[2], 4), p_value = round(p, 6),
        note = "", stringsAsFactors = FALSE
      ))
    }, error = function(e) {
      cat(sprintf("  %-30s -- (%s)\n", oName, e$message))
      results <<- rbind(results, data.frame(
        target_id = targetId, comparator_id = comparatorId,
        outcome_id = oid, outcome_name = oName,
        n_target = nT, n_comparator = nC,
        events_target = evT, events_comparator = evC,
        hr = NA, ci_lower = NA, ci_upper = NA, p_value = NA,
        note = substr(e$message, 1, 100), stringsAsFactors = FALSE
      ))
    })
  }

  return(results)
}

# =============================================================================
# MAIN
# =============================================================================
allResults <- data.frame()

for (comp in COMPARISONS) {
  cat(paste0(strrep("=", 80), "\n"))
  cat(sprintf("비교: t%d vs c%d (%s)\n", comp$target, comp$comparator, comp$name))
  cat(paste0(strrep("=", 80), "\n"))

  # 1. 데이터 통합
  cat("\n[1] 데이터 통합\n")
  pooledData <- loadAndPoolData(comp$target, comp$comparator)

  nT <- sum(pooledData$cohorts$treatment == 1)
  nC <- sum(pooledData$cohorts$treatment == 0)
  cat(sprintf("  통합: Target=%s, Comparator=%s\n", format(nT, big.mark=","), format(nC, big.mark=",")))

  # 2. Cyclops PS 적합
  cat("\n[2] Cyclops PS 적합\n")
  psResult <- fitPsWithCyclops(pooledData)

  psMeanT <- mean(psResult$cohorts$ps[psResult$cohorts$treatment == 1])
  psMeanC <- mean(psResult$cohorts$ps[psResult$cohorts$treatment == 0])
  cat(sprintf("  PS 분포: Target=%.4f, Comparator=%.4f\n", psMeanT, psMeanC))

  # 3. 1:2 매칭
  cat("\n[3] 1:2 PS Matching\n")
  matched <- matchPairs(psResult$cohorts, nMatches = 1, caliper = 0.2)

  # 4. 시간 구간별 Cox 분석
  TIME_WINDOWS <- list(
    list(name = "1_3650d", wStart = 1, wEnd = 3650)
  )

  for (tw in TIME_WINDOWS) {
    cat(sprintf("\n[4] Cox (%s, day %d-%d)\n", tw$name, tw$wStart, tw$wEnd))

    twResults <- data.frame()
    for (oid in OUTCOME_IDS) {
      oc <- pooledData$outcomes[pooledData$outcomes$outcomeId == oid &
                                pooledData$outcomes$daysToEvent >= tw$wStart &
                                pooledData$outcomes$daysToEvent <= tw$wEnd, ]

      if (nrow(oc) > 0) {
        firstEvent <- aggregate(daysToEvent ~ rowId, data = oc, FUN = min)
        names(firstEvent) <- c("rowId", "timeToEvent")
      } else {
        firstEvent <- data.frame(rowId = integer(0), timeToEvent = numeric(0))
      }

      analysisDf <- merge(
        matched[, c("rowId", "treatment", "daysToObsEnd", "site")],
        firstEvent, by = "rowId", all.x = TRUE
      )
      analysisDf$maxFollow <- pmin(analysisDf$daysToObsEnd, tw$wEnd)
      analysisDf <- analysisDf[analysisDf$maxFollow >= tw$wStart, ]

      analysisDf$event <- 0
      hasEvent <- !is.na(analysisDf$timeToEvent) & analysisDf$timeToEvent <= analysisDf$maxFollow
      analysisDf$event[hasEvent] <- 1

      analysisDf$time <- analysisDf$maxFollow - tw$wStart + 1
      analysisDf$time[hasEvent] <- analysisDf$timeToEvent[hasEvent] - tw$wStart + 1
      analysisDf$time <- pmax(analysisDf$time, 0.5)

      nT <- sum(analysisDf$treatment == 1)
      nC <- sum(analysisDf$treatment == 0)
      evT <- sum(analysisDf$event[analysisDf$treatment == 1])
      evC <- sum(analysisDf$event[analysisDf$treatment == 0])
      oName <- OUTCOME_NAMES[as.character(oid)]

      if (evT + evC < 3) {
        twResults <- rbind(twResults, data.frame(
          target_id = comp$target, comparator_id = comp$comparator,
          time_window = tw$name, window_start = tw$wStart, window_end = tw$wEnd,
          outcome_id = oid, outcome_name = oName,
          n_target = nT, n_comparator = nC,
          events_target = evT, events_comparator = evC,
          hr = NA, ci_lower = NA, ci_upper = NA, p_value = NA,
          note = "insufficient events", stringsAsFactors = FALSE
        ))
        next
      }

      tryCatch({
        nSites <- length(unique(analysisDf$site))
        if (nSites > 1) {
          analysisDf$site <- as.factor(analysisDf$site)
          fit <- coxph(Surv(time, event) ~ treatment + site, data = analysisDf)
        } else {
          fit <- coxph(Surv(time, event) ~ treatment, data = analysisDf)
        }

        hr <- exp(coef(fit)["treatment"])
        ci <- exp(confint(fit)["treatment", ])
        p <- summary(fit)$coefficients["treatment", "Pr(>|z|)"]

        sig <- ifelse(p < 0.05, "*", "")
        cat(sprintf("  %-15s HR=%.3f (%.3f-%.3f) p=%.4f%s ev=%d+%d\n",
                    oName, hr, ci[1], ci[2], p, sig, evT, evC))

        twResults <- rbind(twResults, data.frame(
          target_id = comp$target, comparator_id = comp$comparator,
          time_window = tw$name, window_start = tw$wStart, window_end = tw$wEnd,
          outcome_id = oid, outcome_name = oName,
          n_target = nT, n_comparator = nC,
          events_target = evT, events_comparator = evC,
          hr = round(hr, 4), ci_lower = round(ci[1], 4),
          ci_upper = round(ci[2], 4), p_value = round(p, 6),
          note = "", stringsAsFactors = FALSE
        ))
      }, error = function(e) {
        cat(sprintf("  %-15s -- (%s)\n", oName, e$message))
      })
    }
    allResults <- rbind(allResults, twResults)
  }
  cat("\n")
}

# 결과 저장
outPath <- file.path(OUTPUT_DIR, "ipd_10sites_nc_results.csv")
write.csv(allResults, outPath, row.names = FALSE, fileEncoding = "UTF-8")

cat(paste0(strrep("=", 80), "\n"))
cat(sprintf("결과 저장: %s\n", outPath))
cat(sprintf("총 %d개 분석 (%d개 HR 산출)\n", nrow(allResults), sum(!is.na(allResults$hr))))
