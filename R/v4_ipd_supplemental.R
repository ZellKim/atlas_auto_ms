# ⚠️  DEPRECATED 2026-04-24 — superseded by R/lib/ipd_pooled.R + driver pattern.
# Kept for reference. See docs/system_knowledge_base.md §7.2.
# =============================================================================
# v4 IPD Supplemental Analyses (S-C, S-D, S-H, S-F)
# S-C: Full Union prior outcome filter → re-match → Cox
# S-D: Table 1 with SMD (before/after match, before/after Full Union)
# S-H: Time-window Cox (30d / 90d / 1y / 3y / 10y)
# S-F: E-value per primary outcome
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
# Load functions (replicated from v4_ipd_pooled_analysis.R for self-containment)
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

buildPooled <- function(comparatorId) {
  cat(sprintf("\n=== buildPooled c=%d ===\n", comparatorId))
  allCohorts <- list(); allOutcomes <- list(); allCov <- list(); covRef <- list()
  for (si in seq_along(SITES)) {
    site <- SITES[si]
    offset <- (si - 1) * 100000000L
    cm_1a <- loadCm(site, "v4_1a_cbc_wbc", comparatorId)
    if (is.null(cm_1a)) { next }
    cohorts <- cm_1a$cohorts
    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$personSeqId <- NULL
    cohorts$site <- site
    covA <- cm_1a$covariates
    covA$rowId <- as.integer(covA$rowId) + offset
    covRefA <- cm_1a$covariateRef

    siteOc <- list()
    for (a in ANALYSES) {
      cm_a <- loadCm(site, a, comparatorId)
      if (is.null(cm_a)) next
      oc <- cm_a$outcomes
      oc$rowId <- as.integer(oc$rowId) + offset
      siteOc[[a]] <- oc
    }
    oc_all <- bind_rows(siteOc)
    oc_all <- oc_all %>% distinct(rowId, outcomeId, daysToEvent, .keep_all = TRUE)

    cat(sprintf("  %s: cohorts=%d (T=%d, C=%d), outcomes=%d\n",
                site, nrow(cohorts),
                sum(cohorts$treatment == 1), sum(cohorts$treatment == 0),
                nrow(oc_all)))

    allCohorts[[site]] <- cohorts
    allOutcomes[[site]] <- oc_all
    allCov[[site]] <- covA
    covRef[[length(covRef)+1]] <- covRefA
  }
  list(
    cohorts = bind_rows(allCohorts),
    outcomes = bind_rows(allOutcomes),
    covariates = bind_rows(allCov),
    covariateRef = bind_rows(covRef) %>% distinct(covariateId, .keep_all = TRUE)
  )
}

fitPs <- function(pool, maxCompFit = 150000L) {
  coh <- pool$cohorts; cov <- pool$covariates
  nT <- sum(coh$treatment == 1); nC <- sum(coh$treatment == 0)
  cat(sprintf("  PS fit input: T=%d, C=%d\n", nT, nC))
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
    cvType = "auto", fold = 10, lowerLimit = 0.01, upperLimit = 20, seed = 42, noiseLevel = "quiet"
  )
  t0 <- proc.time()
  fit <- Cyclops::fitCyclopsModel(cyData, prior = prior, control = control)
  cat(sprintf("  Cyclops fit: %.1fs\n", (proc.time() - t0)[3]))
  ps <- predict(fit, type = "response")
  fitCoh$ps <- ps
  if (nC > maxCompFit) {
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
  cat(sprintf("  matched: anchors=%d, pool=%d\n", length(unique(mA)), length(mP)))
  matched
}

# =============================================================================
# S-C: Full Union Prior Outcome Filter (with lookback window)
# lookbackDays = NULL → no limit (all prior)
# lookbackDays = 365 → only prior events within 365 days before index
# lookbackDays = 90  → only prior events within 90 days before index
# =============================================================================
applyFullUnion <- function(pool, primaryIds, lookbackDays = NULL) {
  if (is.null(lookbackDays)) {
    prior_rows <- pool$outcomes %>%
      filter(outcomeId %in% primaryIds, daysToEvent < 0)
    lb_label <- "no lookback limit"
  } else {
    prior_rows <- pool$outcomes %>%
      filter(outcomeId %in% primaryIds,
             daysToEvent < 0,
             daysToEvent >= -lookbackDays)
    lb_label <- sprintf("%dd lookback", lookbackDays)
  }
  prior <- unique(prior_rows$rowId)
  cat(sprintf("  Full Union filter [%s]: %d rowIds with prior primary event\n", lb_label, length(prior)))
  cat(sprintf("  Before filter: T=%d, C=%d\n",
              sum(pool$cohorts$treatment==1), sum(pool$cohorts$treatment==0)))
  pool$cohorts    <- pool$cohorts[!pool$cohorts$rowId %in% prior, ]
  pool$outcomes   <- pool$outcomes[!pool$outcomes$rowId %in% prior, ]
  pool$covariates <- pool$covariates[!pool$covariates$rowId %in% prior, ]
  n_after <- nrow(pool$cohorts)
  n_total <- n_after + length(prior)
  cat(sprintf("  After filter : T=%d, C=%d (kept %.1f%%)\n",
              sum(pool$cohorts$treatment==1), sum(pool$cohorts$treatment==0),
              100 * n_after / n_total))
  pool
}

# =============================================================================
# S-H: Time-window Cox
# =============================================================================
coxWindow <- function(matched, outcomes, outcomeIds, wStart, wEnd) {
  res <- data.frame()
  for (oid in outcomeIds) {
    oc_i <- outcomes[outcomes$outcomeId == oid &
                     !is.na(outcomes$daysToEvent) &
                     outcomes$daysToEvent >= wStart &
                     outcomes$daysToEvent <= wEnd, ]
    if (nrow(oc_i) == 0) {
      res <- rbind(res, data.frame(outcomeId=oid, window=sprintf("%dd-%dd", wStart, wEnd),
                                    nT=0, nC=0, evT=0, evC=0, hr=NA, ciLb=NA, ciUb=NA,
                                    logHr=NA, seLogHr=NA, p=NA, stringsAsFactors=FALSE)); next
    }
    firstEv <- aggregate(daysToEvent ~ rowId, data=oc_i, FUN=min)
    names(firstEv) <- c("rowId", "tte")
    d <- merge(matched[, c("rowId","treatment","daysToObsEnd","site")], firstEv, by="rowId", all.x=TRUE)
    d$maxFU <- pmin(d$daysToObsEnd, wEnd)
    d <- d[d$maxFU >= wStart, ]
    if (nrow(d) == 0) {
      res <- rbind(res, data.frame(outcomeId=oid, window=sprintf("%dd-%dd", wStart, wEnd),
                                    nT=0, nC=0, evT=0, evC=0, hr=NA, ciLb=NA, ciUb=NA,
                                    logHr=NA, seLogHr=NA, p=NA, stringsAsFactors=FALSE)); next
    }
    d$event <- as.integer(!is.na(d$tte) & d$tte <= d$maxFU & d$tte >= wStart)
    d$time <- ifelse(d$event==1, d$tte, d$maxFU)
    d$time <- pmax(d$time, wStart + 0.5)
    nT <- sum(d$treatment==1); nC <- sum(d$treatment==0)
    evT <- sum(d$event[d$treatment==1]); evC <- sum(d$event[d$treatment==0])
    if (evT + evC < 2) {
      res <- rbind(res, data.frame(outcomeId=oid, window=sprintf("%dd-%dd", wStart, wEnd),
                                    nT=nT, nC=nC, evT=evT, evC=evC, hr=NA, ciLb=NA, ciUb=NA,
                                    logHr=NA, seLogHr=NA, p=NA, stringsAsFactors=FALSE)); next
    }
    # Use tryCatch that returns the data.frame, then local rbind (avoid <<- scope bug)
    new_row <- tryCatch({
      fit <- if (length(unique(d$site)) > 1)
        coxph(Surv(time, event) ~ treatment + strata(site), data=d)
      else
        coxph(Surv(time, event) ~ treatment, data=d)
      co <- summary(fit)$coefficients
      hr <- exp(co["treatment","coef"]); seL <- co["treatment","se(coef)"]
      data.frame(outcomeId=oid, window=sprintf("%dd-%dd", wStart, wEnd),
                 nT=nT, nC=nC, evT=evT, evC=evC,
                 hr=hr, ciLb=exp(co["treatment","coef"]-1.96*seL),
                 ciUb=exp(co["treatment","coef"]+1.96*seL),
                 logHr=co["treatment","coef"], seLogHr=seL,
                 p=co["treatment","Pr(>|z|)"],
                 stringsAsFactors=FALSE)
    }, error = function(e) {
      data.frame(outcomeId=oid, window=sprintf("%dd-%dd", wStart, wEnd),
                 nT=nT, nC=nC, evT=evT, evC=evC, hr=NA, ciLb=NA, ciUb=NA,
                 logHr=NA, seLogHr=NA, p=NA, stringsAsFactors=FALSE)
    })
    res <- rbind(res, new_row)
  }
  res
}

# =============================================================================
# S-F: E-value (VanderWeele 2017)
# =============================================================================
eValue <- function(hr, ciLb, ciUb) {
  if (is.na(hr) || !is.finite(hr)) return(c(NA_real_, NA_real_))
  rr <- ifelse(hr >= 1, hr, 1/hr)
  e_point <- rr + sqrt(rr * (rr - 1))
  # E-value for CI: use CI bound closer to 1
  if (hr >= 1) {
    ci_near1 <- ciLb
  } else {
    ci_near1 <- 1/ciUb
  }
  if (is.na(ci_near1) || ci_near1 <= 1) {
    e_ci <- 1  # CI crosses null
  } else {
    e_ci <- ci_near1 + sqrt(ci_near1 * (ci_near1 - 1))
  }
  c(e_point, e_ci)
}

# =============================================================================
# S-D: Table 1 with SMD
# =============================================================================
generateTable1 <- function(cohorts, covariates, covariateRef, label = "Table1") {
  # Top frequency covariates (binary)
  covRef <- covariateRef %>%
    rename(covariateName = covariateName) %>%
    select(covariateId, covariateName)
  cov_long <- covariates %>%
    inner_join(cohorts[, c("rowId","treatment")], by="rowId")
  # For each covariate, compute proportion per treatment group + SMD
  cov_summary <- cov_long %>%
    group_by(covariateId, treatment) %>%
    summarise(n_present = n_distinct(rowId), .groups = "drop") %>%
    left_join(
      cohorts %>% group_by(treatment) %>% summarise(n_total = n_distinct(rowId), .groups="drop"),
      by = "treatment"
    ) %>%
    mutate(prop = n_present / n_total) %>%
    select(covariateId, treatment, prop, n_present, n_total) %>%
    tidyr::pivot_wider(id_cols = covariateId,
                       names_from = treatment,
                       values_from = c(prop, n_present),
                       names_sep = "_t")
  # SMD: for binary covariate with p0, p1: SMD = (p1-p0)/sqrt((p1(1-p1)+p0(1-p0))/2)
  cov_summary <- cov_summary %>%
    mutate(
      p_t = ifelse(is.na(prop_t1), 0, prop_t1),
      p_c = ifelse(is.na(prop_t0), 0, prop_t0),
      smd = (p_t - p_c) / sqrt((p_t*(1-p_t) + p_c*(1-p_c))/2 + 1e-10)
    ) %>%
    left_join(covRef, by = "covariateId") %>%
    arrange(desc(abs(smd)))
  # Top 50
  top <- head(cov_summary, 100) %>%
    transmute(covariateId, covariateName,
              n_T = n_present_t1, n_C = n_present_t0,
              prop_T = round(p_t, 4), prop_C = round(p_c, 4),
              SMD = round(smd, 4))
  outPath <- file.path(OUT_DIR, sprintf("%s.csv", label))
  write.csv(top, outPath, row.names = FALSE)
  cat(sprintf("  Table1[%s] saved → %s (top 100 by |SMD|)\n", label, outPath))
  top
}

# =============================================================================
# MAIN
# =============================================================================
t_all <- proc.time()
all_summary <- data.frame()
all_tw <- data.frame()
table1_list <- list()

for (compCfg in COMPARATORS) {
  cid <- compCfg$id; cname <- compCfg$name
  cat(paste0("\n", strrep("=", 80), "\n"))
  cat(sprintf("COMPARATOR: %s (c=%d)\n", cname, cid))
  cat(paste0(strrep("=", 80), "\n"))

  # ---- Step 1: Build pooled ----
  pool <- buildPooled(cid)
  cat(sprintf("\nPooled: cohorts=%d (T=%d, C=%d)\n",
              nrow(pool$cohorts), sum(pool$cohorts$treatment==1), sum(pool$cohorts$treatment==0)))

  # ---- Step 2 (S-C): Apply Full Union filter ----
  cat("\n[S-C] Full Union prior outcome filter\n")
  pool_fu <- applyFullUnion(pool, ALL_PRIMARY)

  # ---- Step 3: PS fit on FULL UNION filtered pool ----
  cat("\n[PS fit on Full Union pool]\n")
  psCoh <- fitPs(pool_fu)
  cat(sprintf("\n[1:1 match on Full Union pool]\n"))
  matched <- matchOne(psCoh, nMatches = 1, caliperMult = 0.2)

  # ---- Step 4 (S-D): Table 1 on matched cohort ----
  cat("\n[S-D] Table 1 with SMD (after Full Union + match)\n")
  t1 <- generateTable1(matched, pool_fu$covariates, pool_fu$covariateRef,
                       label = sprintf("v4_funlimited_table1_c%d_%s", cid, cname))
  table1_list[[paste0("c", cid, "_", cname)]] <- t1

  # ---- Step 5: Primary Cox (full risk window 1-3650) ----
  cat("\n[Cox primary on Full Union matched]\n")
  primRes <- coxWindow(matched, pool_fu$outcomes, intersect(ALL_PRIMARY, unique(pool_fu$outcomes$outcomeId)),
                       1, 3650)
  primRes$window <- "1-3650d"
  cat(sprintf("  primary: %d rows, %d with HR\n", nrow(primRes), sum(!is.na(primRes$hr))))

  # ---- Step 6: NC Cox + calibration ----
  cat("\n[NC Cox]\n")
  allOc <- unique(pool_fu$outcomes$outcomeId)
  ncIds <- setdiff(allOc, ALL_PRIMARY)
  ncRes <- coxWindow(matched, pool_fu$outcomes, ncIds, 1, 3650)
  cat(sprintf("  NC: %d rows, %d with HR\n", nrow(ncRes), sum(!is.na(ncRes$hr))))

  # Calibrate
  nc <- ncRes[!is.na(ncRes$logHr) & !is.na(ncRes$seLogHr) &
              is.finite(ncRes$logHr) & is.finite(ncRes$seLogHr) &
              (ncRes$evT + ncRes$evC) >= 5 & abs(ncRes$logHr) < log(10), ]
  cat(sprintf("  NC usable: %d / %d\n", nrow(nc), nrow(ncRes)))
  nullD <- fitNull(nc$logHr, nc$seLogHr)
  nullMean <- as.numeric(nullD[1]); nullSd <- as.numeric(nullD[2])
  cat(sprintf("  Null: mean=%.3f, sd=%.3f (HR bias %.2f)\n", nullMean, nullSd, exp(nullMean)))

  primRes$calHr <- NA_real_; primRes$calCiLb <- NA_real_; primRes$calCiUb <- NA_real_; primRes$calP <- NA_real_
  # S-F: E-value
  primRes$eval_hr <- NA_real_; primRes$eval_ci <- NA_real_
  primRes$cal_eval_hr <- NA_real_; primRes$cal_eval_ci <- NA_real_

  z <- qnorm(0.975)
  for (i in seq_len(nrow(primRes))) {
    lh <- primRes$logHr[i]; se <- primRes$seLogHr[i]
    if (is.na(lh) || is.na(se) || !is.finite(lh) || !is.finite(se)) next
    calLh <- lh - nullMean; calSe <- sqrt(se^2 + nullSd^2)
    primRes$calHr[i]   <- exp(calLh)
    primRes$calCiLb[i] <- exp(calLh - z*calSe)
    primRes$calCiUb[i] <- exp(calLh + z*calSe)
    primRes$calP[i]    <- 2 * pnorm(-abs(calLh)/calSe)
    # E-value raw
    ev <- eValue(primRes$hr[i], primRes$ciLb[i], primRes$ciUb[i])
    primRes$eval_hr[i] <- ev[1]; primRes$eval_ci[i] <- ev[2]
    # E-value calibrated
    ev_c <- eValue(primRes$calHr[i], primRes$calCiLb[i], primRes$calCiUb[i])
    primRes$cal_eval_hr[i] <- ev_c[1]; primRes$cal_eval_ci[i] <- ev_c[2]
  }

  primRes$comparator <- cname; primRes$comparatorId <- cid
  primRes$outcomeName <- OUTCOME_NAMES[as.character(primRes$outcomeId)]
  all_summary <- rbind(all_summary, primRes)

  # ---- Step 7 (S-H): Time-window Cox ----
  cat("\n[S-H] Time-window Cox\n")
  WINDOWS <- list(c(1, 30), c(31, 90), c(91, 365), c(366, 1095), c(1096, 3650))
  for (w in WINDOWS) {
    cat(sprintf("  window %d-%dd\n", w[1], w[2]))
    tw <- coxWindow(matched, pool_fu$outcomes, intersect(ALL_PRIMARY, allOc), w[1], w[2])
    tw$comparator <- cname; tw$comparatorId <- cid
    tw$outcomeName <- OUTCOME_NAMES[as.character(tw$outcomeId)]
    # Calibrate time-window HRs with same null
    tw$calHr <- NA_real_; tw$calCiLb <- NA_real_; tw$calCiUb <- NA_real_; tw$calP <- NA_real_
    for (i in seq_len(nrow(tw))) {
      lh <- tw$logHr[i]; se <- tw$seLogHr[i]
      if (is.na(lh) || is.na(se) || !is.finite(lh) || !is.finite(se)) next
      calLh <- lh - nullMean; calSe <- sqrt(se^2 + nullSd^2)
      tw$calHr[i]   <- exp(calLh)
      tw$calCiLb[i] <- exp(calLh - z*calSe)
      tw$calCiUb[i] <- exp(calLh + z*calSe)
      tw$calP[i]    <- 2 * pnorm(-abs(calLh)/calSe)
    }
    all_tw <- rbind(all_tw, tw)
  }

  # Save per-comparator results
  write.csv(primRes, file.path(OUT_DIR, sprintf("v4_funlimited_primary_c%d_%s.csv", cid, cname)), row.names=FALSE)
  write.csv(ncRes,   file.path(OUT_DIR, sprintf("v4_funlimited_nc_c%d_%s.csv", cid, cname)), row.names=FALSE)
}

# Final CSVs
write.csv(all_summary, file.path(OUT_DIR, "v4_funlimited_summary.csv"), row.names = FALSE)
write.csv(all_tw,      file.path(OUT_DIR, "v4_funlimited_timewindow.csv"), row.names = FALSE)
cat(sprintf("\n\n=== DONE ===\nTotal runtime: %.1f min\n", (proc.time() - t_all)[3] / 60))
cat(sprintf("Output dir: %s\n", OUT_DIR))
cat(sprintf("  v4_funlimited_summary.csv: %d rows (primary w/ unlimited Full Union + E-value)\n", nrow(all_summary)))
cat(sprintf("  v4_funlimited_timewindow.csv: %d rows (5 windows × outcomes × 2 comparators)\n", nrow(all_tw)))
cat("\nDone. Telegram notification will be sent separately.\n")
