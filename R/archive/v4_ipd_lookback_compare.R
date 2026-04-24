# ⚠️  DEPRECATED 2026-04-24 — superseded by R/lib/ipd_pooled.R + driver pattern.
# Kept for reference. See docs/system_knowledge_base.md §7.2.
# =============================================================================
# Compare Full Union with lookback windows: 90d vs 365d
# Run same S-C/D/H/F for each lookback → produce comparison table
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
ALL_PRIMARY <- unname(as.integer(unlist(PRIMARY_OUTCOMES)))

# ---- Functions (same as v4_ipd_supplemental.R) ----
loadCm <- function(siteCode, analysis, comparatorId) {
  d <- file.path(WORKSPACE, siteCode, analysis, sprintf("CmData_l1_t1072_c%d", comparatorId))
  sqf <- list.files(d, pattern = "\\.sqlite$", full.names = TRUE)[1]
  if (is.na(sqf)) return(NULL)
  con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
  res <- list(
    cohorts = DBI::dbReadTable(con, "cohorts"),
    outcomes = DBI::dbReadTable(con, "outcomes"),
    covariates = DBI::dbReadTable(con, "covariates"),
    covariateRef = DBI::dbReadTable(con, "covariateRef")
  )
  DBI::dbDisconnect(con)
  res
}

buildPooled <- function(comparatorId) {
  allCohorts <- list(); allOutcomes <- list(); allCov <- list(); covRef <- list()
  for (si in seq_along(SITES)) {
    site <- SITES[si]
    offset <- (si - 1) * 100000000L
    cm_1a <- loadCm(site, "v4_1a_cbc_wbc", comparatorId)
    if (is.null(cm_1a)) next
    cohorts <- cm_1a$cohorts
    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$personSeqId <- NULL
    cohorts$site <- site
    covA <- cm_1a$covariates
    covA$rowId <- as.integer(covA$rowId) + offset
    siteOc <- list()
    for (a in ANALYSES) {
      cm_a <- loadCm(site, a, comparatorId)
      if (is.null(cm_a)) next
      oc <- cm_a$outcomes
      oc$rowId <- as.integer(oc$rowId) + offset
      siteOc[[a]] <- oc
    }
    oc_all <- bind_rows(siteOc) %>% distinct(rowId, outcomeId, daysToEvent, .keep_all = TRUE)
    allCohorts[[site]] <- cohorts
    allOutcomes[[site]] <- oc_all
    allCov[[site]] <- covA
    covRef[[length(covRef)+1]] <- cm_1a$covariateRef
  }
  list(
    cohorts = bind_rows(allCohorts),
    outcomes = bind_rows(allOutcomes),
    covariates = bind_rows(allCov),
    covariateRef = bind_rows(covRef) %>% distinct(covariateId, .keep_all = TRUE)
  )
}

applyFullUnion <- function(pool, primaryIds, lookbackDays = NULL) {
  if (is.null(lookbackDays)) {
    prior_rows <- pool$outcomes %>% filter(outcomeId %in% primaryIds, daysToEvent < 0)
    lb_label <- "unlimited"
  } else {
    prior_rows <- pool$outcomes %>%
      filter(outcomeId %in% primaryIds, daysToEvent < 0, daysToEvent >= -lookbackDays)
    lb_label <- sprintf("%dd", lookbackDays)
  }
  prior <- unique(prior_rows$rowId)
  n_before <- nrow(pool$cohorts)
  pool$cohorts    <- pool$cohorts[!pool$cohorts$rowId %in% prior, ]
  pool$outcomes   <- pool$outcomes[!pool$outcomes$rowId %in% prior, ]
  pool$covariates <- pool$covariates[!pool$covariates$rowId %in% prior, ]
  n_after <- nrow(pool$cohorts)
  cat(sprintf("  [%s] excluded %d rowIds, kept %d/%d (%.1f%%)\n",
              lb_label, length(prior), n_after, n_before, 100 * n_after / n_before))
  pool
}

fitPs <- function(pool, maxCompFit = 150000L) {
  coh <- pool$cohorts; cov <- pool$covariates
  nT <- sum(coh$treatment == 1); nC <- sum(coh$treatment == 0)
  if (nC > maxCompFit) {
    set.seed(42)
    compIds <- coh$rowId[coh$treatment == 0]
    sampled <- sample(compIds, maxCompFit)
    fitIds <- c(coh$rowId[coh$treatment == 1], sampled)
    fitCoh <- coh[coh$rowId %in% fitIds, ]
    fitCov <- cov[cov$rowId %in% fitIds, ]
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
    cvType = "auto", fold = 10, seed = 42, noiseLevel = "quiet"
  )
  t0 <- proc.time()
  fit <- Cyclops::fitCyclopsModel(cyData, prior = prior, control = control)
  cat(sprintf("  Cyclops fit: %.1fs\n", (proc.time() - t0)[3]))
  ps <- predict(fit, type = "response"); fitCoh$ps <- ps
  if (nC > maxCompFit) {
    fullY <- data.frame(rowId = coh$rowId, y = coh$treatment)
    fullCy <- Cyclops::convertToCyclopsData(outcomes = fullY,
      covariates = cov[, c("rowId", "covariateId", "covariateValue")],
      modelType = "lr", addIntercept = TRUE)
    ps2 <- predict(fit, newCyclopsData = fullCy, type = "response")
    coh$ps <- ps2
    return(coh)
  }
  fitCoh
}

matchOne <- function(cohPs, caliperMult = 0.2) {
  cohPs$logitPs <- log(pmax(cohPs$ps, 1e-8) / pmax(1 - cohPs$ps, 1e-8))
  sdL <- sd(cohPs$logitPs); caliper <- caliperMult * sdL
  tgt <- cohPs[cohPs$treatment == 1, ]
  cmp <- cohPs[cohPs$treatment == 0, ]
  if (nrow(tgt) <= nrow(cmp)) { anchor <- tgt; pool <- cmp; reversed <- FALSE }
  else                         { anchor <- cmp; pool <- tgt; reversed <- TRUE }
  set.seed(42)
  order_a <- sample(nrow(anchor))
  used <- logical(nrow(pool))
  mA <- integer(0); mP <- integer(0); pLogit <- pool$logitPs
  for (ai in order_a) {
    aL <- anchor$logitPs[ai]
    ds <- abs(pLogit - aL)
    cand <- which(ds <= caliper & !used)
    if (!length(cand)) next
    best <- cand[order(ds[cand])[1]]
    mA <- c(mA, ai); mP <- c(mP, best); used[best] <- TRUE
  }
  matched <- rbind(anchor[unique(mA), ], pool[mP, ])
  cat(sprintf("  matched: anchors=%d, pool=%d\n", length(unique(mA)), length(mP)))
  matched
}

coxOne <- function(matched, outcomes, outcomeIds, riskStart = 1, riskEnd = 3650) {
  res <- data.frame()
  for (oid in outcomeIds) {
    oc_i <- outcomes[outcomes$outcomeId == oid & !is.na(outcomes$daysToEvent) &
                     outcomes$daysToEvent >= riskStart & outcomes$daysToEvent <= riskEnd, ]
    if (nrow(oc_i) == 0) {
      res <- rbind(res, data.frame(outcomeId=oid, nT=0, nC=0, evT=0, evC=0,
                                    hr=NA, ciLb=NA, ciUb=NA, logHr=NA, seLogHr=NA, p=NA))
      next
    }
    firstEv <- aggregate(daysToEvent ~ rowId, data=oc_i, FUN=min)
    names(firstEv) <- c("rowId", "tte")
    d <- merge(matched[, c("rowId","treatment","daysToObsEnd","site")], firstEv, by="rowId", all.x=TRUE)
    d$maxFU <- pmin(d$daysToObsEnd, riskEnd); d <- d[d$maxFU > 0, ]
    d$event <- as.integer(!is.na(d$tte) & d$tte <= d$maxFU)
    d$time <- ifelse(d$event==1, d$tte, d$maxFU); d$time <- pmax(d$time, 0.5)
    nT <- sum(d$treatment==1); nC <- sum(d$treatment==0)
    evT <- sum(d$event[d$treatment==1]); evC <- sum(d$event[d$treatment==0])
    if (evT + evC < 2) {
      res <- rbind(res, data.frame(outcomeId=oid, nT=nT, nC=nC, evT=evT, evC=evC,
                                    hr=NA, ciLb=NA, ciUb=NA, logHr=NA, seLogHr=NA, p=NA))
      next
    }
    new_row <- tryCatch({
      fit <- if (length(unique(d$site))>1) coxph(Surv(time,event)~treatment+strata(site),data=d)
             else coxph(Surv(time,event)~treatment,data=d)
      co <- summary(fit)$coefficients
      seL <- co["treatment","se(coef)"]
      data.frame(outcomeId=oid, nT=nT, nC=nC, evT=evT, evC=evC,
                 hr=exp(co["treatment","coef"]),
                 ciLb=exp(co["treatment","coef"]-1.96*seL),
                 ciUb=exp(co["treatment","coef"]+1.96*seL),
                 logHr=co["treatment","coef"], seLogHr=seL,
                 p=co["treatment","Pr(>|z|)"])
    }, error = function(e) {
      data.frame(outcomeId=oid, nT=nT, nC=nC, evT=evT, evC=evC,
                 hr=NA, ciLb=NA, ciUb=NA, logHr=NA, seLogHr=NA, p=NA)
    })
    res <- rbind(res, new_row)
  }
  res
}

calibratePrimary <- function(primRes, ncRes) {
  nc <- ncRes[!is.na(ncRes$logHr) & !is.na(ncRes$seLogHr) &
              is.finite(ncRes$logHr) & is.finite(ncRes$seLogHr) &
              (ncRes$evT + ncRes$evC) >= 5 & abs(ncRes$logHr) < log(10), ]
  if (nrow(nc) < 5) {
    primRes$calHr <- NA_real_; primRes$calCiLb <- NA_real_; primRes$calCiUb <- NA_real_; primRes$calP <- NA_real_
    return(list(res=primRes, nullMean=NA, nullSd=NA, n_nc=nrow(nc)))
  }
  nullD <- fitNull(nc$logHr, nc$seLogHr)
  nullMean <- as.numeric(nullD[1]); nullSd <- as.numeric(nullD[2])
  z <- qnorm(0.975)
  primRes$calHr <- NA_real_; primRes$calCiLb <- NA_real_; primRes$calCiUb <- NA_real_; primRes$calP <- NA_real_
  for (i in seq_len(nrow(primRes))) {
    lh <- primRes$logHr[i]; se <- primRes$seLogHr[i]
    if (is.na(lh) || is.na(se) || !is.finite(lh) || !is.finite(se)) next
    calLh <- lh - nullMean; calSe <- sqrt(se^2 + nullSd^2)
    primRes$calHr[i]   <- exp(calLh)
    primRes$calCiLb[i] <- exp(calLh - z*calSe)
    primRes$calCiUb[i] <- exp(calLh + z*calSe)
    primRes$calP[i]    <- 2 * pnorm(-abs(calLh)/calSe)
  }
  list(res=primRes, nullMean=nullMean, nullSd=nullSd, n_nc=nrow(nc))
}

eValue <- function(hr, ciLb, ciUb) {
  if (is.na(hr) || !is.finite(hr)) return(c(NA_real_, NA_real_))
  rr <- ifelse(hr >= 1, hr, 1/hr)
  e_point <- rr + sqrt(rr * (rr - 1))
  ci_near1 <- if (hr >= 1) ciLb else 1/ciUb
  if (is.na(ci_near1) || ci_near1 <= 1) e_ci <- 1
  else e_ci <- ci_near1 + sqrt(ci_near1 * (ci_near1 - 1))
  c(e_point, e_ci)
}

# =============================================================================
# MAIN: loop over lookback settings
# =============================================================================
LOOKBACKS <- list(
  list(days = 90, label = "90d"),
  list(days = 365, label = "365d")
)

run_summary_list <- list()
all_primary <- data.frame()

for (lb in LOOKBACKS) {
  cat(paste0("\n", strrep("=", 80), "\n"))
  cat(sprintf("LOOKBACK WINDOW: %s\n", lb$label))
  cat(paste0(strrep("=", 80), "\n"))

  for (compCfg in COMPARATORS) {
    cid <- compCfg$id; cname <- compCfg$name
    cat(sprintf("\n-- %s (c=%d), lookback %s --\n", cname, cid, lb$label))

    pool <- buildPooled(cid)
    n_total <- nrow(pool$cohorts)
    pool_fu <- applyFullUnion(pool, ALL_PRIMARY, lookbackDays = lb$days)
    n_after <- nrow(pool_fu$cohorts)
    if (n_after < 200) {
      cat("  too few after filter, skip\n")
      next
    }
    psCoh <- fitPs(pool_fu)
    matched <- matchOne(psCoh)
    n_matched <- nrow(matched) / 2

    # Primary Cox — use ALL_PRIMARY as full list
    primRes <- coxOne(matched, pool_fu$outcomes, ALL_PRIMARY, 1, 3650)
    primRes$outcomeName <- OUTCOME_NAMES[as.character(primRes$outcomeId)]

    # NC
    allOc <- unique(pool_fu$outcomes$outcomeId)
    ncIds <- setdiff(allOc, ALL_PRIMARY)
    ncRes <- coxOne(matched, pool_fu$outcomes, ncIds, 1, 3650)

    # Calibrate
    cal <- calibratePrimary(primRes, ncRes)
    primRes <- cal$res
    # E-value
    primRes$eval_hr <- NA_real_; primRes$eval_ci <- NA_real_
    for (i in seq_len(nrow(primRes))) {
      ev <- eValue(primRes$hr[i], primRes$ciLb[i], primRes$ciUb[i])
      primRes$eval_hr[i] <- ev[1]; primRes$eval_ci[i] <- ev[2]
    }

    primRes$lookback <- lb$label
    primRes$comparator <- cname; primRes$comparatorId <- cid
    all_primary <- rbind(all_primary, primRes)

    # Summary row
    n_sig_cal <- sum(!is.na(primRes$calP) & primRes$calP < 0.05)
    n_cox_ok <- sum(!is.na(primRes$hr))
    run_summary_list[[length(run_summary_list)+1]] <- data.frame(
      lookback = lb$label,
      comparator = cname,
      n_total_cohort = n_total,
      n_after_filter = n_after,
      pct_kept = round(100 * n_after / n_total, 1),
      n_matched_pairs = n_matched,
      n_outcomes_cox_ok = n_cox_ok,
      n_sig_cal = n_sig_cal,
      null_mean = round(cal$nullMean, 3),
      null_sd = round(cal$nullSd, 3),
      n_nc_used = cal$n_nc,
      stringsAsFactors = FALSE
    )
    cat(sprintf("  summary: kept=%d (%.1f%%), matched=%d, cox_ok=%d/35, sig_cal=%d, null=%.3f±%.3f\n",
                n_after, 100*n_after/n_total, n_matched, n_cox_ok, n_sig_cal,
                cal$nullMean, cal$nullSd))
  }
}

run_summary <- do.call(rbind, run_summary_list)
write.csv(run_summary, file.path(OUT_DIR, "v4_lookback_comparison_summary.csv"), row.names = FALSE)
write.csv(all_primary, file.path(OUT_DIR, "v4_lookback_primary_all.csv"), row.names = FALSE)

cat("\n\n========== COMPARISON SUMMARY ==========\n")
print(run_summary)
cat("\n\nDone. Outputs saved to:", OUT_DIR, "\n")
