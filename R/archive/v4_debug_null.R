# ⚠️  DEPRECATED 2026-04-24 — superseded by R/lib/ipd_pooled.R.
# Kept for reference only.
suppressPackageStartupMessages(library(EmpiricalCalibration))
df <- read.csv("C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output/v4_nofilter_nc_c1074_Chole.csv")
nc <- df[!is.na(df$logHr) & !is.na(df$seLogHr) &
         is.finite(df$logHr) & is.finite(df$seLogHr) &
         (df$evT + df$evC) >= 5 &
         abs(df$logHr) < log(10), ]
cat("Usable NC:", nrow(nc), "\n")
cat("logHr sd:", sd(nc$logHr), "  mean:", mean(nc$logHr), "\n")
cat("seLogHr mean:", mean(nc$seLogHr), "\n\n")

# Also fit "normal null" (non-MCMC) — simpler
nullNormal <- fitNull(nc$logHr, nc$seLogHr)
cat("fitNull result (classic method-of-moments):\n")
print(nullNormal)

# MCMC version
nullMcmc <- fitMcmcNull(nc$logHr, nc$seLogHr)
cat("\nfitMcmcNull result:\n")
print(nullMcmc)

# Check attributes / distribution
cat("\nMCMC summary:\n")
if (!is.null(attr(nullMcmc, "mcmc"))) {
  mcmc <- attr(nullMcmc, "mcmc")
  cat("chain rows:", nrow(mcmc$chain), "\n")
  cat("chain mean:\n"); print(colMeans(mcmc$chain))
  cat("chain sd:\n"); print(apply(mcmc$chain, 2, sd))
  cat("chain range:\n"); print(apply(mcmc$chain, 2, range))
}

# Try calibration with normal null
cat("\n--- Calibrate using fitNull (classical) ---\n")
testLogRr <- c(-0.5, 0, 0.5, 1.0, -1.0)
testSe    <- rep(0.1, 5)
for (i in seq_along(testLogRr)) {
  ci <- calibrateConfidenceInterval(testLogRr[i], testSe[i], nullNormal, ciWidth = 0.95)
  cat(sprintf("  logRr=%.2f se=%.2f → calibrated: HR=%.3f (%.3f-%.3f)\n",
              testLogRr[i], testSe[i], exp(ci$logRr), exp(ci$logLb95Rr), exp(ci$logUb95Rr)))
}
