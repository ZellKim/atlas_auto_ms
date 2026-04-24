# ⚠️  DEPRECATED 2026-04-24 — 구형 4-step pipeline, R/lib/ipd_pooled.R 로 대체.
# Kept for reference only. See docs/system_knowledge_base.md §7.2.
# =============================================================================
# 01_pool_cmdata.R
# 다기관 CmData를 로드하여 단일 CohortMethodData 객체로 병합
# =============================================================================

source("00_config.R")

# -----------------------------------------------------------------------------
# 1. 단일 사이트 CmData 로드 및 rowId 재매핑
# -----------------------------------------------------------------------------
loadAndRemapSite <- function(resultFolder, siteName, siteIndex, rowIdOffset) {
  cmDataPath <- file.path(resultFolder, "cmOutput", cmDataFileName)

  if (!file.exists(cmDataPath)) {
    warning(sprintf("CmData not found for %s: %s", siteName, cmDataPath))
    return(NULL)
  }

  message(sprintf("[%d] Loading %s from: %s", siteIndex, siteName, cmDataPath))
  cmData <- CohortMethod::loadCohortMethodData(cmDataPath)

  # cohorts 테이블
  cohorts <- cmData$cohorts %>% collect()
  nRows <- nrow(cohorts)
  message(sprintf("  - %s: %d subjects (T=%d, C=%d)",
                  siteName, nRows,
                  sum(cohorts$treatment == 1),
                  sum(cohorts$treatment == 0)))

  cohorts$rowId <- cohorts$rowId + rowIdOffset
  cohorts$personSeqId <- cohorts$personSeqId + rowIdOffset
  cohorts$siteId <- siteIndex

  # outcomes 테이블
  outcomes <- cmData$outcomes %>% collect()
  outcomes$rowId <- outcomes$rowId + rowIdOffset

  # covariates 테이블 (sparse)
  covariates <- cmData$covariates %>% collect()
  covariates$rowId <- covariates$rowId + rowIdOffset

  # reference 테이블
  covariateRef <- cmData$covariateRef %>% collect()
  analysisRef <- cmData$analysisRef %>% collect()

  Andromeda::close(cmData)

  return(list(
    cohorts = cohorts,
    outcomes = outcomes,
    covariates = covariates,
    covariateRef = covariateRef,
    analysisRef = analysisRef,
    siteName = siteName,
    siteIndex = siteIndex,
    nRows = nRows,
    rowIdOffset = rowIdOffset
  ))
}

# -----------------------------------------------------------------------------
# 2. 사이트 indicator covariate 추가
# -----------------------------------------------------------------------------
addSiteCovariates <- function(pooledCmData, siteMappings) {
  siteIdBase <- 99000000  # 기존 covariateId와 충돌 방지
  nSites <- nrow(siteMappings)

  # cohorts에서 siteId 가져오기
  cohorts <- pooledCmData$cohorts %>% collect()

  # 사이트별 binary indicator covariate 생성
  siteCovRows <- data.frame(
    rowId = cohorts$rowId,
    covariateId = siteIdBase + cohorts$siteId,
    covariateValue = 1
  )
  Andromeda::appendToTable(pooledCmData$covariates, siteCovRows)

  # covariateRef에 사이트 indicator 추가
  newCovRef <- data.frame(
    covariateId = siteIdBase + seq_len(nSites),
    covariateName = paste0("Site: ", siteMappings$siteName),
    analysisId = 9999L
  )
  Andromeda::appendToTable(pooledCmData$covariateRef, newCovRef)

  # analysisRef에 사이트 analysis 추가
  newAnalysisRef <- data.frame(
    analysisId = 9999L,
    analysisName = "Site indicator"
  )
  existingAnalysisIds <- pooledCmData$analysisRef %>% pull(analysisId)
  if (!(9999L %in% existingAnalysisIds)) {
    Andromeda::appendToTable(pooledCmData$analysisRef, newAnalysisRef)
  }

  message(sprintf("  Added %d site indicator covariates", nSites))
  return(pooledCmData)
}

# -----------------------------------------------------------------------------
# 3. 전체 사이트 병합
# -----------------------------------------------------------------------------
poolAllSites <- function(resultFolders, siteNames) {
  allSites <- list()
  siteMappings <- data.frame(
    siteIndex = integer(),
    siteName = character(),
    rowIdOffset = integer(),
    nRows = integer(),
    nTarget = integer(),
    nComparator = integer(),
    stringsAsFactors = FALSE
  )

  currentOffset <- 0L
  validSiteCount <- 0

  for (i in seq_along(siteNames)) {
    site <- loadAndRemapSite(
      resultFolder = resultFolders[[siteNames[i]]],
      siteName = siteNames[i],
      siteIndex = i,
      rowIdOffset = currentOffset
    )

    if (is.null(site)) next

    validSiteCount <- validSiteCount + 1
    allSites[[validSiteCount]] <- site

    siteMappings <- rbind(siteMappings, data.frame(
      siteIndex = i,
      siteName = siteNames[i],
      rowIdOffset = currentOffset,
      nRows = site$nRows,
      nTarget = sum(site$cohorts$treatment == 1),
      nComparator = sum(site$cohorts$treatment == 0),
      stringsAsFactors = FALSE
    ))

    currentOffset <- currentOffset + site$nRows + 1L
  }

  if (validSiteCount == 0) {
    stop("No valid CmData found across any site.")
  }

  message(sprintf("\nPooling %d sites...", validSiteCount))

  # rbind all tables
  pooledCohorts <- do.call(rbind, lapply(allSites, `[[`, "cohorts"))
  pooledOutcomes <- do.call(rbind, lapply(allSites, `[[`, "outcomes"))
  pooledCovariates <- do.call(rbind, lapply(allSites, `[[`, "covariates"))

  # covariateRef/analysisRef 중복 제거
  allCovRef <- do.call(rbind, lapply(allSites, `[[`, "covariateRef"))
  pooledCovRef <- allCovRef[!duplicated(allCovRef$covariateId), ]

  allAnalysisRef <- do.call(rbind, lapply(allSites, `[[`, "analysisRef"))
  pooledAnalysisRef <- allAnalysisRef[!duplicated(allAnalysisRef$analysisId), ]

  # Andromeda 객체 생성
  pooledCmData <- Andromeda::andromeda(
    cohorts = pooledCohorts,
    outcomes = pooledOutcomes,
    covariates = pooledCovariates,
    covariateRef = pooledCovRef,
    analysisRef = pooledAnalysisRef
  )

  # CohortMethodData 클래스 설정
  class(pooledCmData) <- "CohortMethodData"
  attr(class(pooledCmData), "package") <- "CohortMethod"

  metaData <- list(
    targetId = targetId,
    comparatorId = comparatorId,
    outcomeIds = allOutcomeIds,
    attrition = data.frame(
      description = "Original cohorts",
      targetPersons = sum(siteMappings$nTarget),
      comparatorPersons = sum(siteMappings$nComparator),
      stringsAsFactors = FALSE
    )
  )
  attr(pooledCmData, "metaData") <- metaData

  # 사이트 indicator 추가
  pooledCmData <- addSiteCovariates(pooledCmData, siteMappings)

  # 검증
  message("\n=== Pooling Summary ===")
  message(sprintf("Total subjects: %d (T=%d, C=%d)",
                  nrow(pooledCohorts),
                  sum(pooledCohorts$treatment == 1),
                  sum(pooledCohorts$treatment == 0)))
  message(sprintf("Total outcome records: %d", nrow(pooledOutcomes)))
  message(sprintf("Total covariate records: %d", nrow(pooledCovariates)))
  message(sprintf("Unique covariates: %d", nrow(pooledCovRef)))
  message(sprintf("rowId unique: %s", length(unique(pooledCohorts$rowId)) == nrow(pooledCohorts)))

  for (j in seq_len(nrow(siteMappings))) {
    message(sprintf("  %s: N=%d (T=%d, C=%d)",
                    siteMappings$siteName[j],
                    siteMappings$nRows[j],
                    siteMappings$nTarget[j],
                    siteMappings$nComparator[j]))
  }

  # 저장
  savePath <- file.path(outputFolder, "CmData_pooled.zip")
  CohortMethod::saveCohortMethodData(pooledCmData, savePath)
  message(sprintf("\nPooled CmData saved: %s", savePath))

  # siteMappings 저장
  write.csv(siteMappings, file.path(outputFolder, "siteMappings.csv"), row.names = FALSE)

  return(list(cmData = pooledCmData, siteMappings = siteMappings))
}

# =============================================================================
# 실행
# =============================================================================
result <- poolAllSites(resultFolders, siteNames)
pooledCmData <- result$cmData
siteMappings <- result$siteMappings
