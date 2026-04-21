# =============================================================================
# v4 Main Analysis — 365d Full Union Lookback (v3: clinical-state combining)
#
# v3 extends v2's dual-unit combining (CRP mg/dL+mg/L) to include pooling
# of conceptually related measurements for the same clinical state:
#   CRP           : mg/dL (1370) + mg/L (1369)                           → 9001
#   Neutrophilia  : Neutro % (1392) + abs count thou/uL (1390) + /uL (1391) → 9005
#   Eosinophilia  : Eosino % (1375) + abs count thou/uL (1373) + /uL (1374) → 9006
#
# Rationale: study primary outcome is first-occurrence threshold-crossing
# abnormality (a binary event, not a continuous value). Neutrophil % and
# absolute count are different lab tests, but both detect the same clinical
# state (neutrophilia) in the CBC panel. Combining avoids spurious
# duplication of the same underlying event and matches the "abnormality
# detection" framing of the study. Separate % vs count estimates are
# preserved in v2 backup and reported as supplementary eTable 7.
#
# Bidirectional pairs (Lympho%, MCV, Platelet, TotProt, TSH) remain as
# 10 separate rows (direction-specific clinical events).
#
# Primary outcomes after combine: 30 (was 35 unit-split, 32 under v2).
# =============================================================================

Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
suppressPackageStartupMessages({
  library(Cyclops)
  library(EmpiricalCalibration)
  library(survival)
  library(DBI)
  library(RSQLite)
  library(dplyr)
  library(ggplot2)
})

WORKSPACE <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_ipd_workspace"
OUT_DIR   <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output"
FIG_DIR   <- file.path(OUT_DIR, "figures")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)
dir.create(FIG_DIR, showWarnings = FALSE, recursive = TRUE)

SITES <- c("AUMC","CHNUH","DCMC","GNUCH","GNUH","HUMC","ISH","JCMJ","KDH","KHNMC","KWMC","SCHBC","SCHCA","SCHGM","SCHSU","WKUH")
ANALYSES <- c("v4_1a_cbc_wbc", "v4_1b_cbc_rbc", "v4_2_chem_hepa", "v4_3_meta_endo")
COMPARATORS <- list(list(id = 1074, name = "Chole"), list(id = 1121, name = "Hernia"))
LOOKBACK_DAYS <- 365  # MAIN setting

PRIMARY_OUTCOMES <- list(
  v4_1a_cbc_wbc  = c(1357, 1390, 1391, 1392, 1360, 1385, 1373, 1374),
  v4_1b_cbc_rbc  = c(1375, 1362, 1368, 1358, 1387, 1395, 1394, 1393),
  v4_2_chem_hepa = c(1370, 1369, 1364, 1365, 1363, 1400, 1366, 1381, 1384, 1397, 1396),
  v4_3_meta_endo = c(1378, 1379, 1402, 1401, 1367, 1399, 1398, 1404)
)
OUTCOME_NAMES <- c(
  "1357"="WBC_high",
  "1360"="Lympho_pct_low","1385"="Lympho_pct_high",
  "1362"="Mono_high","1368"="Baso_pct_high","1358"="MCV_low",
  "1387"="MCV_high","1395"="RDW_high","1394"="Platelet_low","1393"="Platelet_high",
  "1364"="ALT_high","1365"="AST_high",
  "1363"="ALP_high","1400"="TotBili_high","1366"="Albumin_low","1381"="HbA1c_high",
  "1384"="LDL_high","1397"="TG_high","1396"="TC_high",
  "1378"="GlucDM","1379"="GlucPreDM","1402"="TotProt_low","1401"="TotProt_high",
  "1367"="BUN_high","1399"="TSH_low","1398"="TSH_high","1404"="VitD_low",
  # Combined pseudo-IDs (v3: clinical-state combining)
  "9001"="CRP_high",         # CRP (mg/dL + mg/L)
  "9005"="Neutrophilia_any", # Neutrophil % + absolute count (thou/uL + /uL)
  "9006"="Eosinophilia_any"  # Eosinophil % + absolute count (thou/uL + /uL)
)
# Category for grouping in forest plot
OUTCOME_CATEGORY <- c(
  "WBC_high"="WBC",
  "Lympho_pct_low"="Lymphocyte", "Lympho_pct_high"="Lymphocyte",
  "Mono_high"="Monocyte", "Baso_pct_high"="Basophil", "RDW_high"="RBC",
  "MCV_low"="RBC", "MCV_high"="RBC", "Platelet_low"="Platelet", "Platelet_high"="Platelet",
  "ALT_high"="Liver", "AST_high"="Liver",
  "ALP_high"="Liver", "TotBili_high"="Liver", "Albumin_low"="Protein", "TotProt_low"="Protein",
  "TotProt_high"="Protein", "HbA1c_high"="Glucose", "GlucDM"="Glucose", "GlucPreDM"="Glucose",
  "LDL_high"="Lipid", "TG_high"="Lipid", "TC_high"="Lipid",
  "BUN_high"="Kidney", "TSH_low"="Thyroid", "TSH_high"="Thyroid", "VitD_low"="Vitamin",
  # Combined
  "CRP_high"="CRP", "Neutrophilia_any"="Neutrophil", "Eosinophilia_any"="Eosinophil"
)

# v3: Clinical-state combining map. Neutrophil % and absolute count (both units)
# are pooled because they represent the same clinical state (neutrophilia),
# and similarly for eosinophilia. CRP dual-unit unchanged.
DUAL_UNIT_MAP <- list(
  "9001" = c(1370, 1369),                    # CRP: mg/dL + mg/L
  "9005" = c(1392, 1390, 1391),              # Neutrophilia: % + thou/uL + /uL
  "9006" = c(1375, 1373, 1374)               # Eosinophilia: % + thou/uL + /uL
)
DUAL_UNIT_ORIG_IDS <- unname(unlist(DUAL_UNIT_MAP))  # c(1370,1369,1392,1390,1391,1375,1373,1374)

# v3 primary outcomes = 35 original - 8 variants + 3 combined pseudo-IDs = 30
ALL_PRIMARY_RAW <- unname(as.integer(unlist(PRIMARY_OUTCOMES)))
ALL_PRIMARY <- c(setdiff(ALL_PRIMARY_RAW, DUAL_UNIT_ORIG_IDS), as.integer(names(DUAL_UNIT_MAP)))

relabelDualUnit <- function(outcomes_df) {
  # For each combined pseudo-ID, overwrite variant IDs with the pseudo-ID.
  # coxOne's aggregate(daysToEvent ~ rowId, FUN=min) then naturally takes the
  # earliest event across any unit variant for the same patient.
  for (pseudo in names(DUAL_UNIT_MAP)) {
    pseudo_int <- as.integer(pseudo)
    outcomes_df$outcomeId[outcomes_df$outcomeId %in% DUAL_UNIT_MAP[[pseudo]]] <- pseudo_int
  }
  outcomes_df
}

# ---- Functions ----
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
  allC <- list(); allO <- list(); allCov <- list(); covRef <- list()
  for (si in seq_along(SITES)) {
    site <- SITES[si]; offset <- (si - 1) * 100000000L
    cm_1a <- loadCm(site, "v4_1a_cbc_wbc", comparatorId)
    if (is.null(cm_1a)) next
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
# MAIN — 365d Full Union lookback
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
  cat(sprintf("  Pooled: T=%d, C=%d\n", sum(pool$cohorts$treatment==1), sum(pool$cohorts$treatment==0)))

  # applyFullUnion365 uses ORIGINAL outcome IDs (including dual-unit variants)
  # since the filter examines pre-index events by their raw outcomeId.
  pool_fu <- applyFullUnion365(pool, ALL_PRIMARY_RAW, LOOKBACK_DAYS)
  n_after <- nrow(pool_fu$cohorts)
  psCoh <- fitPs(pool_fu)
  matched <- matchOne(psCoh); n_matched <- nrow(matched)/2

  # Relabel dual-unit variants to combined pseudo-IDs before all downstream Cox.
  # This is the core of the v2 dual-unit-combined analysis.
  pool_fu$outcomes <- relabelDualUnit(pool_fu$outcomes)
  cat(sprintf("  v3 relabel: CRP 1370/1369\u21929001, Neutrophilia 1392/1390/1391\u21929005, Eosinophilia 1375/1373/1374\u21929006\n"))

  # Primary Cox (full risk 1-3650d) — now operates on 32 primary outcomes
  prim <- coxOne(matched, pool_fu$outcomes, ALL_PRIMARY, 1, 3650)
  prim$outcomeName <- OUTCOME_NAMES[as.character(prim$outcomeId)]
  prim$category <- OUTCOME_CATEGORY[prim$outcomeName]

  # NC Cox + calibration (fitNull method-of-moments)
  allOc <- unique(pool_fu$outcomes$outcomeId)
  ncIds <- setdiff(allOc, ALL_PRIMARY)
  ncRes <- coxOne(matched, pool_fu$outcomes, ncIds, 1, 3650)
  nc <- ncRes[!is.na(ncRes$logHr) & !is.na(ncRes$seLogHr) &
              is.finite(ncRes$logHr) & is.finite(ncRes$seLogHr) &
              (ncRes$evT + ncRes$evC) >= 5 & abs(ncRes$logHr) < log(10), ]
  cat(sprintf("  NC usable: %d/%d\n", nrow(nc), nrow(ncRes)))
  nullD <- fitNull(nc$logHr, nc$seLogHr)
  nullMean <- as.numeric(nullD[1]); nullSd <- as.numeric(nullD[2])
  cat(sprintf("  Null: mean=%.3f, sd=%.3f\n", nullMean, nullSd))

  # Apply calibration (Schuemie 2014)
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

  # Time-window Cox
  WINDOWS <- list(c(1,30), c(31,90), c(91,365), c(366,1095), c(1096,3650))
  for (w in WINDOWS) {
    tw <- coxOne(matched, pool_fu$outcomes, ALL_PRIMARY, w[1], w[2])
    tw$outcomeName <- OUTCOME_NAMES[as.character(tw$outcomeId)]
    tw$category <- OUTCOME_CATEGORY[tw$outcomeName]
    tw$window <- sprintf("%dd-%dd", w[1], w[2])
    # Calibrate time-window HRs with same null
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
    comparator=cname, n_pooled=n_before, n_after_filter=n_after,
    n_matched_pairs=n_matched, cox_ok=sum(!is.na(prim$hr)), sig_cal=sum(!is.na(prim$calP) & prim$calP<0.05),
    null_mean=nullMean, null_sd=nullSd, n_nc=nrow(nc))
}

diag_df <- do.call(rbind, diag_list)
cat("\n\n=== DIAGNOSTICS ===\n"); print(diag_df)

# Save
write.csv(prim_all, file.path(OUT_DIR, "v4_fu365d_primary.csv"), row.names = FALSE)
write.csv(tw_all, file.path(OUT_DIR, "v4_fu365d_timewindow.csv"), row.names = FALSE)
write.csv(diag_df, file.path(OUT_DIR, "v4_fu365d_diagnostics.csv"), row.names = FALSE)

# =============================================================================
# Forest plot (main primary, calibrated HR)
# =============================================================================
plot_df <- prim_all %>%
  filter(!is.na(calHr) & is.finite(calHr) & !is.na(calCiLb) & !is.na(calCiUb)) %>%
  mutate(
    sig = ifelse(calP < 0.05, "sig", "ns"),
    label = sprintf("%s (%d/%d)", outcomeName, evT, evC)
  ) %>%
  arrange(category, calHr)
# Order
plot_df$outcomeName <- factor(plot_df$outcomeName, levels = unique(plot_df$outcomeName[order(plot_df$category, plot_df$calHr)]))

p <- ggplot(plot_df, aes(x = calHr, y = outcomeName, color = sig)) +
  geom_vline(xintercept = 1, linetype = "dashed", color = "gray50") +
  geom_errorbarh(aes(xmin = calCiLb, xmax = calCiUb), height = 0.3) +
  geom_point(size = 2.5) +
  scale_x_log10(breaks = c(0.1, 0.25, 0.5, 1, 2, 4), limits = c(0.1, 4)) +
  scale_color_manual(values = c("sig" = "firebrick", "ns" = "gray60")) +
  facet_grid(category ~ comparator, scales = "free_y", space = "free_y") +
  labs(x = "Calibrated Hazard Ratio (log scale)", y = NULL,
       title = "Appendectomy vs Comparators — Biomarker Outcomes (365d Full Union)",
       subtitle = "Site-stratified Cox model, NC calibration (Schuemie 2014)") +
  theme_minimal(base_size = 10) +
  theme(legend.position = "bottom",
        strip.text.y = element_text(angle = 0),
        panel.spacing = unit(0.3, "lines"))
ggsave(file.path(FIG_DIR, "forest_primary_365d.png"), p, width = 10, height = 12, dpi = 150)
cat("Forest plot saved: ", file.path(FIG_DIR, "forest_primary_365d.png"), "\n")

# Time-window plot for core immune markers
core <- c("WBC_high","Neutro_pct_high","Lympho_pct_low","CRP_mgdL_high","TotBili_high","ALT_high","AST_high","GlucDM")
tw_core <- tw_all %>% filter(outcomeName %in% core, !is.na(calHr) & is.finite(calHr))
tw_core$window <- factor(tw_core$window, levels = c("1d-30d","31d-90d","91d-365d","366d-1095d","1096d-3650d"))
tw_core$outcomeName <- factor(tw_core$outcomeName, levels = core)

p2 <- ggplot(tw_core, aes(x = window, y = calHr, group = interaction(comparator, outcomeName))) +
  geom_hline(yintercept = 1, linetype = "dashed", color = "gray50") +
  geom_pointrange(aes(ymin = calCiLb, ymax = calCiUb, color = comparator),
                  position = position_dodge(0.4)) +
  scale_y_log10() +
  facet_wrap(~ outcomeName, ncol = 4) +
  labs(x = "Time window (days)", y = "Calibrated HR",
       title = "Time-window analysis — core outcomes (365d Full Union)") +
  theme_minimal(base_size = 9) +
  theme(axis.text.x = element_text(angle = 30, hjust = 1), legend.position = "bottom")
ggsave(file.path(FIG_DIR, "timewindow_core_365d.png"), p2, width = 12, height = 6, dpi = 150)
cat("Time-window plot saved: ", file.path(FIG_DIR, "timewindow_core_365d.png"), "\n")

cat(sprintf("\nTotal runtime: %.1f min\n", (proc.time()-t0)[3]/60))
cat("Outputs:\n")
cat("  v4_fu365d_primary.csv: ", nrow(prim_all), " rows\n")
cat("  v4_fu365d_timewindow.csv: ", nrow(tw_all), " rows\n")
cat("  v4_fu365d_diagnostics.csv: ", nrow(diag_df), " rows\n")
cat("  figures/forest_primary_365d.png\n")
cat("  figures/timewindow_core_365d.png\n")
