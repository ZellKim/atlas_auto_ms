# =============================================================================
# ⚠️  DEPRECATED 2026-04-24 — superseded by R/lib/ipd_pooled.R + driver pattern.
# This pilot had simplified censoring (ifelse(event, tte, 1185) ignoring
# daysToObsEnd) and loose NC filter (only !is.na(logHr)). v2 driver via lib
# fixes both to match v4 canonical. See: studies/allergic_diseases/R/run_pilot_v2.R
# =============================================================================
# Allergic diseases IPD pooled analysis — PILOT (3 sites)
# - Target=1290 (T1 allergic rhinitis), Comparator=1287 (C1 non-allergic)
# - Primary outcomes: 1288 (ADHD), 1289 (Tic)
# - NC outcomes: 54 standard condition NC (appendectomy v7 재사용)
# - Pool strategy: L3 — unified covariates + site dummy → Cyclops PS → 1:1 match
#                       → site-stratified Cox → EmpiricalCalibration
# - System KB §7.2 준수: DBI::dbConnect, no loadCohortMethodData
# - 함정 회피: tryCatch 내 <<- 금지, calibrateConfidenceInterval 대신 Schuemie 2014 직접
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

WS  <- "C:/Users/data1/Desktop/atlas_auto_cmdata/cmData_allergic"
OUT <- "C:/Users/data1/Desktop/atlas_auto_cmdata/allergic_pooled_output"
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

SITES <- c("AUMC_5.3.1_11", "CHNUH_5.3.1_01", "SCHCA_5.3.3_03")
TARGET_ID <- 1290L
COMPARATOR_ID <- 1287L
PRIMARY_OUTCOMES <- c("ADHD" = 1288L, "Tic" = 1289L)
NC_IDS <- c(73008, 74855, 75354, 75911, 76786, 77965, 78619, 81378, 81878,
            133141, 133228, 134461, 136368, 139099, 140480, 140641, 140648,
            141932, 192606, 196168, 200775, 260134, 373478, 374375, 374923,
            375552, 376707, 377572, 377575, 378424, 379805, 380038, 380094,
            381581, 436634, 438329, 441818, 443285, 444132, 4030042, 4033858,
            4050747, 4088290, 4092879, 4134455, 4156115, 4169984, 4170770,
            4215978, 4254542, 4329707, 4344500, 40481632, 40568467)

ALL_OUT <- c(PRIMARY_OUTCOMES, setNames(NC_IDS, paste0("NC", NC_IDS)))

# -----------------------------------------------------------------------------
# Step A: Load all 3 sites, unify rowId (add offset per site)
# -----------------------------------------------------------------------------
loadSite <- function(site, siteIdx) {
  d <- file.path(WS, site, sprintf("CmData_l1_t%d_c%d", TARGET_ID, COMPARATOR_ID))
  sqf <- list.files(d, pattern = "\\.sqlite$", full.names = TRUE)[1]
  if (is.na(sqf)) { cat("  skip (no sqlite):", site, "\n"); return(NULL) }

  con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
  offset <- (siteIdx - 1L) * 1e8
  coh  <- DBI::dbReadTable(con, "cohorts")
  out  <- DBI::dbReadTable(con, "outcomes")
  cov  <- DBI::dbReadTable(con, "covariates")
  cref <- DBI::dbReadTable(con, "covariateRef")
  DBI::dbDisconnect(con)

  coh$rowId <- as.integer(coh$rowId) + offset
  out$rowId <- as.integer(out$rowId) + offset
  cov$rowId <- as.integer(cov$rowId) + offset
  coh$siteIdx <- siteIdx
  list(cohorts = coh, outcomes = out, covariates = cov, covariateRef = cref)
}

cat("=== Step A: Load 3 sites ===\n")
siteData <- list()
for (i in seq_along(SITES)) {
  cat(sprintf("  [%d] %s\n", i, SITES[i]))
  siteData[[i]] <- loadSite(SITES[i], i)
}

cohorts    <- do.call(rbind, lapply(siteData, `[[`, "cohorts"))
outcomes   <- do.call(rbind, lapply(siteData, `[[`, "outcomes"))
covariates <- do.call(rbind, lapply(siteData, `[[`, "covariates"))
covariateRef <- siteData[[1]]$covariateRef  # same across sites (same spec)

cat(sprintf("\nPooled cohorts: %d subjects (T=%d, C=%d)\n",
            nrow(cohorts),
            sum(cohorts$treatment == 1), sum(cohorts$treatment == 0)))

# add site dummy covariate (for PS model — strata also in Cox below)
for (si in 2:length(SITES)) {
  site_cov_id <- 900000000 + si  # synthetic covariate id
  site_rows <- cohorts$rowId[cohorts$siteIdx == si]
  new_cov <- data.frame(rowId = site_rows, covariateId = site_cov_id, covariateValue = 1)
  covariates <- rbind(covariates, new_cov)
  new_ref <- data.frame(covariateId = site_cov_id,
                        covariateName = sprintf("Site=%s", SITES[si]),
                        analysisId = 999L, conceptId = 0L)
  covariateRef <- rbind(covariateRef, new_ref)
}

cat(sprintf("Covariate rows: %d, unique covariateIds: %d\n",
            nrow(covariates), length(unique(covariates$covariateId))))

# -----------------------------------------------------------------------------
# Step B: Cyclops PS fitting (subsample comparators if too many, to avoid OOM)
# -----------------------------------------------------------------------------
cat("\n=== Step B: Cyclops PS LASSO ===\n")
MAX_COMP_FIT <- 150000L
nT <- sum(cohorts$treatment == 1); nC <- sum(cohorts$treatment == 0)
cat(sprintf("  T=%d, C=%d\n", nT, nC))

if (nC > MAX_COMP_FIT) {
  set.seed(42)
  compIds <- cohorts$rowId[cohorts$treatment == 0]
  sampled <- sample(compIds, MAX_COMP_FIT)
  fitIds <- c(cohorts$rowId[cohorts$treatment == 1], sampled)
  fitCoh <- cohorts[cohorts$rowId %in% fitIds, ]
  fitCov <- covariates[covariates$rowId %in% fitIds, ]
  cat(sprintf("  Subsampled C: %d → %d\n", nC, MAX_COMP_FIT))
} else {
  fitCoh <- cohorts; fitCov <- covariates
}

outcomesY <- data.frame(rowId = fitCoh$rowId, y = fitCoh$treatment)
psData <- Cyclops::convertToCyclopsData(
  outcomes = outcomesY,
  covariates = fitCov[, c("rowId", "covariateId", "covariateValue")],
  modelType = "lr", addIntercept = TRUE
)
prior <- Cyclops::createPrior("laplace", useCrossValidation = TRUE,
                               variance = 1, exclude = 0, forceIntercept = FALSE)
control <- Cyclops::createControl(
  maxIterations = 1000, tolerance = 2e-7, convergenceType = "gradient",
  cvType = "auto", fold = 10, lowerLimit = 0.01, upperLimit = 20,
  seed = 42, noiseLevel = "quiet"
)
t0 <- proc.time()
psFit <- Cyclops::fitCyclopsModel(psData, prior = prior, control = control)
cat(sprintf("  Cyclops fit: %.1fs\n", (proc.time() - t0)[3]))

# Predict PS for all rowIds (subsampled OR full set). predict returns ps per row.
ps_fit <- predict(psFit, type = "response")
fitCoh$propensityScore <- ps_fit

# For subsample case: re-fit PS on full cohort not needed if we just use matched within subsample.
# Simpler: drop unmatched comparators and use fitCoh as working cohort.
cohorts <- fitCoh
covariates <- fitCov  # keep for consistency
cat(sprintf("PS fit: %d subjects with score\n", sum(!is.na(cohorts$propensityScore))))
cat(sprintf("PS fit: %d subjects with score\n", sum(!is.na(cohorts$propensityScore))))
cat(sprintf("PS range: [%.3f, %.3f], mean=%.3f (T=%.3f, C=%.3f)\n",
            min(cohorts$propensityScore, na.rm=TRUE),
            max(cohorts$propensityScore, na.rm=TRUE),
            mean(cohorts$propensityScore, na.rm=TRUE),
            mean(cohorts$propensityScore[cohorts$treatment==1], na.rm=TRUE),
            mean(cohorts$propensityScore[cohorts$treatment==0], na.rm=TRUE)))

# -----------------------------------------------------------------------------
# Step C: 1:1 nearest-neighbor matching, caliper = 0.2 * SD(logit PS)
# -----------------------------------------------------------------------------
cat("\n=== Step C: 1:1 PS matching ===\n")
cohorts <- cohorts[!is.na(cohorts$propensityScore), ]
cohorts$logitPs <- log(cohorts$propensityScore / (1 - cohorts$propensityScore))
caliper <- 0.2 * sd(cohorts$logitPs, na.rm = TRUE)
cat(sprintf("Caliper = %.4f (0.2 * SD logitPS)\n", caliper))

# Simple greedy 1:1 NN matching
matched <- local({
  tr <- cohorts[cohorts$treatment == 1, c("rowId", "logitPs", "siteIdx")]
  co <- cohorts[cohorts$treatment == 0, c("rowId", "logitPs", "siteIdx")]
  # sort T by random order
  set.seed(42)
  tr <- tr[sample(nrow(tr)), ]
  co_taken <- rep(FALSE, nrow(co))
  pair_tr <- integer(); pair_co <- integer(); pair_site <- integer()
  for (i in seq_len(nrow(tr))) {
    # candidates not taken
    cand_idx <- which(!co_taken)
    if (length(cand_idx) == 0) break
    diffs <- abs(co$logitPs[cand_idx] - tr$logitPs[i])
    best <- which.min(diffs)
    if (diffs[best] <= caliper) {
      pair_tr <- c(pair_tr, tr$rowId[i])
      pair_co <- c(pair_co, co$rowId[cand_idx[best]])
      pair_site <- c(pair_site, tr$siteIdx[i])
      co_taken[cand_idx[best]] <- TRUE
    }
  }
  data.frame(tr = pair_tr, co = pair_co, siteIdx = pair_site)
})
cat(sprintf("Matched pairs: %d\n", nrow(matched)))
cat("  By site:\n")
print(table(matched$siteIdx))

matched_rows <- c(matched$tr, matched$co)
m_cohorts <- cohorts[cohorts$rowId %in% matched_rows, ]

# -----------------------------------------------------------------------------
# Step D: Site-stratified Cox for each outcome
# -----------------------------------------------------------------------------
cat("\n=== Step D: Site-stratified Cox ===\n")

fit_one <- function(oid, oname) {
  # event flag + time to event (survival days within TAR 91-1185)
  out_sub <- outcomes[outcomes$outcomeId == oid & outcomes$rowId %in% m_cohorts$rowId &
                        outcomes$daysToEvent >= 91 & outcomes$daysToEvent <= 1185, ]
  # for each rowId, pick first event within window
  out_first <- out_sub[!duplicated(out_sub$rowId), ]
  m <- m_cohorts
  m$event <- as.integer(m$rowId %in% out_first$rowId)
  m$time <- ifelse(m$event == 1,
                   out_first$daysToEvent[match(m$rowId, out_first$rowId)],
                   1185)  # censoring = end of TAR
  m$time <- pmax(m$time, 1L)  # guard

  new_row <- tryCatch({
    fit <- survival::coxph(survival::Surv(time, event) ~ treatment + strata(siteIdx),
                           data = m, ties = "efron")
    s <- summary(fit)
    hr <- exp(coef(fit)[1])
    ci <- exp(confint(fit))
    data.frame(
      outcome_id = oid, outcome_name = oname,
      n_pairs = nrow(matched),
      events_t = sum(m$event[m$treatment == 1]),
      events_c = sum(m$event[m$treatment == 0]),
      logHr = coef(fit)[1], seLogHr = s$coefficients[1, 3],
      hr = hr, ci_lb = ci[1, 1], ci_ub = ci[1, 2],
      p = s$coefficients[1, 5],
      stringsAsFactors = FALSE
    )
  }, error = function(e) {
    data.frame(
      outcome_id = oid, outcome_name = oname,
      n_pairs = nrow(matched),
      events_t = NA_integer_, events_c = NA_integer_,
      logHr = NA_real_, seLogHr = NA_real_,
      hr = NA_real_, ci_lb = NA_real_, ci_ub = NA_real_, p = NA_real_,
      stringsAsFactors = FALSE
    )
  })
  new_row  # always local
}

res <- data.frame()
for (nm in names(ALL_OUT)) {
  r <- fit_one(ALL_OUT[[nm]], nm)
  cat(sprintf("  %-8s oid=%-8d evT=%-5s evC=%-5s HR=%-7s CI=[%-7s, %-7s] p=%s\n",
              nm, ALL_OUT[[nm]],
              as.character(r$events_t), as.character(r$events_c),
              ifelse(is.na(r$hr), "NA", sprintf("%.3f", r$hr)),
              ifelse(is.na(r$ci_lb), "NA", sprintf("%.3f", r$ci_lb)),
              ifelse(is.na(r$ci_ub), "NA", sprintf("%.3f", r$ci_ub)),
              ifelse(is.na(r$p), "NA", sprintf("%.3g", r$p))))
  res <- rbind(res, r)
}

# -----------------------------------------------------------------------------
# Step E: NC calibration (EmpiricalCalibration::fitNull + Schuemie 2014 manual CI)
# -----------------------------------------------------------------------------
cat("\n=== Step E: NC calibration ===\n")
nc_res <- res[grepl("^NC", res$outcome_name) & !is.na(res$logHr), ]
cat(sprintf("NC with valid HR: %d / %d\n", nrow(nc_res), length(NC_IDS)))
if (nrow(nc_res) >= 5) {
  null <- EmpiricalCalibration::fitNull(nc_res$logHr, nc_res$seLogHr)
  null_mean <- null[1]; null_sd <- null[2]
  cat(sprintf("Null distribution: mean=%.3f, sd=%.3f\n", null_mean, null_sd))
  cat(sprintf("NC geo.mean HR = %.3f (expected ≈ 1.0)\n", exp(median(nc_res$logHr))))

  # Schuemie 2014 manual calibration (avoid calibrateConfidenceInterval legacy bug)
  res$calLogHr <- res$logHr - null_mean
  res$calSe <- sqrt(res$seLogHr^2 + null_sd^2)
  res$calHr <- exp(res$calLogHr)
  res$calCiLb <- exp(res$calLogHr - 1.96 * res$calSe)
  res$calCiUb <- exp(res$calLogHr + 1.96 * res$calSe)
  res$calP <- 2 * pnorm(-abs(res$calLogHr) / res$calSe)
} else {
  cat("⚠️  NC valid count < 5 → skip calibration\n")
  res$calLogHr <- NA_real_; res$calSe <- NA_real_
  res$calHr <- NA_real_; res$calCiLb <- NA_real_; res$calCiUb <- NA_real_; res$calP <- NA_real_
}

# -----------------------------------------------------------------------------
# Step F: Save + summarize
# -----------------------------------------------------------------------------
out_csv <- file.path(OUT, "t1_rhinitis_3site_pilot.csv")
write.csv(res, out_csv, row.names = FALSE)
cat(sprintf("\nSaved: %s\n", out_csv))

cat("\n=== PRIMARY RESULTS ===\n")
primary <- res[res$outcome_name %in% names(PRIMARY_OUTCOMES), ]
for (i in seq_len(nrow(primary))) {
  r <- primary[i, ]
  cat(sprintf("[%s]  HR = %.3f [%.3f, %.3f]  p = %.3g  | calibrated HR = %.3f [%.3f, %.3f]  calP = %.3g\n",
              r$outcome_name,
              r$hr, r$ci_lb, r$ci_ub, r$p,
              r$calHr, r$calCiLb, r$calCiUb, r$calP))
}
