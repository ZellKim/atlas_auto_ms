#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(DBI)
  library(RSQLite)
})

parse_args <- function(args) {
  parsed <- list()
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (!startsWith(key, "--")) stop(sprintf("Unexpected argument: %s", key))
    name <- sub("^--", "", key)
    if (i == length(args) || startsWith(args[[i + 1L]], "--")) {
      parsed[[name]] <- TRUE
      i <- i + 1L
    } else {
      parsed[[name]] <- args[[i + 1L]]
      i <- i + 2L
    }
  }
  parsed
}

split_ints <- function(x) {
  as.integer(strsplit(x, ",", fixed = TRUE)[[1L]])
}

query_one <- function(con, sql) {
  DBI::dbGetQuery(con, sql)[[1L]][1L]
}

cmdata_dir <- function(root, site, target_id, comparator_id, analysis = NULL) {
  tag <- sprintf("CmData_l1_t%d_c%d", target_id, comparator_id)
  if (is.null(analysis) || identical(analysis, "")) {
    file.path(root, site, tag)
  } else {
    file.path(root, site, analysis, tag)
  }
}

validate_sqlite <- function(sqf) {
  con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
  on.exit(DBI::dbDisconnect(con), add = TRUE)

  tables <- DBI::dbListTables(con)
  required <- c("cohorts", "outcomes", "covariates", "covariateRef")
  missing <- setdiff(required, tables)
  if (length(missing) > 0L) {
    return(data.frame(
      status = "missing_table",
      missing = paste(missing, collapse = ";"),
      stringsAsFactors = FALSE
    ))
  }

  cohort_cols <- DBI::dbGetQuery(con, "PRAGMA table_info(cohorts)")$name
  has_person_id <- "personId" %in% cohort_cols
  has_person_seq_id <- "personSeqId" %in% cohort_cols

  cohort_sql <- paste0(
    "SELECT ",
    "COUNT(*) AS cohort_n, ",
    "COUNT(DISTINCT rowId) AS distinct_rowid, ",
    "SUM(CASE WHEN treatment = 1 THEN 1 ELSE 0 END) AS n_t, ",
    "SUM(CASE WHEN treatment = 0 THEN 1 ELSE 0 END) AS n_c, ",
    "SUM(CASE WHEN treatment NOT IN (0, 1) OR treatment IS NULL THEN 1 ELSE 0 END) AS bad_treatment, ",
    "SUM(CASE WHEN daysToObsEnd IS NULL THEN 1 ELSE 0 END) AS null_obs_end",
    if (has_person_id) ", COUNT(DISTINCT personId) AS distinct_person_id" else ", NULL AS distinct_person_id",
    if (has_person_seq_id) ", COUNT(DISTINCT personSeqId) AS distinct_person_seq_id" else ", NULL AS distinct_person_seq_id",
    " FROM cohorts"
  )

  cohort <- DBI::dbGetQuery(con, cohort_sql)
  cov <- DBI::dbGetQuery(
    con,
    "SELECT COUNT(*) AS cov_n, COUNT(DISTINCT rowId) AS cov_rowids FROM covariates"
  )
  outcome <- DBI::dbGetQuery(
    con,
    paste0(
      "SELECT COUNT(*) AS outcome_n, COUNT(DISTINCT rowId) AS outcome_rowids, ",
      "COUNT(DISTINCT outcomeId) AS outcome_ids FROM outcomes"
    )
  )
  covref <- DBI::dbGetQuery(
    con,
    "SELECT COUNT(*) AS covariate_ref_n, COUNT(DISTINCT covariateId) AS covariate_ref_ids FROM covariateRef"
  )

  cov_orphan <- query_one(
    con,
    "SELECT COUNT(*) FROM (SELECT DISTINCT rowId FROM covariates EXCEPT SELECT rowId FROM cohorts)"
  )
  outcome_orphan <- query_one(
    con,
    "SELECT COUNT(*) FROM (SELECT DISTINCT rowId FROM outcomes EXCEPT SELECT rowId FROM cohorts)"
  )

  status <- "ok"
  if (cohort$cohort_n != cohort$distinct_rowid ||
      cohort$bad_treatment > 0 ||
      cohort$null_obs_end > 0 ||
      cov_orphan > 0 ||
      outcome_orphan > 0) {
    status <- "fail"
  }

  data.frame(
    status = status,
    missing = "",
    cohort,
    cov,
    outcome,
    covref,
    cov_orphan = cov_orphan,
    outcome_orphan = outcome_orphan,
    stringsAsFactors = FALSE
  )
}

main <- function() {
  args <- parse_args(commandArgs(trailingOnly = TRUE))
  if (is.null(args$root) || is.null(args$targets) || is.null(args$comparator)) {
    stop("Usage: Rscript R/validate_cmdata_patient_level.R --root <dir> --targets 1406,1407 --comparator 1411 [--sites auto] [--analysis name] [--out file.csv]")
  }

  root <- args$root
  target_ids <- split_ints(args$targets)
  comparator_id <- as.integer(args$comparator)
  analysis <- args$analysis
  sites <- if (is.null(args$sites) || identical(args$sites, "auto")) {
    sort(list.files(root))
  } else {
    strsplit(args$sites, ",", fixed = TRUE)[[1L]]
  }

  rows <- list()
  row_idx <- 1L
  for (site in sites) {
    for (target_id in target_ids) {
      d <- cmdata_dir(root, site, target_id, comparator_id, analysis)
      sqf <- list.files(d, pattern = "\\.sqlite$", full.names = TRUE)[1L]
      if (is.na(sqf)) {
        rows[[row_idx]] <- data.frame(
          site = site,
          target_id = target_id,
          comparator_id = comparator_id,
          sqlite = NA_character_,
          status = "missing_sqlite",
          stringsAsFactors = FALSE
        )
        row_idx <- row_idx + 1L
        next
      }

      check <- tryCatch(
        validate_sqlite(sqf),
        error = function(e) data.frame(
          status = "error",
          missing = conditionMessage(e),
          stringsAsFactors = FALSE
        )
      )
      rows[[row_idx]] <- cbind(
        data.frame(
          site = site,
          target_id = target_id,
          comparator_id = comparator_id,
          sqlite = sqf,
          stringsAsFactors = FALSE
        ),
        check
      )
      row_idx <- row_idx + 1L
    }
  }

  result <- do.call(rbind, rows)
  print(table(result$status, useNA = "ifany"))
  display_cols <- intersect(
    c("site", "target_id", "status", "cohort_n", "n_t", "n_c",
      "cov_rowids", "outcome_rowids", "cov_orphan", "outcome_orphan"),
    names(result)
  )
  print(result[, display_cols], row.names = FALSE)

  if (!is.null(args$out)) {
    utils::write.csv(result, args$out, row.names = FALSE)
    cat(sprintf("Saved: %s\n", args$out))
  }

  invisible(result)
}

main()
