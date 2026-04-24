# Table 1 with SMD for 15-site 365d main analysis
# Reproduces the matched cohort and computes SMD for covariates

Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
suppressPackageStartupMessages({
  library(Cyclops); library(DBI); library(RSQLite); library(dplyr); library(tidyr)
})

WORKSPACE <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_ipd_workspace"
OUT_DIR   <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_pooled_output"

SITES <- c("AUMC","CHNUH","DCMC","GNUCH","GNUH","HUMC","ISH","JCMJ","KDH","KHNMC","KWMC","SCHBC","SCHCA","SCHGM","SCHSU","WKUH")
ANALYSES <- c("v4_1a_cbc_wbc","v4_1b_cbc_rbc","v4_2_chem_hepa","v4_3_meta_endo")
COMPARATORS <- list(list(id=1074, name="Chole"), list(id=1121, name="Hernia"))
LOOKBACK_DAYS <- 365

PRIMARY_OUTCOMES <- list(
  v4_1a_cbc_wbc  = c(1357,1390,1391,1392,1360,1385,1373,1374),
  v4_1b_cbc_rbc  = c(1375,1362,1368,1358,1387,1395,1394,1393),
  v4_2_chem_hepa = c(1370,1369,1364,1365,1363,1400,1366,1381,1384,1397,1396),
  v4_3_meta_endo = c(1378,1379,1402,1401,1367,1399,1398,1404)
)
ALL_PRIMARY <- unname(as.integer(unlist(PRIMARY_OUTCOMES)))

loadCm <- function(site, analysis, cid) {
  d <- file.path(WORKSPACE, site, analysis, sprintf("CmData_l1_t1072_c%d", cid))
  sqf <- list.files(d, pattern="\\.sqlite$", full.names=TRUE)[1]
  if (is.na(sqf)) return(NULL)
  con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
  res <- list(
    cohorts = DBI::dbReadTable(con,"cohorts"),
    outcomes = DBI::dbReadTable(con,"outcomes"),
    covariates = DBI::dbReadTable(con,"covariates"),
    covariateRef = DBI::dbReadTable(con,"covariateRef")
  )
  DBI::dbDisconnect(con); res
}

buildPooled <- function(cid) {
  allC <- list(); allO <- list(); allCov <- list(); covRef <- list()
  for (si in seq_along(SITES)) {
    site <- SITES[si]; offset <- (si-1)*100000000L
    cm <- loadCm(site, "v4_1a_cbc_wbc", cid); if (is.null(cm)) next
    coh <- cm$cohorts; coh$rowId <- as.integer(coh$rowId)+offset; coh$personSeqId <- NULL; coh$site <- site
    covA <- cm$covariates; covA$rowId <- as.integer(covA$rowId)+offset
    so <- list()
    for (a in ANALYSES) {
      cma <- loadCm(site, a, cid); if (is.null(cma)) next
      oc <- cma$outcomes; oc$rowId <- as.integer(oc$rowId)+offset
      so[[a]] <- oc
    }
    oc_all <- bind_rows(so) %>% distinct(rowId, outcomeId, daysToEvent, .keep_all=TRUE)
    allC[[site]] <- coh; allO[[site]] <- oc_all; allCov[[site]] <- covA
    covRef[[length(covRef)+1]] <- cm$covariateRef
  }
  list(cohorts=bind_rows(allC), outcomes=bind_rows(allO), covariates=bind_rows(allCov),
       covariateRef=bind_rows(covRef) %>% distinct(covariateId, .keep_all=TRUE))
}

applyFullUnion365 <- function(pool, ids, lb) {
  prior <- pool$outcomes %>% filter(outcomeId %in% ids, daysToEvent < 0, daysToEvent >= -lb) %>% pull(rowId) %>% unique()
  pool$cohorts <- pool$cohorts[!pool$cohorts$rowId %in% prior, ]
  pool$outcomes <- pool$outcomes[!pool$outcomes$rowId %in% prior, ]
  pool$covariates <- pool$covariates[!pool$covariates$rowId %in% prior, ]
  pool
}

fitPs <- function(pool, maxCompFit=150000L) {
  coh <- pool$cohorts; cov <- pool$covariates
  nC <- sum(coh$treatment==0)
  if (nC > maxCompFit) {
    set.seed(42); sampled <- sample(coh$rowId[coh$treatment==0], maxCompFit)
    fitIds <- c(coh$rowId[coh$treatment==1], sampled)
    fitCoh <- coh[coh$rowId %in% fitIds, ]; fitCov <- cov[cov$rowId %in% fitIds, ]
  } else { fitCoh <- coh; fitCov <- cov }
  outY <- data.frame(rowId=fitCoh$rowId, y=fitCoh$treatment)
  cyD <- Cyclops::convertToCyclopsData(outY, fitCov[,c("rowId","covariateId","covariateValue")], modelType="lr", addIntercept=TRUE)
  prior <- Cyclops::createPrior("laplace", useCrossValidation=TRUE, variance=1, exclude=0, forceIntercept=FALSE)
  ctrl <- Cyclops::createControl(maxIterations=1000, tolerance=2e-7, convergenceType="gradient", cvType="auto", fold=10, seed=42, noiseLevel="quiet")
  fit <- Cyclops::fitCyclopsModel(cyD, prior=prior, control=ctrl)
  if (nC > maxCompFit) {
    fullY <- data.frame(rowId=coh$rowId, y=coh$treatment)
    fullCy <- Cyclops::convertToCyclopsData(fullY, cov[,c("rowId","covariateId","covariateValue")], modelType="lr", addIntercept=TRUE)
    coh$ps <- predict(fit, newCyclopsData=fullCy, type="response")
    return(coh)
  }
  fitCoh$ps <- predict(fit, type="response"); fitCoh
}

matchOne <- function(cohPs, caliperMult=0.2) {
  cohPs$logitPs <- log(pmax(cohPs$ps,1e-8)/pmax(1-cohPs$ps,1e-8))
  caliper <- caliperMult*sd(cohPs$logitPs)
  tgt <- cohPs[cohPs$treatment==1,]; cmp <- cohPs[cohPs$treatment==0,]
  if (nrow(tgt) <= nrow(cmp)) { anchor <- tgt; pool <- cmp }
  else                        { anchor <- cmp; pool <- tgt }
  set.seed(42); order_a <- sample(nrow(anchor)); used <- logical(nrow(pool))
  mA <- integer(0); mP <- integer(0); pL <- pool$logitPs
  for (ai in order_a) {
    ds <- abs(pL - anchor$logitPs[ai])
    cand <- which(ds <= caliper & !used); if (!length(cand)) next
    best <- cand[order(ds[cand])[1]]
    mA <- c(mA, ai); mP <- c(mP, best); used[best] <- TRUE
  }
  rbind(anchor[unique(mA),], pool[mP,])
}

generateTable1 <- function(matched, covariates, covariateRef, cid, cname) {
  covRef <- covariateRef %>% select(covariateId, covariateName)
  cov_long <- covariates %>% inner_join(matched[,c("rowId","treatment")], by="rowId")
  cov_summary <- cov_long %>%
    group_by(covariateId, treatment) %>%
    summarise(n_present = n_distinct(rowId), .groups = "drop") %>%
    left_join(matched %>% group_by(treatment) %>% summarise(n_total=n_distinct(rowId), .groups="drop"), by="treatment") %>%
    mutate(prop = n_present / n_total) %>%
    select(covariateId, treatment, prop, n_present, n_total) %>%
    pivot_wider(id_cols = covariateId, names_from = treatment,
                values_from = c(prop, n_present), names_sep = "_t")
  cov_summary <- cov_summary %>%
    mutate(
      p_t = ifelse(is.na(prop_t1), 0, prop_t1),
      p_c = ifelse(is.na(prop_t0), 0, prop_t0),
      smd = (p_t - p_c) / sqrt((p_t*(1-p_t) + p_c*(1-p_c))/2 + 1e-10)
    ) %>%
    left_join(covRef, by = "covariateId") %>%
    arrange(desc(abs(smd)))
  top <- head(cov_summary, 300) %>%
    transmute(covariateId, covariateName,
              n_T = n_present_t1, n_C = n_present_t0,
              prop_T = round(p_t, 4), prop_C = round(p_c, 4),
              SMD = round(smd, 4))
  outPath <- file.path(OUT_DIR, sprintf("v4_fu365d_table1_c%d_%s.csv", cid, cname))
  write.csv(top, outPath, row.names = FALSE)
  cat(sprintf("  Saved %s: %d covariates, max|SMD|=%.3f, SMD>0.10: %d\n",
              outPath, nrow(top), max(abs(top$SMD), na.rm=TRUE), sum(abs(top$SMD) > 0.10)))
  top
}

# ===== MAIN =====
for (comp in COMPARATORS) {
  cid <- comp$id; cname <- comp$name
  cat(sprintf("\n=== %s (c=%d) — 15-site 365d main ===\n", cname, cid))
  pool <- buildPooled(cid)
  pool_fu <- applyFullUnion365(pool, ALL_PRIMARY, LOOKBACK_DAYS)
  cat(sprintf("  After filter: T=%d, C=%d\n", sum(pool_fu$cohorts$treatment==1), sum(pool_fu$cohorts$treatment==0)))
  psCoh <- fitPs(pool_fu)
  matched <- matchOne(psCoh)
  cat(sprintf("  Matched: %d pairs\n", nrow(matched)/2))
  generateTable1(matched, pool_fu$covariates, pool_fu$covariateRef, cid, cname)
}

cat("\n=== DONE ===\n")
