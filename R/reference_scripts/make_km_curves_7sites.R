Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
library(CohortMethod)
library(Cyclops)
library(Andromeda)
library(survival)
library(survminer)
library(ggplot2)

BASE_DIR <- "C:/Users/data1/Desktop/atlas_auto_cmdata"
OUTPUT_DIR <- file.path(BASE_DIR, "km_curves")
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

KEEP_SITES <- c("AUMC_5.3.1_11", "GNUCH_5.3.1_06", "GNUH_5.3.1_07",
                "HUMC_DONGTAN_5.3.1_04", "JCMJ_5.3.1_04",
                "KDH_5.3.1_08", "KHNMC_5.3.1_08")

# ---- 데이터 로드 함수 ----
loadAndPoolData <- function(cmDataDir, targetId, comparatorId) {
  allCohorts <- data.frame(); allOutcomes <- data.frame()
  allCovariates <- data.frame(); allCovariateRef <- data.frame()

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
    outcomes <- DBI::dbReadTable(con, "outcomes")
    covariates <- DBI::dbReadTable(con, "covariates")
    covariateRef <- DBI::dbReadTable(con, "covariateRef")
    DBI::dbDisconnect(con)

    siteIdx <- which(SITES == site)
    offset <- (siteIdx - 1) * 10000000
    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$site <- site
    outcomes$rowId <- as.integer(outcomes$rowId) + offset
    covariates$rowId <- as.integer(covariates$rowId) + offset

    allCohorts <- rbind(allCohorts, cohorts)
    allOutcomes <- rbind(allOutcomes, outcomes)
    allCovariates <- rbind(allCovariates, covariates)
    allCovariateRef <- rbind(allCovariateRef, unique(covariateRef))
    rm(cohorts, outcomes, covariates, covariateRef); gc()
  }
  allCovariateRef <- unique(allCovariateRef)

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

  return(list(cohorts = allCohorts, outcomes = allOutcomes,
              covariates = allCovariates, covariateRef = allCovariateRef))
}

# ---- PS fitting + 1:1 matching ----
fitAndMatch <- function(pooledData) {
  cohorts <- pooledData$cohorts
  covariates <- pooledData$covariates

  outcomes_df <- data.frame(rowId = cohorts$rowId, y = cohorts$treatment)
  covLong <- data.frame(rowId = covariates$rowId, covariateId = covariates$covariateId,
                        covariateValue = covariates$covariateValue)

  cat("  Cyclops PS fitting...\n")
  cyclopsData <- Cyclops::convertToCyclopsData(outcomes = outcomes_df, covariates = covLong,
    modelType = "lr", addIntercept = TRUE)
  prior <- Cyclops::createPrior("laplace", useCrossValidation = TRUE, variance = 1,
    exclude = 0, forceIntercept = FALSE)
  control <- Cyclops::createControl(maxIterations = 1000, tolerance = 2e-7,
    convergenceType = "gradient", cvType = "auto", fold = 10, seed = 42, noiseLevel = "quiet")
  fit <- Cyclops::fitCyclopsModel(cyclopsData, prior = prior, control = control)
  cohorts$ps <- predict(fit, type = "response")
  rm(cyclopsData, prior, control, fit); gc()

  cat("  1:1 matching...\n")
  cohorts$logitPs <- log(pmax(cohorts$ps, 1e-8) / pmax(1 - cohorts$ps, 1e-8))
  sdLogit <- sd(cohorts$logitPs)
  caliperVal <- 0.2 * sdLogit

  targets <- cohorts[cohorts$treatment == 1, ]
  comparators <- cohorts[cohorts$treatment == 0, ]
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
  cat(sprintf("  Matched: T=%d, C=%d\n", sum(matched$treatment==1), sum(matched$treatment==0)))
  return(matched)
}

# ---- KM curve 생성 (survminer, cumulative hazard, risk table, TIFF) ----
makeKM <- function(matched, allOutcomes, outcomeId, outcomeName, compName, targetName = "Appendectomy", maxDays = 3650) {
  oc <- allOutcomes[allOutcomes$outcomeId == outcomeId & allOutcomes$daysToEvent > 0, ]
  firstEvent <- aggregate(daysToEvent ~ rowId, data = oc, FUN = min)
  names(firstEvent) <- c("rowId", "timeToEvent")

  df <- merge(matched[, c("rowId", "treatment", "daysToObsEnd", "site")],
              firstEvent, by = "rowId", all.x = TRUE)
  df$maxFollow <- pmin(df$daysToObsEnd, maxDays)
  df <- df[df$maxFollow > 0, ]

  df$event <- 0
  hasEvent <- !is.na(df$timeToEvent) & df$timeToEvent <= df$maxFollow
  df$event[hasEvent] <- 1
  df$time <- df$maxFollow
  df$time[hasEvent] <- df$timeToEvent[hasEvent]
  df$time <- pmax(df$time, 0.5)

  df$treatment <- factor(df$treatment, levels = c(1, 0), labels = c(targetName, compName))

  evT <- sum(df$event[df$treatment == targetName])
  evC <- sum(df$event[df$treatment == compName])

  if (evT + evC < 3) {
    cat(sprintf("  %s: insufficient events (%d+%d)\n", outcomeName, evT, evC))
    return(invisible(NULL))
  }

  # Cox HR
  cox <- coxph(Surv(time, event) ~ treatment, data = df)
  hr <- exp(coef(cox))
  ci <- exp(confint(cox))
  lrt <- survdiff(Surv(time, event) ~ treatment, data = df)
  pval <- 1 - pchisq(lrt$chisq, 1)

  # KM fit
  KM_fit <- survfit(Surv(time, event) ~ treatment, data = df, type = "kaplan-meier")

  # ggsurvplot (cumulative hazard)
  KM_plot <- ggsurvplot(
    KM_fit,
    fun = "cumhaz",
    palette = c("#5048FF", "#ff7608"),
    surv.scale = "default",
    conf.int = FALSE, censor = FALSE,
    xlab = "Time (days)",
    ylab = "Cumulative hazard",
    font.x = c(15, "plain", "black"),
    font.y = c(15, "plain", "black"),
    font.tickslab = c(15, "plain", "black"),
    legend = "top",
    legend.title = "",
    legend.labs = c(targetName, compName),
    font.legend = c(15, "plain", "black"),
    risk.table = TRUE,
    risk.table.title = "Number at risk by time",
    risk.table.col = "black",
    risk.table.fontsize = 5,
    risk.table.y.text.col = TRUE,
    ggtheme = theme_classic(base_size = 15) +
      theme(axis.title.y = element_text(margin = margin(r = -130, l = -10))),
    tables.theme = theme_classic(base_size = 15) +
      theme(
        axis.text.x = element_text(size = 15, face = "plain", color = "black"),
        plot.title = element_text(size = 15, face = "plain", color = "black")
      ),
    xlim = c(0, maxDays),
    break.time.by = 365
  )

  # 제목 추가
  KM_plot$plot <- KM_plot$plot +
    ggtitle(sprintf("%s\nHR=%.3f (95%% CI: %.3f-%.3f), p=%.4f | events: %d vs %d",
                    outcomeName, hr, ci[1], ci[2], pval, evT, evC))

  # TIFF 저장
  fname <- sprintf("km_%s_%s.tiff",
                    gsub("[/ ]", "_", outcomeName),
                    gsub(" ", "_", compName))
  tiff(file.path(OUTPUT_DIR, fname), width = 800, height = 600, units = "px")
  print(KM_plot)
  dev.off()

  cat(sprintf("  %s: HR=%.3f [%.3f-%.3f] p=%.4f events=%d+%d\n",
              outcomeName, hr, ci[1], ci[2], pval, evT, evC))
}

# ====== MAIN ======

# Calibration 후 유의한 결과
SIG_OUTCOMES <- list(
  list(target=1072, comparator=1074, cmdir="cmData_v7", compName="Cholecystectomy",
       outcomes=list(
         list(id=1095, name="Biliary_calculus"),
         list(id=1096, name="T2DM")
       )),
  list(target=1072, comparator=1121, cmdir="cmData_v7", compName="Hernia repair",
       outcomes=list(
         list(id=1095, name="Biliary_calculus")
       )),
  list(target=1072, comparator=1074, cmdir="cmData_biomarker", compName="Cholecystectomy",
       outcomes=list(
         list(id=1098, name="WBC"), list(id=1099, name="Neutrophils"),
         list(id=1100, name="Lymphocytes"), list(id=1101, name="Eosinophils"),
         list(id=1102, name="Monocytes"), list(id=1103, name="Basophils"),
         list(id=1104, name="CRP"), list(id=1108, name="Glucose_DM"),
         list(id=1109, name="Glucose_preDM"), list(id=1112, name="TG"),
         list(id=1116, name="ALT"), list(id=1119, name="Albumin")
       )),
  list(target=1072, comparator=1121, cmdir="cmData_biomarker", compName="Hernia repair",
       outcomes=list(
         list(id=1098, name="WBC"), list(id=1099, name="Neutrophils"),
         list(id=1100, name="Lymphocytes"), list(id=1104, name="CRP"),
         list(id=1109, name="Glucose_preDM"), list(id=1119, name="Albumin")
       )),
  list(target=1072, comparator=1076, cmdir="cmData_v7", compName="General Population",
       outcomes=list(
         list(id=1096, name="T2DM")
       ))
)

loaded_cache <- list()

for (sig in SIG_OUTCOMES) {
  cache_key <- sprintf("t%d_c%d_%s", sig$target, sig$comparator, sig$cmdir)

  if (!cache_key %in% names(loaded_cache)) {
    cat(sprintf("\n===== Loading %s (c%d) =====\n", sig$cmdir, sig$comparator))
    pooled <- loadAndPoolData(file.path(BASE_DIR, sig$cmdir), sig$target, sig$comparator)
    matched <- fitAndMatch(pooled)
    loaded_cache[[cache_key]] <- list(matched = matched, outcomes = pooled$outcomes)
    rm(pooled); gc()
  }

  cached <- loaded_cache[[cache_key]]

  for (oc in sig$outcomes) {
    cat(sprintf("\n--- %s vs %s ---\n", oc$name, sig$compName))
    tryCatch(
      makeKM(cached$matched, cached$outcomes, oc$id, oc$name, sig$compName),
      error = function(e) cat(sprintf("  ERROR: %s\n", e$message))
    )
  }
}

cat("\nAll KM curves done.\n")
