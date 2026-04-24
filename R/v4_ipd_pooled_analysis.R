# ⚠️  DEPRECATED 2026-04-24 — superseded by R/lib/ipd_pooled.R + driver pattern.
# Kept for reference. See docs/system_knowledge_base.md §7.2.
# =============================================================================
# v4 IPD Pooled Analysis (v4_1a, v4_1b, v4_2, v4_3 — 5 common sites)
# - 2 comparators: 1074 (Chole), 1121 (Hernia)
# - 35 primary + 54 NC outcomes
# - Per-site Cyclops PS → 1:1 match → site-stratified Cox
# - NC calibration via EmpiricalCalibration
# =============================================================================

Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
suppressPackageStartupMessages({
  library(Cyclops)
  library(EmpiricalCalibration)
  library(survival)
  library(DBI)
  library(RSQLite)
  library(dplyr)
})

WORKSPACE <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_ipd_workspace"
OUT_DIR   <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output"
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

SITES <- c("AUMC","CHNUH","DCMC","GNUCH","GNUH","HUMC","JCMJ","KDH","KHNMC","KWMC","SCHBC","SCHCA","SCHGM","SCHSU")
ANALYSES <- c("v4_1a_cbc_wbc", "v4_1b_cbc_rbc", "v4_2_chem_hepa", "v4_3_meta_endo")
COMPARATORS <- list(list(id = 1074, name = "Chole"), list(id = 1121, name = "Hernia"))

PRIMARY_OUTCOMES <- list(
  v4_1a_cbc_wbc  = c(1357, 1390, 1391, 1392, 1360, 1385, 1373, 1374),
  v4_1b_cbc_rbc  = c(1375, 1362, 1368, 1358, 1387, 1395, 1394, 1393),
  v4_2_chem_hepa = c(1370, 1369, 1364, 1365, 1363, 1400, 1366, 1381, 1384, 1397, 1396),
  v4_3_meta_endo = c(1378, 1379, 1402, 1401, 1367, 1399, 1398, 1404)
)
OUTCOME_NAMES <- c(
  "1357"="WBC_high","1390"="Neutro#_thou_high","1391"="Neutro#_uL_high","1392"="Neutro_pct_high",
  "1360"="Lympho_pct_low","1385"="Lympho_pct_high","1373"="Eosino#_thou_high","1374"="Eosino#_uL_high",
  "1375"="Eosino_pct_high","1362"="Mono_high","1368"="Baso_pct_high","1358"="MCV_low",
  "1387"="MCV_high","1395"="RDW_high","1394"="Platelet_low","1393"="Platelet_high",
  "1370"="CRP_mgdL_high","1369"="CRP_mgL_high","1364"="ALT_high","1365"="AST_high",
  "1363"="ALP_high","1400"="TotBili_high","1366"="Albumin_low","1381"="HbA1c_high",
  "1384"="LDL_high","1397"="TG_high","1396"="TC_high",
  "1378"="GlucDM","1379"="GlucPreDM","1402"="TotProt_low","1401"="TotProt_high",
  "1367"="BUN_high","1399"="TSH_low","1398"="TSH_high","1404"="VitD_low"
)
ALL_PRIMARY <- unlist(PRIMARY_OUTCOMES)

# -----------------------------------------------------------------------------
# Load one CmData (sqlite) → cohorts, outcomes, covariates
# -----------------------------------------------------------------------------
loadCm <- function(siteCode, analysis, comparatorId) {
  d <- file.path(WORKSPACE, siteCode, analysis, sprintf("CmData_l1_t1072_c%d", comparatorId))
  sqf <- list.files(d, pattern = "\\.sqlite$", full.names = TRUE)[1]
  if (is.na(sqf)) return(NULL)
  con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
  res <- list(
    cohorts     = DBI::dbReadTable(con, "cohorts"),
    outcomes    = DBI::dbReadTable(con, "outcomes"),
    covariates  = DBI::dbReadTable(con, "covariates"),
    covariateRef = DBI::dbReadTable(con, "covariateRef"),
    analysisRef = DBI::dbReadTable(con, "analysisRef")
  )
  DBI::dbDisconnect(con)
  res
}

# -----------------------------------------------------------------------------
# Build one pooled dataset (5 sites × 4 analyses) for given comparator
# -----------------------------------------------------------------------------
buildPooled <- function(comparatorId) {
  cat(sprintf("\n=== buildPooled c=%d ===\n", comparatorId))
  allCohorts <- list(); allOutcomes <- list(); allCov <- list(); covRef <- list()
  for (si in seq_along(SITES)) {
    site <- SITES[si]
    offset <- (si - 1) * 100000000L  # 1e8 — safely unique rowIds across sites

    # v4_1a as the source of truth for cohorts + covariates (verified below)
    cm_1a <- loadCm(site, "v4_1a_cbc_wbc", comparatorId)
    if (is.null(cm_1a)) { cat(sprintf("  %s: skip (no v4_1a c=%d)\n", site, comparatorId)); next }
    cohorts <- cm_1a$cohorts
    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$personSeqId <- NULL
    cohorts$site <- site
    # keep only needed cols
    covA <- cm_1a$covariates
    covA$rowId <- as.integer(covA$rowId) + offset
    covRefA <- cm_1a$covariateRef

    # Stack outcomes from all 4 analyses
    siteOc <- list()
    for (a in ANALYSES) {
      cm_a <- loadCm(site, a, comparatorId)
      if (is.null(cm_a)) { cat(sprintf("  %s/%s: skip\n", site, a)); next }
      # sanity: verify cohorts identical rowIds count
      if (nrow(cm_a$cohorts) != nrow(cm_1a$cohorts)) {
        cat(sprintf("  WARN: %s/%s cohort size differs (%d vs %d)\n", site, a, nrow(cm_a$cohorts), nrow(cm_1a$cohorts)))
      }
      oc <- cm_a$outcomes
      oc$rowId <- as.integer(oc$rowId) + offset
      # keep only outcomes that belong to this analysis's primary + NC (NC same across analyses, so may duplicate)
      siteOc[[a]] <- oc
    }
    oc_all <- bind_rows(siteOc)
    # De-dup NC duplicates: unique by (rowId, outcomeId, daysToEvent)
    oc_all <- oc_all %>% distinct(rowId, outcomeId, daysToEvent, .keep_all = TRUE)

    cat(sprintf("  %s: cohorts=%d (T=%d, C=%d), outcomes rows=%d, outcome IDs=%d\n",
                site, nrow(cohorts),
                sum(cohorts$treatment == 1), sum(cohorts$treatment == 0),
                nrow(oc_all), length(unique(oc_all$outcomeId))))

    allCohorts[[site]]  <- cohorts
    allOutcomes[[site]] <- oc_all
    allCov[[site]]      <- covA
    covRef[[length(covRef) + 1]] <- covRefA
  }
  list(
    cohorts = bind_rows(allCohorts),
    outcomes = bind_rows(allOutcomes),
    covariates = bind_rows(allCov),
    covariateRef = bind_rows(covRef) %>% distinct(covariateId, .keep_all = TRUE)
  )
}

# -----------------------------------------------------------------------------
# Cyclops PS fit (LASSO, CV)
# -----------------------------------------------------------------------------
fitPs <- function(pooled, maxCompFit = 150000L) {
  coh <- pooled$cohorts; cov <- pooled$covariates
  nT <- sum(coh$treatment == 1); nC <- sum(coh$treatment == 0)
  cat(sprintf("  PS fit input: T=%d, C=%d\n", nT, nC))

  # subsample comparators if too many
  if (nC > maxCompFit) {
    set.seed(42)
    compIds <- coh$rowId[coh$treatment == 0]
    sampled <- sample(compIds, maxCompFit)
    fitIds <- c(coh$rowId[coh$treatment == 1], sampled)
    fitCoh <- coh[coh$rowId %in% fitIds, ]
    fitCov <- cov[cov$rowId %in% fitIds, ]
    cat(sprintf("  Subsampled comparators: %d → %d\n", nC, maxCompFit))
  } else {
    fitCoh <- coh; fitCov <- cov
  }

  outcomesY <- data.frame(rowId = fitCoh$rowId, y = fitCoh$treatment)
  cyData <- Cyclops::convertToCyclopsData(
    outcomes = outcomesY,
    covariates = fitCov[, c("rowId", "covariateId", "covariateValue")],
    modelType = "lr", addIntercept = TRUE
  )
  prior <- Cyclops::createPrior("laplace", useCrossValidation = TRUE, variance = 1, exclude = 0, forceIntercept = FALSE)
  control <- Cyclops::createControl(
    maxIterations = 1000, tolerance = 2e-7, convergenceType = "gradient",
    cvType = "auto", fold = 10, lowerLimit = 0.01, upperLimit = 20, seed = 42, noiseLevel = "quiet"
  )
  t0 <- proc.time()
  fit <- Cyclops::fitCyclopsModel(cyData, prior = prior, control = control)
  cat(sprintf("  Cyclops fit: %.1fs\n", (proc.time() - t0)[3]))

  ps <- predict(fit, type = "response")
  fitCoh$ps <- ps

  # if subsampled: predict PS on full cohort (but covariates must match the cyclops model)
  if (nC > maxCompFit) {
    # fit dropped covariates absent; need to map
    # Use full pooled cohort with all covariates; convertToCyclopsData + predict with newCyclopsData
    fullY <- data.frame(rowId = coh$rowId, y = coh$treatment)
    fullCy <- Cyclops::convertToCyclopsData(
      outcomes = fullY,
      covariates = cov[, c("rowId", "covariateId", "covariateValue")],
      modelType = "lr", addIntercept = TRUE
    )
    ps2 <- predict(fit, newCyclopsData = fullCy, type = "response")
    coh$ps <- ps2
    return(coh)
  }
  fitCoh
}

# -----------------------------------------------------------------------------
# 1:1 greedy match with caliper = 0.2 * SD(logit PS)
# -----------------------------------------------------------------------------
matchOne <- function(cohPs, nMatches = 1, caliperMult = 0.2) {
  cohPs$logitPs <- log(pmax(cohPs$ps, 1e-8) / pmax(1 - cohPs$ps, 1e-8))
  sdL <- sd(cohPs$logitPs)
  caliper <- caliperMult * sdL
  cat(sprintf("  caliper = %.3f × SD(%.4f) = %.4f\n", caliperMult, sdL, caliper))

  tgt <- cohPs[cohPs$treatment == 1, ]
  cmp <- cohPs[cohPs$treatment == 0, ]
  if (nrow(tgt) <= nrow(cmp)) { anchor <- tgt; pool <- cmp; reversed <- FALSE }
  else                         { anchor <- cmp; pool <- tgt; reversed <- TRUE }

  cat(sprintf("  match anchor=%d × %d from pool=%d\n", nrow(anchor), nMatches, nrow(pool)))
  set.seed(42)
  order_a <- sample(nrow(anchor))
  used <- logical(nrow(pool))
  mA <- integer(0); mP <- integer(0)
  pLogit <- pool$logitPs
  for (ai in order_a) {
    aL <- anchor$logitPs[ai]
    ds <- abs(pLogit - aL)
    cand <- which(ds <= caliper & !used)
    if (!length(cand)) next
    nPick <- min(nMatches, length(cand))
    best <- cand[order(ds[cand])[1:nPick]]
    mA <- c(mA, rep(ai, length(best)))
    mP <- c(mP, best)
    used[best] <- TRUE
  }
  matched <- rbind(anchor[unique(mA), ], pool[mP, ])
  cat(sprintf("  matched: anchors=%d, pool=%d (%.1f:1)\n",
              length(unique(mA)), length(mP), length(mP) / max(length(unique(mA)), 1)))
  matched
}

# -----------------------------------------------------------------------------
# Site-stratified Cox per outcome
# -----------------------------------------------------------------------------
coxPerOutcome <- function(matched, outcomes, outcomeIds, riskStart = 1, riskEnd = 3650) {
  res <- data.frame()
  for (oid in outcomeIds) {
    oc_i <- outcomes[outcomes$outcomeId == oid & !is.na(outcomes$daysToEvent) & outcomes$daysToEvent >= riskStart & outcomes$daysToEvent <= riskEnd, ]
    if (nrow(oc_i) == 0) {
      res <- rbind(res, data.frame(outcomeId = oid, nT = 0, nC = 0, evT = 0, evC = 0,
                                    hr = NA, ciLb = NA, ciUb = NA, logHr = NA, seLogHr = NA, p = NA,
                                    stringsAsFactors = FALSE))
      next
    }
    firstEv <- aggregate(daysToEvent ~ rowId, data = oc_i, FUN = min)
    names(firstEv) <- c("rowId", "tte")

    d <- merge(matched[, c("rowId", "treatment", "daysToObsEnd", "site")], firstEv, by = "rowId", all.x = TRUE)
    d$maxFU <- pmin(d$daysToObsEnd, riskEnd)
    d <- d[d$maxFU > 0, ]
    d$event <- as.integer(!is.na(d$tte) & d$tte <= d$maxFU)
    d$time <- ifelse(d$event == 1, d$tte, d$maxFU)
    d$time <- pmax(d$time, 0.5)

    nT <- sum(d$treatment == 1); nC <- sum(d$treatment == 0)
    evT <- sum(d$event[d$treatment == 1]); evC <- sum(d$event[d$treatment == 0])

    if (evT + evC < 2) {
      res <- rbind(res, data.frame(outcomeId = oid, nT = nT, nC = nC, evT = evT, evC = evC,
                                    hr = NA, ciLb = NA, ciUb = NA, logHr = NA, seLogHr = NA, p = NA,
                                    stringsAsFactors = FALSE))
      next
    }
    tryCatch({
      nSites <- length(unique(d$site))
      if (nSites > 1) {
        fit <- coxph(Surv(time, event) ~ treatment + strata(site), data = d)
      } else {
        fit <- coxph(Surv(time, event) ~ treatment, data = d)
      }
      co <- summary(fit)$coefficients
      hr <- exp(co["treatment", "coef"])
      seL <- co["treatment", "se(coef)"]
      ciLb <- exp(co["treatment", "coef"] - 1.96 * seL)
      ciUb <- exp(co["treatment", "coef"] + 1.96 * seL)
      p <- co["treatment", "Pr(>|z|)"]
      res <- rbind(res, data.frame(outcomeId = oid, nT = nT, nC = nC, evT = evT, evC = evC,
                                    hr = hr, ciLb = ciLb, ciUb = ciUb,
                                    logHr = co["treatment","coef"], seLogHr = seL, p = p,
                                    stringsAsFactors = FALSE))
    }, error = function(e) {
      res <<- rbind(res, data.frame(outcomeId = oid, nT = nT, nC = nC, evT = evT, evC = evC,
                                     hr = NA, ciLb = NA, ciUb = NA, logHr = NA, seLogHr = NA, p = NA,
                                     stringsAsFactors = FALSE))
    })
  }
  res
}

# -----------------------------------------------------------------------------
# NC calibration per comparator
# -----------------------------------------------------------------------------
calibrate <- function(primRes, ncRes) {
  # Filter NC: require finite logHr/seLogHr AND minimum events (evT+evC >= 5) AND |logHr| < log(10)
  nc <- ncRes[!is.na(ncRes$logHr) & !is.na(ncRes$seLogHr) &
              is.finite(ncRes$logHr) & is.finite(ncRes$seLogHr) &
              (ncRes$evT + ncRes$evC) >= 5 &
              abs(ncRes$logHr) < log(10), ]
  cat(sprintf("  NC usable for calibration: %d / %d (filter: events>=5, |logHR|<log(10))\n", nrow(nc), nrow(ncRes)))
  primRes$calHr <- NA_real_; primRes$calCiLb <- NA_real_; primRes$calCiUb <- NA_real_; primRes$calP <- NA_real_
  if (nrow(nc) < 5) {
    cat("  Too few NC — skip calibration\n")
    return(primRes)
  }
  # fitNull for null-distribution mean/sd (method of moments)
  null <- tryCatch(fitNull(nc$logHr, nc$seLogHr),
                   error = function(e) { cat("  fitNull error:", conditionMessage(e), "\n"); NULL })
  if (is.null(null)) return(primRes)
  nullMean <- as.numeric(null[1]); nullSd <- as.numeric(null[2])
  cat(sprintf("  Null (method-of-moments): mean=%.3f, sd=%.3f  (→ HR bias ≈ %.2f)\n",
              nullMean, nullSd, exp(nullMean)))

  # Direct Schuemie 2014 calibration formula (avoid broken calibrateConfidenceInterval):
  #   calLogHr = logHr - nullMean
  #   calSe    = sqrt(seLogHr^2 + nullSd^2)
  #   calCI    = calLogHr ± z * calSe
  #   calP     = 2 * pnorm(-|calLogHr|/calSe)
  z <- qnorm(0.975)  # 1.96 for 95% CI
  for (i in seq_len(nrow(primRes))) {
    lh <- primRes$logHr[i]; se <- primRes$seLogHr[i]
    if (is.na(lh) || is.na(se) || !is.finite(lh) || !is.finite(se)) next
    calLh <- lh - nullMean
    calSe <- sqrt(se^2 + nullSd^2)
    primRes$calHr[i]   <- exp(calLh)
    primRes$calCiLb[i] <- exp(calLh - z * calSe)
    primRes$calCiUb[i] <- exp(calLh + z * calSe)
    primRes$calP[i]    <- 2 * pnorm(-abs(calLh) / calSe)
  }
  # Also try package's calibrateP (which works even though CI is broken)
  for (i in seq_len(nrow(primRes))) {
    if (!is.na(primRes$calP[i]) && is.na(primRes$logHr[i])) next
  }
  primRes
}

# =============================================================================
# MAIN
# =============================================================================
summary_all <- data.frame()

for (compCfg in COMPARATORS) {
  cid <- compCfg$id; cname <- compCfg$name
  cat(paste0("\n", strrep("=", 70), "\n"))
  cat(sprintf("COMPARATOR: %s (c=%d)\n", cname, cid))
  cat(paste0(strrep("=", 70), "\n"))

  # 1. Build pooled dataset
  pool <- buildPooled(cid)
  cat(sprintf("\nPooled: cohorts=%d (T=%d, C=%d), outcome rows=%d, outcome IDs=%d\n",
              nrow(pool$cohorts), sum(pool$cohorts$treatment == 1),
              sum(pool$cohorts$treatment == 0), nrow(pool$outcomes),
              length(unique(pool$outcomes$outcomeId))))

  # 2. PS fit
  cat("\n[PS fit]\n")
  psCoh <- fitPs(pool)

  # 3. Match 1:1
  cat("\n[1:1 match]\n")
  matched <- matchOne(psCoh, nMatches = 1, caliperMult = 0.2)

  # Which outcomes are NC vs primary?
  allOc <- unique(pool$outcomes$outcomeId)
  ncIds <- setdiff(allOc, ALL_PRIMARY)
  cat(sprintf("Outcomes: primary candidates=%d, NC=%d\n", sum(ALL_PRIMARY %in% allOc), length(ncIds)))

  # 4. Cox primary
  cat("\n[Cox primary]\n")
  primRes <- coxPerOutcome(matched, pool$outcomes, intersect(ALL_PRIMARY, allOc))
  cat(sprintf("  primary done: %d rows, %d with HR\n", nrow(primRes), sum(!is.na(primRes$hr))))

  # 5. Cox NC
  cat("\n[Cox NC]\n")
  ncRes <- coxPerOutcome(matched, pool$outcomes, ncIds)
  cat(sprintf("  NC done: %d rows, %d with HR\n", nrow(ncRes), sum(!is.na(ncRes$hr))))

  # 6. Calibrate
  cat("\n[Calibration]\n")
  primRes <- calibrate(primRes, ncRes)
  primRes$comparator <- cname; primRes$comparatorId <- cid
  primRes$outcomeName <- OUTCOME_NAMES[as.character(primRes$outcomeId)]

  summary_all <- rbind(summary_all, primRes)

  # Save intermediate CSV
  write.csv(primRes, file.path(OUT_DIR, sprintf("v4_nofilter_primary_c%d_%s.csv", cid, cname)), row.names = FALSE)
  write.csv(ncRes,   file.path(OUT_DIR, sprintf("v4_nofilter_nc_c%d_%s.csv", cid, cname)), row.names = FALSE)
}

# Final combined output
write.csv(summary_all, file.path(OUT_DIR, "v4_nofilter_summary.csv"), row.names = FALSE)
cat(sprintf("\n\n=== DONE ===\nOutput: %s\n", OUT_DIR))
cat(sprintf("Total rows: %d\n", nrow(summary_all)))

# Print top results
cat("\n=== Significant (p<0.05) results after calibration ===\n")
sig <- summary_all[!is.na(summary_all$calP) & summary_all$calP < 0.05, c("comparator","outcomeId","outcomeName","evT","evC","hr","ciLb","ciUb","calHr","calCiLb","calCiUb","calP")]
sig <- sig[order(sig$calP), ]
print(sig)
