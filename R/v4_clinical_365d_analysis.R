# =============================================================================
# v4 Clinical IPD Pooled Analysis (365d Full Union)
# 14 sites, 11 clinical outcomes, 2 comparators
# Uses identical T/C cohorts as biomarker (deterministic from base 212)
# =============================================================================

Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
suppressPackageStartupMessages({
  library(Cyclops); library(EmpiricalCalibration); library(survival)
  library(DBI); library(RSQLite); library(dplyr); library(ggplot2)
})

WORKSPACE <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_clinical_workspace"
OUT_DIR   <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output"
FIG_DIR   <- file.path(OUT_DIR, "figures")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)
dir.create(FIG_DIR, showWarnings = FALSE, recursive = TRUE)

SITES <- c("AUMC","CHNUH","DCMC","GNUCH","GNUH","HUMC","ISH","JCMJ","KDH","KHNMC","KWMC","SCHBC","SCHCA","SCHGM","SCHSU","WKUH")
COMPARATORS <- list(list(id = 1074, name = "Chole"), list(id = 1121, name = "Hernia"))
LOOKBACK_DAYS <- 365

CLINICAL_OUTCOMES <- c(1077, 1078, 1079, 1080, 1090, 1092, 1093, 1094, 1097, 1271, 1285)
OUTCOME_NAMES <- c(
  "1077"="UC", "1078"="CD", "1079"="Asthma", "1080"="AD", "1090"="RA",
  "1092"="CDI", "1093"="PD", "1094"="BilCalc", "1097"="CRC",
  "1271"="AMI_v2", "1285"="T2DM_v3"
)
OUTCOME_CATEGORY <- c(
  "UC"="IBD", "CD"="IBD",
  "Asthma"="Allergic", "AD"="Allergic",
  "RA"="Autoimmune",
  "CDI"="Infection",
  "PD"="Neurologic",
  "BilCalc"="Biliary",
  "CRC"="Oncologic",
  "AMI_v2"="Cardiovascular",
  "T2DM_v3"="Metabolic"
)

# ---- CmData loading ----
loadCm <- function(siteCode, comparatorId) {
  d <- file.path(WORKSPACE, siteCode, sprintf("CmData_l1_t1072_c%d", comparatorId))
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
  allC <- list(); allO <- list(); allCov <- list(); covRef <- list()
  for (si in seq_along(SITES)) {
    site <- SITES[si]; offset <- (si - 1) * 100000000L
    cm <- loadCm(site, comparatorId); if (is.null(cm)) next
    cohorts <- cm$cohorts
    cohorts$rowId <- as.integer(cohorts$rowId) + offset
    cohorts$personSeqId <- NULL; cohorts$site <- site
    oc <- cm$outcomes; oc$rowId <- as.integer(oc$rowId) + offset
    cov <- cm$covariates; cov$rowId <- as.integer(cov$rowId) + offset
    allC[[site]] <- cohorts; allO[[site]] <- oc; allCov[[site]] <- cov
    covRef[[length(covRef)+1]] <- cm$covariateRef
    cat(sprintf("  %s: cohorts=%d (T=%d, C=%d), outcomes=%d\n",
                site, nrow(cohorts), sum(cohorts$treatment==1), sum(cohorts$treatment==0), nrow(oc)))
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
    fitCoh <- coh[coh$rowId %in% fitIds, ]; fitCov <- cov[cov$rowId %in% fitIds, ]
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

eValue <- function(hr, ciLb, ciUb) {
  if (is.na(hr) || !is.finite(hr)) return(c(NA_real_, NA_real_))
  rr <- ifelse(hr >= 1, hr, 1/hr)
  ep <- rr + sqrt(rr * (rr - 1))
  ci1 <- if (hr >= 1) ciLb else 1/ciUb
  if (is.na(ci1) || ci1 <= 1) ec <- 1
  else ec <- ci1 + sqrt(ci1 * (ci1 - 1))
  c(ep, ec)
}

# =============================================================================
# MAIN
# =============================================================================
t0 <- proc.time()
prim_all <- data.frame()
tw_all <- data.frame()
diag_list <- list()

for (comp in COMPARATORS) {
  cid <- comp$id; cname <- comp$name
  cat(paste0("\n=== ", cname, " (c=", cid, ") ===\n"))
  pool <- buildPooled(cid)
  n_before <- nrow(pool$cohorts)
  cat(sprintf("\n  Pooled: T=%d, C=%d\n", sum(pool$cohorts$treatment==1), sum(pool$cohorts$treatment==0)))

  # Full Union filter based on CLINICAL outcomes (11)
  pool_fu <- applyFullUnion365(pool, CLINICAL_OUTCOMES, LOOKBACK_DAYS)
  n_after <- nrow(pool_fu$cohorts)
  psCoh <- fitPs(pool_fu)
  matched <- matchOne(psCoh); n_matched <- nrow(matched)/2

  # Primary Cox
  prim <- coxOne(matched, pool_fu$outcomes, CLINICAL_OUTCOMES, 1, 3650)
  prim$outcomeName <- OUTCOME_NAMES[as.character(prim$outcomeId)]
  prim$category <- OUTCOME_CATEGORY[prim$outcomeName]

  # NC calibration
  allOc <- unique(pool_fu$outcomes$outcomeId)
  ncIds <- setdiff(allOc, CLINICAL_OUTCOMES)
  ncRes <- coxOne(matched, pool_fu$outcomes, ncIds, 1, 3650)
  nc <- ncRes[!is.na(ncRes$logHr) & !is.na(ncRes$seLogHr) &
              is.finite(ncRes$logHr) & is.finite(ncRes$seLogHr) &
              (ncRes$evT + ncRes$evC) >= 5 & abs(ncRes$logHr) < log(10), ]
  cat(sprintf("  NC usable: %d/%d\n", nrow(nc), nrow(ncRes)))
  nullD <- fitNull(nc$logHr, nc$seLogHr)
  nullMean <- as.numeric(nullD[1]); nullSd <- as.numeric(nullD[2])
  cat(sprintf("  Null: mean=%.3f, sd=%.3f\n", nullMean, nullSd))

  z <- qnorm(0.975)
  prim$calHr <- NA_real_; prim$calCiLb <- NA_real_; prim$calCiUb <- NA_real_; prim$calP <- NA_real_
  prim$eval_hr <- NA_real_; prim$eval_ci <- NA_real_
  prim$cal_eval_hr <- NA_real_; prim$cal_eval_ci <- NA_real_
  for (i in seq_len(nrow(prim))) {
    lh <- prim$logHr[i]; se <- prim$seLogHr[i]
    if (is.na(lh) || is.na(se)) next
    calLh <- lh - nullMean; calSe <- sqrt(se^2 + nullSd^2)
    prim$calHr[i]   <- exp(calLh)
    prim$calCiLb[i] <- exp(calLh - z*calSe)
    prim$calCiUb[i] <- exp(calLh + z*calSe)
    prim$calP[i]    <- 2 * pnorm(-abs(calLh)/calSe)
    ev <- eValue(prim$hr[i], prim$ciLb[i], prim$ciUb[i])
    prim$eval_hr[i] <- ev[1]; prim$eval_ci[i] <- ev[2]
    evc <- eValue(prim$calHr[i], prim$calCiLb[i], prim$calCiUb[i])
    prim$cal_eval_hr[i] <- evc[1]; prim$cal_eval_ci[i] <- evc[2]
  }
  prim$comparator <- cname; prim$comparatorId <- cid
  prim_all <- rbind(prim_all, prim)

  # Time-window
  WINDOWS <- list(c(1,30), c(31,90), c(91,365), c(366,1095), c(1096,3650))
  for (w in WINDOWS) {
    tw <- coxOne(matched, pool_fu$outcomes, CLINICAL_OUTCOMES, w[1], w[2])
    tw$outcomeName <- OUTCOME_NAMES[as.character(tw$outcomeId)]
    tw$category <- OUTCOME_CATEGORY[tw$outcomeName]
    tw$window <- sprintf("%dd-%dd", w[1], w[2])
    tw$calHr <- NA_real_; tw$calCiLb <- NA_real_; tw$calCiUb <- NA_real_; tw$calP <- NA_real_
    for (i in seq_len(nrow(tw))) {
      lh <- tw$logHr[i]; se <- tw$seLogHr[i]
      if (is.na(lh) || is.na(se)) next
      calLh <- lh - nullMean; calSe <- sqrt(se^2 + nullSd^2)
      tw$calHr[i]   <- exp(calLh)
      tw$calCiLb[i] <- exp(calLh - z*calSe)
      tw$calCiUb[i] <- exp(calLh + z*calSe)
      tw$calP[i]    <- 2 * pnorm(-abs(calLh)/calSe)
    }
    tw$comparator <- cname; tw$comparatorId <- cid
    tw_all <- rbind(tw_all, tw)
  }

  diag_list[[paste0("c",cid)]] <- data.frame(
    comparator=cname, n_pooled=n_before, n_after_filter=n_after, n_matched_pairs=n_matched,
    cox_ok=sum(!is.na(prim$hr)), sig_cal=sum(!is.na(prim$calP) & prim$calP<0.05),
    null_mean=round(nullMean,3), null_sd=round(nullSd,3), n_nc=nrow(nc))
}

diag_df <- do.call(rbind, diag_list)
cat("\n=== DIAGNOSTICS ===\n"); print(diag_df)

# Save
write.csv(prim_all, file.path(OUT_DIR, "v4_clinical365d_primary.csv"), row.names = FALSE)
write.csv(tw_all, file.path(OUT_DIR, "v4_clinical365d_timewindow.csv"), row.names = FALSE)
write.csv(diag_df, file.path(OUT_DIR, "v4_clinical365d_diagnostics.csv"), row.names = FALSE)

# Forest plot
plot_df <- prim_all %>%
  filter(!is.na(calHr) & is.finite(calHr) & !is.na(calCiLb) & !is.na(calCiUb)) %>%
  mutate(sig = ifelse(calP < 0.05, "sig", "ns"))
plot_df$outcomeName <- factor(plot_df$outcomeName,
                               levels = unique(plot_df$outcomeName[order(plot_df$category, plot_df$calHr)]))
if (nrow(plot_df) > 0) {
  p <- ggplot(plot_df, aes(x = calHr, y = outcomeName, color = sig)) +
    geom_vline(xintercept = 1, linetype = "dashed", color = "gray50") +
    geom_errorbarh(aes(xmin = calCiLb, xmax = calCiUb), height = 0.3) +
    geom_point(size = 2.5) +
    scale_x_log10(breaks = c(0.1, 0.25, 0.5, 1, 2, 4, 10), limits = c(0.05, 10)) +
    scale_color_manual(values = c("sig" = "firebrick", "ns" = "gray60")) +
    facet_grid(category ~ comparator, scales = "free_y", space = "free_y") +
    labs(x = "Calibrated Hazard Ratio (log scale)", y = NULL,
         title = "Appendectomy vs Comparators — Clinical Outcomes (365d Full Union)",
         subtitle = "14 hospitals, site-stratified Cox, NC calibration") +
    theme_minimal(base_size = 10) +
    theme(legend.position = "bottom", strip.text.y = element_text(angle = 0))
  ggsave(file.path(FIG_DIR, "forest_clinical_365d.png"), p, width = 10, height = 8, dpi = 150)
  cat("Forest plot saved:\n")
}

cat(sprintf("\nTotal runtime: %.1f min\n", (proc.time()-t0)[3]/60))
