# Compare v4 Chole via lib to v4 canonical output.
# Numerical diff on hr, ciLb, ciUb, calHr, calP.
CANONICAL <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output/v4_fu365d_primary.csv"
NEW       <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_lib_regression_output/v4_chole_via_lib_primary.csv"

cn <- read.csv(CANONICAL)
nw <- read.csv(NEW)
cn <- cn[cn$comparator == "Chole", ]
cat(sprintf("Canonical Chole rows: %d | New: %d\n", nrow(cn), nrow(nw)))

m <- merge(cn[, c("outcomeId","evT","evC","hr","ciLb","ciUb","calHr","calP")],
           nw[, c("outcomeId","evT","evC","hr","ciLb","ciUb","calHr","calP")],
           by = "outcomeId", suffixes = c(".canonical", ".new"))

m$d_evT   <- m$evT.new - m$evT.canonical
m$d_evC   <- m$evC.new - m$evC.canonical
m$d_hr    <- m$hr.new - m$hr.canonical
m$d_calHr <- m$calHr.new - m$calHr.canonical
m$d_calP  <- m$calP.new - m$calP.canonical

cat("\n=== Row-by-row diff (|d_*| > 1e-4 flagged) ===\n")
cat(sprintf("%-10s %5s %5s %8s %8s %8s %8s %8s\n",
            "outcomeId", "evT", "evC", "hr.can", "hr.new", "d_hr", "d_calHr", "d_calP"))
max_d_hr <- 0; max_d_calHr <- 0; max_d_calP <- 0
for (i in seq_len(nrow(m))) {
  r <- m[i, ]
  flag_hr    <- abs(r$d_hr) > 1e-4
  flag_calHr <- abs(r$d_calHr) > 1e-4
  flag_calP  <- abs(r$d_calP) > 1e-4
  flag <- flag_hr || flag_calHr || flag_calP
  if (!is.na(r$d_hr))    max_d_hr    <- max(max_d_hr, abs(r$d_hr), na.rm = TRUE)
  if (!is.na(r$d_calHr)) max_d_calHr <- max(max_d_calHr, abs(r$d_calHr), na.rm = TRUE)
  if (!is.na(r$d_calP))  max_d_calP  <- max(max_d_calP, abs(r$d_calP), na.rm = TRUE)
  cat(sprintf("%-10d %5d %5d %8.4f %8.4f %8.4g %8.4g %8.4g  %s\n",
              r$outcomeId, r$evT.canonical, r$evC.canonical,
              r$hr.canonical, r$hr.new, r$d_hr, r$d_calHr, r$d_calP,
              if (flag) "*" else ""))
}

cat(sprintf("\nMax abs diff: hr=%.3g, calHr=%.3g, calP=%.3g\n",
            max_d_hr, max_d_calHr, max_d_calP))
cat(sprintf("evT differences: %s\n", paste(unique(m$d_evT[m$d_evT != 0]), collapse = ", ")))
cat(sprintf("evC differences: %s\n", paste(unique(m$d_evC[m$d_evC != 0]), collapse = ", ")))
