Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
library(CohortMethod)
library(Cyclops)
library(Andromeda)
library(survival)

BASE_DIR <- "C:/Users/data1/Desktop/atlas_auto_cmdata"
OUTPUT_DIR <- file.path(BASE_DIR, "table1_output")
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

KEEP_SITES <- c("AUMC_5.3.1_11", "GNUCH_5.3.1_06", "GNUH_5.3.1_07",
                "HUMC_DONGTAN_5.3.1_04", "JCMJ_5.3.1_04",
                "KDH_5.3.1_08", "KHNMC_5.3.1_08")

# ---- 함수: 데이터 로드 + 통합 (ipd_7sites_v7b.R과 동일) ----
loadAndPoolData <- function(cmDataDir, targetId, comparatorId) {
  allCohorts <- data.frame()
  allCovariates <- data.frame()
  allCovariateRef <- data.frame()
  allAnalysisRef <- data.frame()

  SITES <- sort(list.dirs(cmDataDir, recursive = FALSE, full.names = FALSE))
  SITES <- SITES[SITES %in% KEEP_SITES]

  for (site in SITES) {
    cmName <- sprintf("CmData_l1_t%d_c%d", targetId, comparatorId)
    cmDir <- file.path(cmDataDir, site, cmName)
    if (!dir.exists(cmDir)) next
    sqliteFiles <- list.files(cmDir, pattern = "\\.sqlite$", full.names = TRUE)
    if (length(sqliteFiles) == 0) next

    con <- DBI::dbConnect(RSQLite::SQLite(), sqliteFiles[1])
    cohorts <- DBI::dbReadTable(con, "cohorts")
    covariates <- DBI::dbReadTable(con, "covariates")
    covariateRef <- DBI::dbReadTable(con, "covariateRef")
    analysisRef <- DBI::dbReadTable(con, "analysisRef")
    DBI::dbDisconnect(con)

    siteIdx <- which(SITES == site)
    offset <- (siteIdx - 1) * 10000000
    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$site <- site
    covariates$rowId <- as.integer(covariates$rowId) + offset

    allCohorts <- rbind(allCohorts, cohorts)
    allCovariates <- rbind(allCovariates, covariates)
    allCovariateRef <- rbind(allCovariateRef, covariateRef)
    allAnalysisRef <- rbind(allAnalysisRef, analysisRef)
    rm(cohorts, covariates, covariateRef, analysisRef); gc()
  }

  allCovariateRef <- unique(allCovariateRef)
  allAnalysisRef <- unique(allAnalysisRef)

  # site dummy
  siteLevels <- sort(unique(allCohorts$site))
  if (length(siteLevels) > 1) {
    maxCovId <- max(allCovariateRef$covariateId, na.rm = TRUE)
    for (i in 2:length(siteLevels)) {
      newCovId <- maxCovId + i
      s <- siteLevels[i]
      siteRows <- allCohorts[allCohorts$site == s, ]
      allCovariates <- rbind(allCovariates, data.frame(
        rowId = siteRows$rowId, covariateId = newCovId, covariateValue = 1))
      allCovariateRef <- rbind(allCovariateRef, data.frame(
        covariateId = newCovId, covariateName = paste0("site: ", s),
        analysisId = 999, conceptId = 0))
    }
  }

  return(list(cohorts = allCohorts, covariates = allCovariates,
              covariateRef = allCovariateRef, analysisRef = allAnalysisRef))
}

# ---- 함수: Cyclops PS ----
fitPS <- function(pooledData) {
  cohorts <- pooledData$cohorts
  covariates <- pooledData$covariates
  rowIds <- cohorts$rowId
  y <- cohorts$treatment

  rowIdMap <- setNames(seq_along(rowIds), as.character(rowIds))
  validCovs <- covariates[as.character(covariates$rowId) %in% names(rowIdMap), ]

  outcomes <- data.frame(rowId = rowIds, y = y)
  covLong <- data.frame(rowId = validCovs$rowId, covariateId = validCovs$covariateId,
                        covariateValue = validCovs$covariateValue)

  cyclopsData <- Cyclops::convertToCyclopsData(outcomes = outcomes, covariates = covLong,
    modelType = "lr", addIntercept = TRUE)
  prior <- Cyclops::createPrior("laplace", useCrossValidation = TRUE, variance = 1,
    exclude = 0, forceIntercept = FALSE)
  control <- Cyclops::createControl(maxIterations = 1000, tolerance = 2e-7,
    convergenceType = "gradient", cvType = "auto", fold = 10, seed = 42, noiseLevel = "quiet")
  fit <- Cyclops::fitCyclopsModel(cyclopsData, prior = prior, control = control)
  rm(cyclopsData, prior, control); gc()

  cohorts$ps <- predict(fit, type = "response")
  return(cohorts)
}

# ---- 함수: 1:1 매칭 ----
matchPS <- function(psCohorts) {
  psCohorts$logitPs <- log(pmax(psCohorts$ps, 1e-8) / pmax(1 - psCohorts$ps, 1e-8))
  sdLogit <- sd(psCohorts$logitPs)
  caliperVal <- 0.2 * sdLogit

  targets <- psCohorts[psCohorts$treatment == 1, ]
  comparators <- psCohorts[psCohorts$treatment == 0, ]

  if (nrow(targets) <= nrow(comparators)) {
    anchor <- targets; pool <- comparators; reversed <- FALSE
  } else {
    anchor <- comparators; pool <- targets; reversed <- TRUE
  }

  set.seed(42)
  anchorOrder <- sample(nrow(anchor))
  matchedAnchorIdx <- c(); matchedPoolIdx <- c()
  usedPool <- logical(nrow(pool)); poolLogit <- pool$logitPs

  for (ai in anchorOrder) {
    dists <- abs(poolLogit - anchor$logitPs[ai])
    candidates <- which(dists <= caliperVal & !usedPool)
    if (length(candidates) == 0) next
    bestIdx <- candidates[which.min(dists[candidates])]
    matchedAnchorIdx <- c(matchedAnchorIdx, ai)
    matchedPoolIdx <- c(matchedPoolIdx, bestIdx)
    usedPool[bestIdx] <- TRUE
  }

  if (reversed) {
    matched <- rbind(pool[unique(matchedPoolIdx), ], anchor[unique(matchedAnchorIdx), ])
  } else {
    matched <- rbind(anchor[unique(matchedAnchorIdx), ], pool[unique(matchedPoolIdx), ])
  }
  return(matched)
}

# ---- 함수: Balance 계산 ----
computeBalance <- function(allCohorts, matchedCohorts, covariates, covariateRef) {
  # before matching
  beforeTarget <- allCohorts$rowId[allCohorts$treatment == 1]
  beforeComp <- allCohorts$rowId[allCohorts$treatment == 0]
  # after matching
  afterTarget <- matchedCohorts$rowId[matchedCohorts$treatment == 1]
  afterComp <- matchedCohorts$rowId[matchedCohorts$treatment == 0]

  covIds <- unique(covariateRef$covariateId[covariateRef$analysisId != 999])
  results <- data.frame()

  for (cid in covIds) {
    cRows <- covariates[covariates$covariateId == cid, ]

    bt <- mean(cRows$rowId %in% beforeTarget & cRows$covariateId == cid)
    # actually: proportion of target that has this covariate
    bt_n <- sum(cRows$rowId %in% beforeTarget)
    bc_n <- sum(cRows$rowId %in% beforeComp)
    at_n <- sum(cRows$rowId %in% afterTarget)
    ac_n <- sum(cRows$rowId %in% afterComp)

    bt_prop <- bt_n / length(beforeTarget)
    bc_prop <- bc_n / length(beforeComp)
    at_prop <- at_n / length(afterTarget)
    ac_prop <- ac_n / length(afterComp)

    # StdDiff for binary
    bt_sd <- sqrt(bt_prop * (1 - bt_prop))
    bc_sd <- sqrt(bc_prop * (1 - bc_prop))
    at_sd <- sqrt(at_prop * (1 - at_prop))
    ac_sd <- sqrt(ac_prop * (1 - ac_prop))

    before_sdiff <- (bt_prop - bc_prop) / sqrt((bt_sd^2 + bc_sd^2) / 2)
    after_sdiff <- (at_prop - ac_prop) / sqrt((at_sd^2 + ac_sd^2) / 2)

    cname <- covariateRef$covariateName[covariateRef$covariateId == cid][1]
    aid <- covariateRef$analysisId[covariateRef$covariateId == cid][1]

    results <- rbind(results, data.frame(
      covariateId = cid, covariateName = cname, analysisId = aid,
      beforeMatchingMeanTarget = round(bt_prop, 4),
      beforeMatchingMeanComparator = round(bc_prop, 4),
      beforeMatchingStdDiff = round(before_sdiff, 4),
      afterMatchingMeanTarget = round(at_prop, 4),
      afterMatchingMeanComparator = round(ac_prop, 4),
      afterMatchingStdDiff = round(after_sdiff, 4),
      beforeTargetN = bt_n, beforeCompN = bc_n,
      afterTargetN = at_n, afterCompN = ac_n,
      stringsAsFactors = FALSE
    ))
  }
  return(results)
}

# ====== MAIN ======
COMPARISONS <- list(
  list(target = 1072, comparator = 1074, name = "vs_Chol", cmdir = "cmData_v7"),
  list(target = 1072, comparator = 1121, name = "vs_Hernia", cmdir = "cmData_v7")
)

for (comp in COMPARISONS) {
  cat(sprintf("\n===== %s =====\n", comp$name))

  cat("[1] Loading data...\n")
  pooled <- loadAndPoolData(file.path(BASE_DIR, comp$cmdir), comp$target, comp$comparator)
  nT <- sum(pooled$cohorts$treatment == 1)
  nC <- sum(pooled$cohorts$treatment == 0)
  cat(sprintf("  Before matching: Target=%d, Comparator=%d\n", nT, nC))

  cat("[2] Fitting PS...\n")
  psCohorts <- fitPS(pooled)

  cat("[3] 1:1 Matching...\n")
  matched <- matchPS(psCohorts)
  nTm <- sum(matched$treatment == 1)
  nCm <- sum(matched$treatment == 0)
  cat(sprintf("  After matching: Target=%d, Comparator=%d\n", nTm, nCm))

  cat("[4] Computing balance...\n")
  balance <- computeBalance(pooled$cohorts, matched, pooled$covariates, pooled$covariateRef)

  # 저장
  out_file <- file.path(OUTPUT_DIR, sprintf("ipd_balance_%s.csv", comp$name))
  write.csv(balance, out_file, row.names = FALSE)
  cat(sprintf("  Saved: %s (%d covariates)\n", out_file, nrow(balance)))

  # StdDiff 요약
  cat(sprintf("  Before: max|StdDiff|=%.3f, >0.1: %d/%d\n",
    max(abs(balance$beforeMatchingStdDiff), na.rm = TRUE),
    sum(abs(balance$beforeMatchingStdDiff) > 0.1, na.rm = TRUE), nrow(balance)))
  cat(sprintf("  After:  max|StdDiff|=%.3f, >0.1: %d/%d\n",
    max(abs(balance$afterMatchingStdDiff), na.rm = TRUE),
    sum(abs(balance$afterMatchingStdDiff) > 0.1, na.rm = TRUE), nrow(balance)))

  # createCmTable1 시도
  tryCatch({
    table1 <- createCmTable1(balance,
      beforeLabel = "Before matching", afterLabel = "After matching",
      targetLabel = "Appendectomy",
      comparatorLabel = ifelse(comp$comparator == 1074, "Cholecystectomy", "Hernia repair"),
      beforeTargetPopSize = nT, beforeComparatorPopSize = nC,
      afterTargetPopSize = nTm, afterComparatorPopSize = nCm)
    t1_file <- file.path(OUTPUT_DIR, sprintf("table1_ipd_%s.csv", comp$name))
    write.csv(table1, t1_file, row.names = FALSE)
    cat(sprintf("  Table1: %s\n", t1_file))
  }, error = function(e) {
    cat(sprintf("  createCmTable1 error: %s\n", e$message))
  })

  rm(pooled, psCohorts, matched, balance); gc()
}

cat("\nDone.\n")
