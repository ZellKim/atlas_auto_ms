# ⚠️  DEPRECATED 2026-04-24 — superseded by R/lib/ipd_pooled.R.
# Kept for reference only.
suppressPackageStartupMessages(library(EmpiricalCalibration))
df <- read.csv("C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output/v4_nofilter_nc_c1074_Chole.csv")
nc <- df[!is.na(df$logHr) & !is.na(df$seLogHr) &
         is.finite(df$logHr) & is.finite(df$seLogHr) &
         (df$evT + df$evC) >= 5 &
         abs(df$logHr) < log(10), ]
null <- fitNull(nc$logHr, nc$seLogHr)
cat("Null:\n"); print(null); cat("Class:", class(null), "\n")

# Try primary
prim <- read.csv("C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output/v4_nofilter_primary_c1074_Chole.csv")
cat("\nPrimary example:\n")
r1 <- prim[1, ]
cat("logHr:", r1$logHr, "  seLogHr:", r1$seLogHr, "\n")

# Call calibrateConfidenceInterval step-by-step
cat("\n-- Try calibrateConfidenceInterval (no legacy arg) --\n")
ci <- tryCatch(
  calibrateConfidenceInterval(logRr = r1$logHr, seLogRr = r1$seLogHr, null = null, ciWidth = 0.95),
  error = function(e) { cat("ERR:", conditionMessage(e), "\n"); NULL }
)
print(ci)

cat("\n-- Try with legacy=FALSE --\n")
ci2 <- tryCatch(
  calibrateConfidenceInterval(logRr = r1$logHr, seLogRr = r1$seLogHr, null = null, ciWidth = 0.95, legacy = FALSE),
  error = function(e) { cat("ERR:", conditionMessage(e), "\n"); NULL }
)
print(ci2)

cat("\n-- Try with legacy=TRUE --\n")
ci3 <- tryCatch(
  calibrateConfidenceInterval(logRr = r1$logHr, seLogRr = r1$seLogHr, null = null, ciWidth = 0.95, legacy = TRUE),
  error = function(e) { cat("ERR:", conditionMessage(e), "\n"); NULL }
)
print(ci3)

# Show function signature
cat("\n-- function signature --\n")
print(args(calibrateConfidenceInterval))

# Also try calibrateP
cat("\n-- calibrateP --\n")
p1 <- tryCatch(calibrateP(null, r1$logHr, r1$seLogHr), error = function(e) {cat("ERR:", conditionMessage(e), "\n"); NULL})
print(p1)
