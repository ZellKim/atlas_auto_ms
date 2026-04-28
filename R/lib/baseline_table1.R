# =============================================================================
# R/lib/baseline_table1.R
# Baseline Table 1 (publication-ready, exact N) — KB §5.5
#
# Reusable across studies. Reads row-level CmData sqlite from each site,
# applies lookback consistent with primary, exact-counts for pre/post matching,
# returns formatted Table 1 + raw balance object.
#
# Korean CDM safe (no Race/Ethnicity dependency). Handles drug covariateId
# int32 overflow (numeric promotion). Sanity checks vs primary analysis N.
#
# Usage:
#   source("R/lib/baseline_table1.R")
#   result <- build_table1(config)
#   # result$table1   = formatted publication csv-ready data.table
#   # result$balance  = full per-covariate exact N + means + SMD pre/post
#
# Dependencies: data.table, DBI, RSQLite. dplyr optional (only for top-prev pick).
# =============================================================================

suppressPackageStartupMessages({
  library(data.table); library(DBI); library(RSQLite)
})

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
.bt1_smd_bin <- function(pT, pC) {
  s <- sqrt((pT * (1 - pT) + pC * (1 - pC)) / 2)
  ifelse(s == 0, 0, (pT - pC) / s)
}

.bt1_fmt_np <- function(n, p) {
  sprintf("%s (%.1f%%)", format(round(n), big.mark = ","), 100 * p)
}

.bt1_fmt_smd <- function(s) {
  v <- sprintf("%+.2f", s)
  v[abs(s) < 0.005] <- "0.00"
  v
}

.bt1_clean_name <- function(s) {
  s <- gsub("^age group: *", "Age ", s)
  s <- gsub("^gender = *",   "",     s)
  s <- gsub("^drug_era group during day -365 through -1 days relative to index: *", "", s)
  s <- gsub("^condition_era group during day -365 through -1 days relative to index: *", "", s)
  s
}

# -----------------------------------------------------------------------------
# build_table1(config)
#
# config = list(
#   cmdata_root      = "C:/.../cmData_<study>",   # {site}/CmData_l1_t<T>_c<C>/*.sqlite
#   sites            = NULL or character vector  (NULL = autodetect)
#   target_id        = 1290L,
#   comparator_id    = 1287L,
#   primary_outcomes = c(1288L, 1289L),  # for lookback exclusion
#   lookback_days    = 365L,
#   matched_rds      = ".../matched.rds",
#   primary_csv      = ".../primary.csv",  # for N consistency check
#   spec_top_n_cond  = 10L,
#   spec_top_n_drug  = 8L,
#   extra_cov_ids    = NULL  # additional covariateIds to force include
# )
# -----------------------------------------------------------------------------
build_table1 <- function(config) {
  CMROOT  <- config$cmdata_root
  T_ID    <- as.integer(config$target_id)
  C_ID    <- as.integer(config$comparator_id)
  PRI     <- as.integer(config$primary_outcomes)
  LB      <- as.integer(config$lookback_days %||% 365L)
  TOP_C   <- as.integer(config$spec_top_n_cond %||% 10L)
  TOP_D   <- as.integer(config$spec_top_n_drug %||% 8L)

  if (is.null(config$sites)) {
    SITES <- sort(list.files(CMROOT))
    SITES <- SITES[file.exists(file.path(CMROOT, SITES,
                                          sprintf("CmData_l1_t%d_c%d", T_ID, C_ID)))]
  } else SITES <- config$sites
  cat(sprintf("[Table1] Sites: %d\n", length(SITES)))

  # -------------------------------------------------------------------------
  # Stage 1: get superset of candidate covariateIds in target analysisIds
  # via covariateRef (small) from one site. Set is consistent across sites.
  # -------------------------------------------------------------------------
  ref_sqf  <- list.files(file.path(CMROOT, SITES[1],
                                    sprintf("CmData_l1_t%d_c%d", T_ID, C_ID)),
                         pattern = "\\.sqlite$", full.names = TRUE)[1]
  con <- dbConnect(SQLite(), ref_sqf)
  ref_names <- as.data.table(dbGetQuery(con,
    "SELECT covariateId, covariateName FROM covariateRef"))
  dbDisconnect(con)
  ref_names[, covariateId := as.numeric(covariateId)]
  ref_names[, analysisId := as.integer(covariateId %% 1000)]

  candidate_cids <- ref_names[analysisId %in% c(1L, 3L, 210L, 410L), covariateId]
  if (!is.null(config$extra_cov_ids))
    candidate_cids <- unique(c(candidate_cids, as.numeric(config$extra_cov_ids)))
  cid_sql_all <- paste(format(candidate_cids, scientific = FALSE, trim = TRUE),
                        collapse = ",")
  cat(sprintf("[Table1] Candidate covariates (analysisId 1/3/210/410): %d\n",
              length(candidate_cids)))

  # -------------------------------------------------------------------------
  # Read each site, apply offset, pool, exclude lookback rowIds
  # -------------------------------------------------------------------------
  all_cov <- vector("list", length(SITES))
  all_coh <- vector("list", length(SITES))
  prior_ids <- integer(0)
  for (si in seq_along(SITES)) {
    off <- (si - 1L) * 100000000L
    sqf <- list.files(file.path(CMROOT, SITES[si],
                                  sprintf("CmData_l1_t%d_c%d", T_ID, C_ID)),
                       pattern = "\\.sqlite$", full.names = TRUE)[1]
    con <- dbConnect(SQLite(), sqf)
    cov <- as.data.table(dbGetQuery(con, sprintf(
      "SELECT rowId, covariateId, covariateValue FROM covariates WHERE covariateId IN (%s)",
      cid_sql_all)))
    coh <- as.data.table(dbGetQuery(con, "SELECT rowId, treatment FROM cohorts"))
    oc  <- as.data.table(dbGetQuery(con, sprintf(
      "SELECT rowId FROM outcomes WHERE outcomeId IN (%s) AND daysToEvent < 0 AND daysToEvent >= %d",
      paste(PRI, collapse = ","), -LB)))
    dbDisconnect(con)
    cov[, rowId := as.integer(rowId) + off]
    cov[, covariateId := as.numeric(covariateId)]
    coh[, rowId := as.integer(rowId) + off]
    if (nrow(oc) > 0) prior_ids <- c(prior_ids, unique(as.integer(oc$rowId) + off))
    all_cov[[si]] <- cov; all_coh[[si]] <- coh
  }
  cov_pool <- rbindlist(all_cov)
  coh_pool <- rbindlist(all_coh)
  cat(sprintf("[Table1] Pool raw: cohort %d, cov %d  | lookback excl: %d\n",
              nrow(coh_pool), nrow(cov_pool), length(prior_ids)))
  coh_pool <- coh_pool[!rowId %in% prior_ids]
  cov_pool <- cov_pool[!rowId %in% prior_ids]

  # -------------------------------------------------------------------------
  # Pre/post match exact N
  # -------------------------------------------------------------------------
  matched <- readRDS(config$matched_rds)
  matched_ids <- as.integer(matched$rowId)
  nT_pre  <- coh_pool[treatment == 1, .N]
  nC_pre  <- coh_pool[treatment == 0, .N]
  nT_post <- coh_pool[rowId %in% matched_ids & treatment == 1, .N]
  nC_post <- coh_pool[rowId %in% matched_ids & treatment == 0, .N]

  cat(sprintf("[Table1] Exact N: pre  T=%d C=%d  post T=%d C=%d\n",
              nT_pre, nC_pre, nT_post, nC_post))

  # Sanity vs primary.csv
  if (!is.null(config$primary_csv) && file.exists(config$primary_csv)) {
    prim <- read.csv(config$primary_csv)
    expN <- prim$nT[1] + prim$nC[1]
    if (expN != nT_post + nC_post) {
      warning(sprintf("Post-match N mismatch: primary.csv expects %d, table1 has %d",
                      expN, nT_post + nC_post))
    }
  }

  cov_pool <- merge(cov_pool, coh_pool, by = "rowId")

  count_set <- function(dt, nT, nC) {
    dt[, .(sumT = sum(covariateValue * (treatment == 1L)),
            sumC = sum(covariateValue * (treatment == 0L))),
        by = covariateId][
      , `:=`(meanT = sumT / nT, meanC = sumC / nC)][
      , smd := .bt1_smd_bin(meanT, meanC)][]
  }
  pre  <- count_set(cov_pool, nT_pre, nC_pre)
  post <- count_set(cov_pool[rowId %in% matched_ids], nT_post, nC_post)

  # -------------------------------------------------------------------------
  # Stage 2: select top by POOLED pre-match max(meanT, meanC) per analysisId
  # -------------------------------------------------------------------------
  pre_with_ai <- merge(pre, ref_names[, .(covariateId, analysisId)],
                        by = "covariateId", all.x = TRUE)
  pre_with_ai[, max_prev := pmax(meanT, meanC)]
  age_ids    <- pre_with_ai[analysisId == 3L,   covariateId]
  gender_ids <- pre_with_ai[analysisId == 1L,   covariateId]
  cond_ids   <- pre_with_ai[analysisId == 210L][order(-max_prev)][1:TOP_C, covariateId]
  drug_ids   <- pre_with_ai[analysisId == 410L][order(-max_prev)][1:TOP_D, covariateId]
  needed_cids <- unique(c(age_ids, gender_ids, cond_ids, drug_ids,
                          as.numeric(config$extra_cov_ids)))
  needed_cids <- needed_cids[!is.na(needed_cids)]
  cat(sprintf("[Table1] Selected (pooled top): age %d, gender %d, cond %d, drug %d\n",
              length(age_ids), length(gender_ids), length(cond_ids), length(drug_ids)))
  pre  <- pre [covariateId %in% needed_cids]
  post <- post[covariateId %in% needed_cids]

  bal <- merge(
    pre[, .(covariateId, sumT_pre = sumT, sumC_pre = sumC,
             meanT_pre = meanT, meanC_pre = meanC, smd_pre = smd)],
    post[, .(covariateId, sumT_post = sumT, sumC_post = sumC,
              meanT_post = meanT, meanC_post = meanC, smd_post = smd)],
    by = "covariateId", all = TRUE)
  bal <- merge(bal, ref_names[, .(covariateId, covariateName)],
                by = "covariateId", all.x = TRUE)
  bal[, analysisId := as.integer(covariateId %% 1000)]
  bal[, conceptId  := as.integer((covariateId - analysisId) / 1000)]

  # -------------------------------------------------------------------------
  # Build publication table
  # -------------------------------------------------------------------------
  tag_section <- function(label) data.table(
    Characteristic = label,
    bf_T = "", bf_C = "", bf_SMD = "",
    af_T = "", af_C = "", af_SMD = "")
  tag_row <- function(name, br) data.table(
    Characteristic = paste0("  ", name),
    bf_T   = .bt1_fmt_np(br$sumT_pre,  br$meanT_pre),
    bf_C   = .bt1_fmt_np(br$sumC_pre,  br$meanC_pre),
    bf_SMD = .bt1_fmt_smd(br$smd_pre),
    af_T   = .bt1_fmt_np(br$sumT_post, br$meanT_post),
    af_C   = .bt1_fmt_np(br$sumC_post, br$meanC_post),
    af_SMD = .bt1_fmt_smd(br$smd_post))

  bf <- bal[order(analysisId, -meanT_pre)]
  build_section <- function(label, ais) {
    rows <- bf[analysisId %in% ais]
    if (nrow(rows) == 0) return(NULL)
    out <- list(tag_section(label))
    for (i in seq_len(nrow(rows))) {
      rr <- rows[i]; rr$covariateName <- .bt1_clean_name(rr$covariateName)
      out[[length(out)+1]] <- tag_row(rr$covariateName, rr)
    }
    rbindlist(out)
  }

  t1 <- rbindlist(list(
    data.table(Characteristic = sprintf(
        "Pre-match: T=%s, C=%s   Post-match: T=%s, C=%s (1:1)",
        format(nT_pre,  big.mark=","), format(nC_pre,  big.mark=","),
        format(nT_post, big.mark=","), format(nC_post, big.mark=",")),
        bf_T="", bf_C="", bf_SMD="", af_T="", af_C="", af_SMD=""),
    build_section("Demographics — Age",                       3L),
    build_section("Demographics — Gender",                    1L),
    build_section(sprintf("Medical history (1 yr prior, top %d)", TOP_C), 210L),
    build_section(sprintf("Medication use (1 yr prior, top %d)", TOP_D),  410L)
  ))
  setnames(t1, c("bf_T","bf_C","bf_SMD","af_T","af_C","af_SMD"),
           c("Before T","Before C","Before SMD","After T","After C","After SMD"))

  list(table1 = t1, balance = bal,
       n = list(nT_pre = nT_pre, nC_pre = nC_pre,
                 nT_post = nT_post, nC_post = nC_post))
}

# null-coalesce helper
`%||%` <- function(a, b) if (is.null(a)) b else a
