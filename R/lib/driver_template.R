# =============================================================================
# IPD Pooled Analysis Driver Template
# Copy to studies/{연구}/R/run_main.R and fill in config.
# =============================================================================

Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
source("G:/내 드라이브/KHNMC/atlas_auto_with_claude/R/lib/ipd_pooled.R")

config <- list(
  # Where CmData SQLite files live. Directory layout:
  #   single analysis:  {cmdata_root}/{site}/CmData_l1_t{T}_c{C}/*.sqlite
  #   multi analysis:   {cmdata_root}/{site}/{analysis}/CmData_l1_t{T}_c{C}/*.sqlite
  cmdata_root = "C:/Users/data1/Desktop/atlas_auto_cmdata/{STUDY}/cmData",

  # Site names matching directory names under cmdata_root.
  sites = c("AUMC_5.3.1_11", "CHNUH_5.3.1_01" # , ...
            ),

  # ATLAS cohort IDs.
  target_id     = 0L,   # e.g., 1290L = T1 allergic rhinitis
  comparator_id = 0L,   # e.g., 1287L = C1 non-allergic

  # NULL for single-analysis study. For multi-analysis (v4-style):
  #   c("v4_1a_cbc_wbc", "v4_1b_cbc_rbc", ...) — outcomes unioned across all.
  analyses = NULL,

  # Primary outcome IDs (what you want HR for).
  # If using dual_unit_map, include pseudo IDs here (not the variants).
  primary_outcomes = c(),

  # NC outcomes. NULL → auto-detect = all non-primary IDs in pool (recommended
  # when estimation spec carried 54 standard NCs in negativeControls).
  nc_outcomes = NULL,

  # Time-at-risk window, days from index.
  risk_window = c(91L, 1185L),  # e.g., lag 90d + 3y TAR

  # Lookback filter: subjects with any prior primary-outcome within N days
  # before index are dropped (Full Union filter).
  lookback_days = 365L,

  # Optional: clinical-state combining (dual-unit measurements, etc.).
  # Pseudo concept_id → c(variant_ids to relabel). Example:
  #   list("9001" = c(1370, 1369))  # CRP mg/dL + mg/L → 9001
  dual_unit_map = NULL,

  # Optional: landmark interval Cox (NON-overlapping windows from index).
  # NULL → step skipped (default).
  # Set ONLY if your hypothesis benefits from interval decomposition (e.g.
  # appendectomy: acute post-op vs late complication). For lag×TAR sliding
  # sensitivity (e.g. allergic study: lag 0/30/90/180 × TAR 3y/5y), DO NOT
  # use this — write a separate driver looping risk_window instead.
  # Appendectomy-style default reference (uncomment per-study only):
  #   time_windows = list(c(1, 30), c(31, 90), c(91, 365), c(366, 1095), c(1096, 3650))
  time_windows = NULL
)

OUT <- "C:/Users/data1/Desktop/atlas_auto_cmdata/{STUDY}/pooled_output"
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

result <- run_ipd_pooled(config)

write.csv(result$primary,     file.path(OUT, "primary.csv"),     row.names = FALSE)
write.csv(result$nc,          file.path(OUT, "nc.csv"),          row.names = FALSE)
if (!is.null(result$timewindow))
  write.csv(result$timewindow, file.path(OUT, "timewindow.csv"), row.names = FALSE)
write.csv(result$diagnostics, file.path(OUT, "diagnostics.csv"), row.names = FALSE)

cat("\n=== PRIMARY ===\n")
print(result$primary[, c("outcomeId", "evT", "evC", "hr", "ciLb", "ciUb", "calHr", "calP")])
cat(sprintf("\nNull: mean=%.3f, sd=%.3f, n_used=%d\n",
            result$null$mean, result$null$sd, result$null$n_used))
cat(sprintf("Matched pairs: %d | Primary OK: %d\n",
            result$diagnostics$n_matched_pairs,
            result$diagnostics$n_primary_ok))
