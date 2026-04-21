# =============================================================================
# v4 LOSO (Leave-One-Site-Out) Sensitivity Analysis
#
# For each of the 16 sites, drop that site and re-run the 15-site pipeline
# (PS fit + match + Cox for the 32 combined primary outcomes, both comparators).
# NC calibration uses the LOSO-specific null fit so each run is fully independent.
#
# Functions are copied verbatim from v4_main_365d_analysis_v2_combined.R to
# guarantee identical pipeline to the main analysis.
# =============================================================================
Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
suppressPackageStartupMessages({
  library(Cyclops); library(EmpiricalCalibration); library(survival)
  library(DBI); library(RSQLite); library(dplyr)
})

WORKSPACE <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_ipd_workspace"
OUT_DIR   <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output"

ALL_SITES <- c("AUMC","CHNUH","DCMC","GNUCH","GNUH","HUMC","ISH","JCMJ","KDH","KHNMC","KWMC","SCHBC","SCHCA","SCHGM","SCHSU","WKUH")
ANALYSES <- c("v4_1a_cbc_wbc","v4_1b_cbc_rbc","v4_2_chem_hepa","v4_3_meta_endo")
COMPARATORS <- list(list(id = 1074, name = "Chole"), list(id = 1121, name = "Hernia"))
LOOKBACK_DAYS <- 365

PRIMARY_OUTCOMES <- list(
  v4_1a_cbc_wbc  = c(1357, 1390, 1391, 1392, 1360, 1385, 1373, 1374),
  v4_1b_cbc_rbc  = c(1375, 1362, 1368, 1358, 1387, 1395, 1394, 1393),
  v4_2_chem_hepa = c(1370, 1369, 1364, 1365, 1363, 1400, 1366, 1381, 1384, 1397, 1396),
  v4_3_meta_endo = c(1378, 1379, 1402, 1401, 1367, 1399, 1398, 1404)
)
OUTCOME_NAMES <- c(
  "1357"="WBC_high",
  "1360"="Lympho_pct_low","1385"="Lympho_pct_high",
  "1362"="Mono_high","1368"="Baso_pct_high",
  "1358"="MCV_low","1387"="MCV_high","1395"="RDW_high",
  "1394"="Platelet_low","1393"="Platelet_high",
  "1364"="ALT_high","1365"="AST_high","1363"="ALP_high",
  "1400"="TotBili_high","1366"="Albumin_low","1381"="HbA1c_high",
  "1384"="LDL_high","1397"="TG_high","1396"="TC_high",
  "1378"="GlucDM","1379"="GlucPreDM",
  "1402"="TotProt_low","1401"="TotProt_high",
  "1367"="BUN_high","1399"="TSH_low","1398"="TSH_high","1404"="VitD_low",
  "9001"="CRP_high","9005"="Neutrophilia_any","9006"="Eosinophilia_any"
)
DUAL_UNIT_MAP <- list(
  "9001" = c(1370, 1369),
  "9005" = c(1392, 1390, 1391),
  "9006" = c(1375, 1373, 1374)
)
DUAL_UNIT_ORIG_IDS <- unname(unlist(DUAL_UNIT_MAP))
ALL_PRIMARY_RAW <- unname(as.integer(unlist(PRIMARY_OUTCOMES)))
ALL_PRIMARY <- c(setdiff(ALL_PRIMARY_RAW, DUAL_UNIT_ORIG_IDS), as.integer(names(DUAL_UNIT_MAP)))

relabelDualUnit <- function(outcomes_df) {
  for (pseudo in names(DUAL_UNIT_MAP)) {
    outcomes_df$outcomeId[outcomes_df$outcomeId %in% DUAL_UNIT_MAP[[pseudo]]] <- as.integer(pseudo)
  }
  outcomes_df
}

# ---- Functions (verbatim from v4_main_365d_analysis_v2_combined.R) ----
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
  DBI::dbDisconnect(con); res
}

buildPooled <- function(comparatorId, sites) {
  allC <- list(); allO <- list(); allCov <- list(); covRef <- list()
  for (si in seq_along(sites)) {
    site <- sites[si]; offset <- (si - 1) * 100000000L
    cm_1a <- loadCm(site, "v4_1a_cbc_wbc", comparatorId); if (is.null(cm_1a)) next
    cohorts <- cm_1a$cohorts
    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$personSeqId <- NULL; cohorts$site <- site
    covA <- cm_1a$covariates; covA$rowId <- as.integer(covA$rowId) + offset
    siteOc <- list()
    for (a in ANALYSES) {
      cm_a <- loadCm(site, a, comparatorId); if (is.null(cm_a)) next
      oc <- cm_a$outcomes; oc$rowId <- as.integer(oc$rowId) + offset
      siteOc[[a]] <- oc
    }
    oc_all <- bind_rows(siteOc) %>% distinct(rowId, outcomeId, daysToEvent, .keep_all = TRUE)
    allC[[site]] <- cohorts; allO[[site]] <- oc_all; allCov[[site]] <- covA
    covRef[[length(covRef)+1]] <- cm_1a$covariateRef
  }
  list(cohorts = bind_rows(allC), outcomes = bind_rows(allO),
       covariates = bind_rows(allCov),
       covariateRef = bind_rows(covRef) %>% distinct(covariateId, .keep_all = TRUE))
}

applyFullUnion365 <- function(pool, primaryIds, lookbackDays) {
  prior_rows <- pool$outcomes %>%
    filter(outcomeId %in% primaryIds, daysToEvent < 0, daysToEvent >= -lookbackDays)
  prior <- unique(prior_rows$rowId)
  n_before <- nrow(pool$cohorts)
  pool$cohorts <- pool$cohorts[!pool$cohorts$rowId %in% prior, ]
  pool$outcomes <- pool$outcomes[!pool$outcomes$rowId %in% prior, ]
  pool$covariates <- pool$covariates[!pool$covariates$rowId %in% prior, ]
  cat(sprintf("  Filter[%dd]: excluded %d, kept %d/%d (%.1f%%)\n",
              lookbackDays, length(prior), nrow(pool$cohorts), n_before,
              100*nrow(pool$cohorts)/n_before))
  pool
}

fitPs <- function(pool, maxCompFit = 150000L) {
  coh <- pool$cohorts; cov <- pool$covariates
  nC <- sum(coh$treatment == 0)
  if (nC > maxCompFit) {
    set.seed(42)
    sampled <- sample(coh$rowId[coh$treatment == 0], maxCompFit)
    fitIds <- c(coh$rowId[coh$treatment == 1], sampled)
    fitCoh <- coh[coh$rowId %in% fitIds, ]
    fitCov <- cov[cov$rowId %in% fitIds, ]
  } else { fitCoh <- coh; fitCov <- cov }
  outY <- data.frame(rowId = fitCoh$rowId, y = fitCoh$treatment)
  cyD <- Cyclops::convertToCyclopsData(outY, fitCov[, c("rowId","covariateId","covariateValue")],
                                        modelType = "lr", addIntercept = TRUE)
  prior <- Cyclops::createPrior("laplace", useCrossValidation = TRUE, variance = 1,
                                 exclude = 0, forceIntercept = FALSE)
  ctrl <- Cyclops::createControl(maxIterations = 1000, tolerance = 2e-7, convergenceType = "gradient",
                                  cvType = "auto", fold = 10, seed = 42, noiseLevel = "quiet")
  t0 <- proc.time()
  fit <- Cyclops::fitCyclopsModel(cyD, prior = prior, control = ctrl)
  cat(sprintf("  Cyclops fit: %.1fs\n", (proc.time() - t0)[3]))
  if (nC > maxCompFit) {
    fullY <- data.frame(rowId = coh$rowId, y = coh$treatment)
    fullCy <- Cyclops::convertToCyclopsData(fullY, cov[, c("rowId","covariateId","covariateValue")],
                                             modelType = "lr", addIntercept = TRUE)
    coh$ps <- predict(fit, newCyclopsData = fullCy, type = "response")
    return(coh)
  }
  fitCoh$ps <- predict(fit, type = "response")
  fitCoh
}

matchOne <- function(cohPs, caliperMult = 0.2) {
  cohPs$logitPs <- log(pmax(cohPs$ps, 1e-8) / pmax(1 - cohPs$ps, 1e-8))
  caliper <- caliperMult * sd(cohPs$logitPs)
  tgt <- cohPs[cohPs$treatment == 1, ]; cmp <- cohPs[cohPs$treatment == 0, ]
  if (nrow(tgt) <= nrow(cmp)) { anchor <- tgt; pool <- cmp }
  else                        { anchor <- cmp; pool <- tgt }
  set.seed(42); order_a <- sample(nrow(anchor))
  used <- logical(nrow(pool)); mA <- integer(0); mP <- integer(0); pL <- pool$logitPs
  for (ai in order_a) {
    ds <- abs(pL - anchor$logitPs[ai])
    cand <- which(ds <= caliper & !used); if (!length(cand)) next
    best <- cand[order(ds[cand])[1]]
    mA <- c(mA, ai); mP <- c(mP, best); used[best] <- TRUE
  }
  matched <- rbind(anchor[unique(mA), ], pool[mP, ])
  cat(sprintf("  matched: %d pairs\n", length(unique(mA))))
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
      co <- summary(fit)$coefficients; seL <- co["treatment","se(coef)"]
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

# =============================================================================
# LOSO MAIN LOOP
# =============================================================================
t0 <- proc.time()
loso_all <- data.frame()

for (drop_site in ALL_SITES) {
  sites_sub <- setdiff(ALL_SITES, drop_site)
  cat(sprintf("\n\n========== DROP %s (keep %d sites) ==========\n", drop_site, length(sites_sub)))

  for (comp in COMPARATORS) {
    cid <- comp$id; cname <- comp$name
    cat(sprintf("\n--- %s (c=%d) ---\n", cname, cid))
    pool <- buildPooled(cid, sites_sub)
    cat(sprintf("  Pooled: T=%d, C=%d\n", sum(pool$cohorts$treatment==1), sum(pool$cohorts$treatment==0)))
    pool_fu <- applyFullUnion365(pool, ALL_PRIMARY_RAW, LOOKBACK_DAYS)
    psCoh <- fitPs(pool_fu)
    matched <- matchOne(psCoh); n_matched <- nrow(matched)/2

    pool_fu$outcomes <- relabelDualUnit(pool_fu$outcomes)

    prim <- coxOne(matched, pool_fu$outcomes, ALL_PRIMARY, 1, 3650)
    prim$outcomeName <- OUTCOME_NAMES[as.character(prim$outcomeId)]

    allOc <- unique(pool_fu$outcomes$outcomeId)
    ncIds <- setdiff(allOc, ALL_PRIMARY)
    ncRes <- coxOne(matched, pool_fu$outcomes, ncIds, 1, 3650)
    nc <- ncRes[!is.na(ncRes$logHr) & !is.na(ncRes$seLogHr) &
                is.finite(ncRes$logHr) & is.finite(ncRes$seLogHr) &
                (ncRes$evT + ncRes$evC) >= 5 & abs(ncRes$logHr) < log(10), ]
    if (nrow(nc) >= 5) {
      nullD <- fitNull(nc$logHr, nc$seLogHr)
      nullMean <- as.numeric(nullD[1]); nullSd <- as.numeric(nullD[2])
    } else {
      nullMean <- 0; nullSd <- 0
    }
    cat(sprintf("  Null: mean=%.3f, sd=%.3f (n_nc=%d)\n", nullMean, nullSd, nrow(nc)))

    z <- qnorm(0.975)
    prim$calHr <- NA_real_; prim$calCiLb <- NA_real_; prim$calCiUb <- NA_real_; prim$calP <- NA_real_
    for (i in seq_len(nrow(prim))) {
      lh <- prim$logHr[i]; se <- prim$seLogHr[i]
      if (is.na(lh) || is.na(se)) next
      calLh <- lh - nullMean; calSe <- sqrt(se^2 + nullSd^2)
      prim$calHr[i]   <- exp(calLh)
      prim$calCiLb[i] <- exp(calLh - z*calSe)
      prim$calCiUb[i] <- exp(calLh + z*calSe)
      prim$calP[i]    <- 2 * pnorm(-abs(calLh)/calSe)
    }
    prim$comparator <- cname
    prim$dropped_site <- drop_site
    prim$null_mean <- nullMean; prim$null_sd <- nullSd; prim$n_nc <- nrow(nc)
    prim$n_matched <- n_matched
    loso_all <- rbind(loso_all, prim)
  }

  elapsed <- (proc.time()-t0)[3]/60
  cat(sprintf("\n  >> elapsed so far: %.1f min (dropped %d/%d sites)\n",
              elapsed, which(ALL_SITES==drop_site), length(ALL_SITES)))
  write.csv(loso_all, file.path(OUT_DIR, "v4_loso_primary_v3_partial.csv"), row.names = FALSE)
}

write.csv(loso_all, file.path(OUT_DIR, "v4_loso_primary_v3.csv"), row.names = FALSE)
cat(sprintf("\n\n=== LOSO complete ===\nTotal rows: %d\nTotal runtime: %.1f min\n",
            nrow(loso_all), (proc.time()-t0)[3]/60))
