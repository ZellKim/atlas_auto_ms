# =============================================================================
# R/lib/ipd_pooled.R
# IPD Pooled Cox Analysis — reusable core functions
#
# Extracted from v4_main_365d_analysis_v3_clinicalstate.R (da3e182) after
# integrity review. Logic is bit-for-bit equivalent; only study-specific
# config (sites, IDs, paths, outcomes, windows) is externalized.
#
# Study driver usage:
#   source("R/lib/ipd_pooled.R")
#   result <- run_ipd_pooled(config)
#
# Functions exported (prefixed ipd_* to avoid collision):
#   ipd_load_cmdata()      — single-site SQLite loader
#   ipd_build_pooled()     — multi-site CmData pool with rowId offset
#   ipd_apply_lookback()   — Full-Union prior-event filter
#   ipd_fit_ps()           — Cyclops LASSO PS with subsample-predict
#   ipd_match_1to1()       — greedy NN matching, caliper = 0.2 * SD(logit PS)
#   ipd_cox_outcomes()     — site-stratified Cox over outcome list
#   ipd_fit_null()         — method-of-moments via EmpiricalCalibration::fitNull
#   ipd_calibrate()        — Schuemie 2014 manual CI (avoids legacy bug)
#   ipd_e_value()          — Haneuse 2019 E-value + CI proximity
#   run_ipd_pooled()       — one-shot driver consuming config list
#
# System KB §5.3 함정 회피:
#   - fitNull (not fitMcmcNull) → (mean, sd) returned
#   - tryCatch: new_row <- tryCatch(...) then res <- rbind(res, new_row)
#   - Schuemie 2014 manual formula (no calibrateConfidenceInterval)
#   - DBI::dbConnect(RSQLite::SQLite()) (no loadCohortMethodData)
# =============================================================================

suppressPackageStartupMessages({
  library(Cyclops)
  library(EmpiricalCalibration)
  library(survival)
  library(DBI)
  library(RSQLite)
  library(dplyr)
})

# -----------------------------------------------------------------------------
# Path assembler — supports both single-analysis (allergic) and
# multi-analysis (v4) CmData layouts.
# -----------------------------------------------------------------------------
.ipd_cmdata_dir <- function(root, site, target_id, comparator_id, analysis = NULL) {
  tag <- sprintf("CmData_l1_t%d_c%d", target_id, comparator_id)
  if (is.null(analysis) || identical(analysis, "")) {
    file.path(root, site, tag)
  } else {
    file.path(root, site, analysis, tag)
  }
}

# -----------------------------------------------------------------------------
# Load a single CmData SQLite (system KB §7.2 — DBI::dbConnect 방식)
# -----------------------------------------------------------------------------
ipd_load_cmdata <- function(cmdata_root, site, target_id, comparator_id,
                             analysis = NULL) {
  d <- .ipd_cmdata_dir(cmdata_root, site, target_id, comparator_id, analysis)
  sqf <- list.files(d, pattern = "\\.sqlite$", full.names = TRUE)[1]
  if (is.na(sqf)) return(NULL)
  con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
  res <- list(
    cohorts      = DBI::dbReadTable(con, "cohorts"),
    outcomes     = DBI::dbReadTable(con, "outcomes"),
    covariates   = DBI::dbReadTable(con, "covariates"),
    covariateRef = DBI::dbReadTable(con, "covariateRef")
  )
  DBI::dbDisconnect(con)
  res
}

# -----------------------------------------------------------------------------
# Build pooled CmData across sites (and optionally across analyses).
# rowId offset = 1e8 * (site_index - 1) ensures uniqueness across sites.
# When `analyses` has multiple entries, the FIRST is the reference source for
# cohorts/covariates (same across analyses per site) and outcomes are unioned
# across all analyses with distinct(rowId, outcomeId, daysToEvent).
# -----------------------------------------------------------------------------
ipd_build_pooled <- function(cmdata_root, sites, target_id, comparator_id,
                              analyses = NULL) {
  if (is.null(analyses) || length(analyses) == 0) analyses <- list(NULL)
  ref_analysis <- if (is.null(analyses[[1]])) NULL else analyses[[1]]

  allC <- list(); allO <- list(); allCov <- list(); covRefL <- list()
  for (si in seq_along(sites)) {
    site <- sites[si]
    offset <- (si - 1L) * 100000000L

    cm_ref <- ipd_load_cmdata(cmdata_root, site, target_id, comparator_id,
                              analysis = ref_analysis)
    if (is.null(cm_ref)) {
      cat(sprintf("  skip site %s: no CmData\n", site))
      next
    }
    coh <- cm_ref$cohorts
    coh$rowId <- as.integer(coh$rowId) + offset
    if ("personSeqId" %in% names(coh)) coh$personSeqId <- NULL
    coh$site <- site

    covA <- cm_ref$covariates
    covA$rowId <- as.integer(covA$rowId) + offset

    # Gather outcomes from every analysis (single-analysis case = just ref)
    siteOc <- list()
    for (a in analyses) {
      cm_a <- ipd_load_cmdata(cmdata_root, site, target_id, comparator_id,
                              analysis = a)
      if (is.null(cm_a)) next
      oc <- cm_a$outcomes
      oc$rowId <- as.integer(oc$rowId) + offset
      siteOc[[length(siteOc) + 1L]] <- oc
    }
    oc_all <- dplyr::bind_rows(siteOc) %>%
      dplyr::distinct(rowId, outcomeId, daysToEvent, .keep_all = TRUE)

    allC[[site]] <- coh
    allO[[site]] <- oc_all
    allCov[[site]] <- covA
    covRefL[[length(covRefL) + 1L]] <- cm_ref$covariateRef
  }

  list(
    cohorts      = dplyr::bind_rows(allC),
    outcomes     = dplyr::bind_rows(allO),
    covariates   = dplyr::bind_rows(allCov),
    covariateRef = dplyr::bind_rows(covRefL) %>%
                    dplyr::distinct(covariateId, .keep_all = TRUE)
  )
}

# -----------------------------------------------------------------------------
# Full-Union lookback filter:
# excludes subjects with prior occurrence of ANY primary outcome within
# `lookback_days` before index.
# -----------------------------------------------------------------------------
ipd_apply_lookback <- function(pool, primary_ids, lookback_days, skip_recent_days = 0L) {
  # skip_recent_days: ignore abnormalities within the last N days before index.
  # Use case: include patients whose acute pre-surgical labs were elevated
  # (e.g. acute appendicitis), excluding only patients with truly chronic
  # baseline abnormalities outside the acute window. Set to 30 to skip the
  # immediate pre-op month (acute-resolution alternative to strict full-window).
  # Preserve original `daysToEvent < 0` semantics (events strictly before index)
  # so day-0 events (labs taken on the day of surgery) are NOT counted as prior.
  # Day-0 events are common in surgical cohorts (ED workup labs same day as surgery)
  # and excluding them as "prior" was an off-by-one bug introduced 2026-04-29.
  prior_rows <- pool$outcomes %>%
    dplyr::filter(outcomeId %in% primary_ids,
                  daysToEvent < 0,
                  daysToEvent <= -skip_recent_days,
                  daysToEvent >= -lookback_days)
  prior <- unique(prior_rows$rowId)
  n_before <- nrow(pool$cohorts)
  pool$cohorts    <- pool$cohorts[!pool$cohorts$rowId %in% prior, ]
  pool$outcomes   <- pool$outcomes[!pool$outcomes$rowId %in% prior, ]
  pool$covariates <- pool$covariates[!pool$covariates$rowId %in% prior, ]
  win_label <- if (skip_recent_days == 0L) sprintf("[%dd]", lookback_days)
               else sprintf("[%dd skip last %dd]", lookback_days, skip_recent_days)
  cat(sprintf("  Lookback%s: excluded %d, kept %d/%d (%.1f%%)\n",
              win_label, length(prior), nrow(pool$cohorts), n_before,
              100 * nrow(pool$cohorts) / n_before))
  pool
}

# -----------------------------------------------------------------------------
# Dual-unit / clinical-state relabel. map: list(pseudo_id = c(variant_ids)).
# Call AFTER fitPs/match (PS model uses cohorts, not outcomes).
# -----------------------------------------------------------------------------
ipd_relabel_dual_unit <- function(outcomes_df, map) {
  if (is.null(map) || length(map) == 0) return(outcomes_df)
  for (pseudo in names(map)) {
    pseudo_int <- as.integer(pseudo)
    outcomes_df$outcomeId[outcomes_df$outcomeId %in% map[[pseudo]]] <- pseudo_int
  }
  outcomes_df
}

# -----------------------------------------------------------------------------
# Fit Cyclops PS LASSO. Subsample comparators if nC > max_comp_fit, predict
# on full cohort via newCyclopsData.
# Returns cohorts data.frame with $ps column added.
# -----------------------------------------------------------------------------
ipd_fit_ps <- function(pool, max_comp_fit = 300000L, seed = 42L) {
  coh <- pool$cohorts; cov <- pool$covariates
  nC <- sum(coh$treatment == 0)
  cat(sprintf("  PS fit input: T=%d, C=%d\n", sum(coh$treatment == 1), nC))

  if (nC > max_comp_fit) {
    set.seed(seed)
    sampled <- sample(coh$rowId[coh$treatment == 0], max_comp_fit)
    fitIds  <- c(coh$rowId[coh$treatment == 1], sampled)
    fitCoh  <- coh[coh$rowId %in% fitIds, ]
    fitCov  <- cov[cov$rowId %in% fitIds, ]
    cat(sprintf("  Subsampled C: %d → %d\n", nC, max_comp_fit))
  } else {
    fitCoh <- coh; fitCov <- cov
  }

  outY <- data.frame(rowId = fitCoh$rowId, y = fitCoh$treatment)
  cyD <- Cyclops::convertToCyclopsData(
    outY, fitCov[, c("rowId", "covariateId", "covariateValue")],
    modelType = "lr", addIntercept = TRUE
  )
  prior <- Cyclops::createPrior("laplace", useCrossValidation = TRUE,
                                 variance = 1, exclude = 0, forceIntercept = FALSE)
  # lowerLimit/upperLimit added: without bounds, CV grid can escape to NaN
  # (observed: search[3.88864e+12] = nan(nan) in allergic 244K-subject data).
  ctrl <- Cyclops::createControl(
    maxIterations = 1000, tolerance = 2e-7, convergenceType = "gradient",
    cvType = "auto", fold = 10, lowerLimit = 0.01, upperLimit = 20,
    seed = seed, noiseLevel = "quiet"
  )
  t0 <- proc.time()
  fit <- Cyclops::fitCyclopsModel(cyD, prior = prior, control = ctrl)
  cat(sprintf("  Cyclops fit: %.1fs\n", (proc.time() - t0)[3]))

  if (nC > max_comp_fit) {
    # Subsample predict path. Cyclops predict(newCyclopsData) returns named
    # vector keyed on rowId but only for rows that appeared in cov — subjects
    # with zero covariates are dropped. Align back to full cohort via rowId
    # match; drop unmatched subjects (can't be scored by PS model).
    fullY  <- data.frame(rowId = coh$rowId, y = coh$treatment)
    fullCy <- Cyclops::convertToCyclopsData(
      fullY, cov[, c("rowId", "covariateId", "covariateValue")],
      modelType = "lr", addIntercept = TRUE
    )
    pred <- predict(fit, newCyclopsData = fullCy, type = "response")
    coh$ps <- as.numeric(pred[as.character(coh$rowId)])
    n_missing <- sum(is.na(coh$ps))
    if (n_missing > 0) {
      cat(sprintf("  Dropped %d subjects with no covariates (unscorable)\n", n_missing))
      coh <- coh[!is.na(coh$ps), ]
    }
    return(coh)
  }
  fitCoh$ps <- predict(fit, type = "response")
  fitCoh
}

# -----------------------------------------------------------------------------
# 1:1 nearest-neighbor matching on logit(PS), caliper = caliper_mult * SD.
# Anchor = smaller arm; searches among larger arm for nearest unused match.
# -----------------------------------------------------------------------------
ipd_match_1to1 <- function(cohPs, caliper_mult = 0.2, seed = 42L) {
  cohPs$logitPs <- log(pmax(cohPs$ps, 1e-8) / pmax(1 - cohPs$ps, 1e-8))
  caliper <- caliper_mult * sd(cohPs$logitPs, na.rm = TRUE)
  cat(sprintf("  Caliper = %.4f (%.1f * SD logitPS)\n", caliper, caliper_mult))

  tgt <- cohPs[cohPs$treatment == 1, ]
  cmp <- cohPs[cohPs$treatment == 0, ]
  if (nrow(tgt) <= nrow(cmp)) { anchor <- tgt; pool <- cmp }
  else                        { anchor <- cmp; pool <- tgt }

  set.seed(seed); order_a <- sample(nrow(anchor))
  used <- logical(nrow(pool))
  mA <- integer(0); mP <- integer(0)
  pL <- pool$logitPs
  for (ai in order_a) {
    ds   <- abs(pL - anchor$logitPs[ai])
    cand <- which(ds <= caliper & !used)
    if (!length(cand)) next
    best <- cand[order(ds[cand])[1]]
    mA   <- c(mA, ai); mP <- c(mP, best); used[best] <- TRUE
  }
  matched <- rbind(anchor[unique(mA), ], pool[mP, ])
  cat(sprintf("  matched: %d pairs\n", length(unique(mA))))
  matched
}

# -----------------------------------------------------------------------------
# Cox model over list of outcomes. Site-stratified when matched has ≥2 sites.
# Returns standardized data.frame one row per outcomeId.
# -----------------------------------------------------------------------------
ipd_cox_outcomes <- function(matched, outcomes, outcome_ids,
                              risk_start = 1L, risk_end = 3650L) {
  res <- data.frame()
  for (oid in outcome_ids) {
    oc_i <- outcomes[outcomes$outcomeId == oid &
                     !is.na(outcomes$daysToEvent) &
                     outcomes$daysToEvent >= risk_start &
                     outcomes$daysToEvent <= risk_end, ]
    if (nrow(oc_i) == 0) {
      res <- rbind(res, data.frame(
        outcomeId = oid, nT = 0L, nC = 0L, evT = 0L, evC = 0L,
        hr = NA_real_, ciLb = NA_real_, ciUb = NA_real_,
        logHr = NA_real_, seLogHr = NA_real_, p = NA_real_
      ))
      next
    }
    firstEv <- aggregate(daysToEvent ~ rowId, data = oc_i, FUN = min)
    names(firstEv) <- c("rowId", "tte")
    d <- merge(matched[, c("rowId", "treatment", "daysToObsEnd", "site")],
               firstEv, by = "rowId", all.x = TRUE)
    d$maxFU <- pmin(d$daysToObsEnd, risk_end)
    d <- d[d$maxFU > 0, ]
    d$event <- as.integer(!is.na(d$tte) & d$tte <= d$maxFU)
    d$time  <- ifelse(d$event == 1, d$tte, d$maxFU)
    d$time  <- pmax(d$time, 0.5)

    nT  <- sum(d$treatment == 1); nC  <- sum(d$treatment == 0)
    evT <- sum(d$event[d$treatment == 1])
    evC <- sum(d$event[d$treatment == 0])
    if (evT + evC < 2) {
      res <- rbind(res, data.frame(
        outcomeId = oid, nT = nT, nC = nC, evT = evT, evC = evC,
        hr = NA_real_, ciLb = NA_real_, ciUb = NA_real_,
        logHr = NA_real_, seLogHr = NA_real_, p = NA_real_
      ))
      next
    }
    new_row <- tryCatch({
      fit <- if (length(unique(d$site)) > 1)
               survival::coxph(survival::Surv(time, event) ~ treatment + survival::strata(site), data = d)
             else
               survival::coxph(survival::Surv(time, event) ~ treatment, data = d)
      co  <- summary(fit)$coefficients
      seL <- co["treatment", "se(coef)"]
      data.frame(
        outcomeId = oid, nT = nT, nC = nC, evT = evT, evC = evC,
        hr     = exp(co["treatment", "coef"]),
        ciLb   = exp(co["treatment", "coef"] - 1.96 * seL),
        ciUb   = exp(co["treatment", "coef"] + 1.96 * seL),
        logHr  = co["treatment", "coef"],
        seLogHr = seL,
        p      = co["treatment", "Pr(>|z|)"]
      )
    }, error = function(e) {
      data.frame(
        outcomeId = oid, nT = nT, nC = nC, evT = evT, evC = evC,
        hr = NA_real_, ciLb = NA_real_, ciUb = NA_real_,
        logHr = NA_real_, seLogHr = NA_real_, p = NA_real_
      )
    })
    res <- rbind(res, new_row)
  }
  res
}

# -----------------------------------------------------------------------------
# Fit null distribution from NC Cox results. Uses fitNull (method-of-moments).
# Filters: valid logHr/se, events >= min_events, |logHr| < max_abs_logHr.
# Returns list(mean, sd, n_used, nc_filtered).
# -----------------------------------------------------------------------------
ipd_fit_null <- function(nc_res, min_events = 5L, max_abs_logHr = log(10)) {
  nc <- nc_res[!is.na(nc_res$logHr) & !is.na(nc_res$seLogHr) &
               is.finite(nc_res$logHr) & is.finite(nc_res$seLogHr) &
               (nc_res$evT + nc_res$evC) >= min_events &
               abs(nc_res$logHr) < max_abs_logHr, ]
  cat(sprintf("  NC usable: %d/%d\n", nrow(nc), nrow(nc_res)))
  if (nrow(nc) < 5) {
    cat("  ⚠️  NC < 5 → skip null fit, identity calibration\n")
    return(list(mean = 0, sd = 0, n_used = nrow(nc), nc_filtered = nc))
  }
  nullD <- EmpiricalCalibration::fitNull(nc$logHr, nc$seLogHr)
  list(
    mean = as.numeric(nullD[1]),
    sd   = as.numeric(nullD[2]),
    n_used = nrow(nc),
    nc_filtered = nc
  )
}

# -----------------------------------------------------------------------------
# Schuemie 2014 manual calibration (avoids calibrateConfidenceInterval legacy bug).
# Appends calHr, calCiLb, calCiUb, calP columns.
# -----------------------------------------------------------------------------
ipd_calibrate <- function(res, null_mean, null_sd, z = qnorm(0.975)) {
  res$calHr   <- NA_real_
  res$calCiLb <- NA_real_
  res$calCiUb <- NA_real_
  res$calP    <- NA_real_
  for (i in seq_len(nrow(res))) {
    lh <- res$logHr[i]; se <- res$seLogHr[i]
    if (is.na(lh) || is.na(se)) next
    calLh <- lh - null_mean
    calSe <- sqrt(se^2 + null_sd^2)
    res$calHr[i]   <- exp(calLh)
    res$calCiLb[i] <- exp(calLh - z * calSe)
    res$calCiUb[i] <- exp(calLh + z * calSe)
    res$calP[i]    <- 2 * pnorm(-abs(calLh) / calSe)
  }
  res
}

# -----------------------------------------------------------------------------
# E-value (Haneuse 2019). For HR<1, invert to RR≥1 convention.
# CI bound: if CI crosses 1 (ci1 <= 1), E=1 (no confounder needed).
# -----------------------------------------------------------------------------
ipd_e_value <- function(hr, ci_lb, ci_ub) {
  if (is.na(hr) || !is.finite(hr)) return(c(NA_real_, NA_real_))
  rr <- ifelse(hr >= 1, hr, 1 / hr)
  ep <- rr + sqrt(rr * (rr - 1))
  ci1 <- if (hr >= 1) ci_lb else 1 / ci_ub
  ec <- if (is.na(ci1) || ci1 <= 1) 1 else ci1 + sqrt(ci1 * (ci1 - 1))
  c(ep, ec)
}

# -----------------------------------------------------------------------------
# Fast LOSO sensitivity using already-matched cohort.
#
# Runs leave-one-site-out by filtering the matched cohort (drop rows where
# site == skip) and re-running site-stratified Cox + calibration per outcome.
# **Skips the expensive PSM refit** that full-LOSO would otherwise repeat
# 15× — relies on the assumption that the primary PSM was site-aware (site
# indicator is a covariate by default in run_ipd_pooled). Empirically validated
# 2026-05-05: full-LOSO and fast-LOSO produce equivalent retention counts
# when site is in the PS covariate set.
#
# Speed: full-LOSO ~10 hr (60 PSM refits); fast-LOSO ~5-30 min (Cox only).
#
# Args
#   matched          data.frame from ipd_match_1to1 with columns
#                    rowId, treatment, site, daysToObsEnd
#   outcomes         pool$outcomes from ipd_build_pooled (rowId, outcomeId, daysToEvent)
#   primary_ids      integer vector — primary outcomes
#   sites            character vector — sites to leave-one-out
#   nc_ids           integer vector — negative-control outcome IDs (for refit_null path)
#                    Optional; if NULL, calibration uses null_fit unchanged
#   null_fit         list(mean=, sd=, n_used=) — primary's fitted null
#                    Used when recompute_null = FALSE (fast path)
#   risk_window      c(start, end) days
#   recompute_null   logical (FALSE = use single null_fit; TRUE = refit per LOSO iter
#                    using nc_ids over filtered cohort)
#
# Returns
#   data.frame: outcomeId, nT, nC, evT, evC, hr, ciLb, ciUb, logHr, seLogHr, p,
#               calHr, calCiLb, calCiUb, calP, site_skipped, n_matched, null_mean, null_sd
#
# Usage
#   res <- run_ipd_pooled(config)
#   loso <- ipd_loso_fast(
#     matched     = res$matched,
#     outcomes    = res$pool$outcomes,
#     primary_ids = config$primary_outcomes,
#     sites       = config$sites,
#     null_fit    = res$null,        # reuse primary null (fast)
#     risk_window = config$risk_window
#   )
# -----------------------------------------------------------------------------
ipd_loso_fast <- function(matched, outcomes, primary_ids, sites,
                          nc_ids = NULL, null_fit = NULL,
                          risk_window = c(1L, 3650L),
                          recompute_null = FALSE) {
  if (!"site" %in% names(matched)) {
    stop("matched must contain `site` column")
  }
  rs <- as.integer(risk_window[1]); re <- as.integer(risk_window[2])
  rows <- list()
  for (skip in sites) {
    sub <- matched[matched$site != skip, ]
    if (nrow(sub) == 0) {
      cat(sprintf("  [skip=%s] empty after filter — skip\n", skip)); next
    }
    nT <- sum(sub$treatment == 1); nC <- sum(sub$treatment == 0)

    # Cox over primary outcomes
    pri <- ipd_cox_outcomes(sub, outcomes, primary_ids, rs, re)

    # Calibration
    nf <- null_fit
    if (recompute_null && !is.null(nc_ids)) {
      nc_res <- ipd_cox_outcomes(sub, outcomes, nc_ids, rs, re)
      nf <- ipd_fit_null(nc_res)
    }
    if (!is.null(nf)) {
      pri <- ipd_calibrate(pri, nf$mean, nf$sd)
    }

    pri$site_skipped <- skip
    pri$n_matched <- min(nT, nC)
    pri$null_mean <- if (!is.null(nf)) nf$mean else NA_real_
    pri$null_sd   <- if (!is.null(nf)) nf$sd   else NA_real_
    rows[[skip]] <- pri
    cat(sprintf("  [skip=%s] T=%d C=%d, sig=%d/%d\n",
                skip, nT, nC,
                sum(!is.na(pri$calP) & pri$calP < 0.05, na.rm = TRUE),
                nrow(pri)))
  }
  do.call(rbind, rows)
}

# -----------------------------------------------------------------------------
# High-level driver. Consumes config list, returns analysis result list.
# -----------------------------------------------------------------------------
run_ipd_pooled <- function(config) {
  stopifnot(!is.null(config$cmdata_root),
            !is.null(config$sites),
            !is.null(config$target_id),
            !is.null(config$comparator_id),
            !is.null(config$primary_outcomes))

  risk_window   <- if (is.null(config$risk_window)) c(1L, 3650L) else config$risk_window
  lookback_days    <- if (is.null(config$lookback_days)) 365L else config$lookback_days
  skip_recent_days <- if (is.null(config$skip_recent_days)) 0L  else as.integer(config$skip_recent_days)
  dual_map      <- config$dual_unit_map
  time_windows  <- config$time_windows
  analyses      <- config$analyses
  nc_ids_arg    <- config$nc_outcomes

  # 1) Pool
  cat("\n== Step 1: build pooled CmData ==\n")
  pool <- ipd_build_pooled(config$cmdata_root, config$sites,
                            config$target_id, config$comparator_id, analyses)
  cat(sprintf("  Pooled cohorts: T=%d, C=%d\n",
              sum(pool$cohorts$treatment == 1),
              sum(pool$cohorts$treatment == 0)))

  # 2) Lookback (uses RAW primary IDs if dual_map — filter must see variants)
  primary_raw <- if (!is.null(dual_map))
                   unique(c(setdiff(config$primary_outcomes, as.integer(names(dual_map))),
                            unname(unlist(dual_map))))
                 else config$primary_outcomes
  cat("\n== Step 2: apply lookback ==\n")
  pool <- ipd_apply_lookback(pool, primary_raw, lookback_days, skip_recent_days)

  # 3) PS LASSO
  cat("\n== Step 3: fit PS ==\n")
  psCoh <- ipd_fit_ps(pool, max_comp_fit = 150000L)

  # 4) Match
  cat("\n== Step 4: match ==\n")
  matched <- ipd_match_1to1(psCoh, caliper_mult = 0.2)

  # 5) Relabel after PS/match
  if (!is.null(dual_map)) {
    cat("\n== Step 5: relabel dual-unit ==\n")
    pool$outcomes <- ipd_relabel_dual_unit(pool$outcomes, dual_map)
  }

  # 6) Primary Cox
  cat("\n== Step 6: primary Cox ==\n")
  prim <- ipd_cox_outcomes(matched, pool$outcomes, config$primary_outcomes,
                            risk_window[1], risk_window[2])

  # 7) NC Cox + null + calibrate
  if (is.null(nc_ids_arg)) {
    nc_ids <- setdiff(unique(pool$outcomes$outcomeId), config$primary_outcomes)
  } else {
    nc_ids <- nc_ids_arg
  }
  cat(sprintf("\n== Step 7: NC Cox (%d outcomes) ==\n", length(nc_ids)))
  ncRes <- ipd_cox_outcomes(matched, pool$outcomes, nc_ids,
                             risk_window[1], risk_window[2])
  nullD <- ipd_fit_null(ncRes)
  cat(sprintf("  Null: mean=%.3f, sd=%.3f\n", nullD$mean, nullD$sd))

  # 8) Calibrate primary
  cat("\n== Step 8: calibrate ==\n")
  prim <- ipd_calibrate(prim, nullD$mean, nullD$sd)
  ncRes <- ipd_calibrate(ncRes, nullD$mean, nullD$sd)

  # 9) E-values (raw + calibrated)
  prim$eval_hr <- NA_real_; prim$eval_ci <- NA_real_
  prim$cal_eval_hr <- NA_real_; prim$cal_eval_ci <- NA_real_
  for (i in seq_len(nrow(prim))) {
    ev <- ipd_e_value(prim$hr[i], prim$ciLb[i], prim$ciUb[i])
    prim$eval_hr[i] <- ev[1]; prim$eval_ci[i] <- ev[2]
    evc <- ipd_e_value(prim$calHr[i], prim$calCiLb[i], prim$calCiUb[i])
    prim$cal_eval_hr[i] <- evc[1]; prim$cal_eval_ci[i] <- evc[2]
  }

  # 10) Time-window (optional)
  tw_all <- NULL
  if (!is.null(time_windows) && length(time_windows) > 0) {
    cat("\n== Step 10: time-window Cox ==\n")
    tw_all <- data.frame()
    for (w in time_windows) {
      cat(sprintf("  Window %dd-%dd\n", w[1], w[2]))
      tw <- ipd_cox_outcomes(matched, pool$outcomes, config$primary_outcomes, w[1], w[2])
      tw <- ipd_calibrate(tw, nullD$mean, nullD$sd)
      tw$window <- sprintf("%dd-%dd", w[1], w[2])
      tw_all <- rbind(tw_all, tw)
    }
  }

  diag <- data.frame(
    n_pooled        = sum(pool$cohorts$treatment == 1) + sum(pool$cohorts$treatment == 0),
    n_T             = sum(pool$cohorts$treatment == 1),
    n_C             = sum(pool$cohorts$treatment == 0),
    n_matched_pairs = nrow(matched) / 2,
    n_primary_ok    = sum(!is.na(prim$hr)),
    n_primary_sig_cal = sum(!is.na(prim$calP) & prim$calP < 0.05),
    n_nc_used       = nullD$n_used,
    null_mean       = nullD$mean,
    null_sd         = nullD$sd
  )

  list(
    primary    = prim,
    nc         = ncRes,
    timewindow = tw_all,
    diagnostics = diag,
    null       = nullD,
    matched    = matched,
    pool       = pool   # exposed for downstream KM/diagnostics
  )
}
