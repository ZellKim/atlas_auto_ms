# Quick verification: load one CmData SQLite from each study's new path.
Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")
suppressPackageStartupMessages({
  library(DBI); library(RSQLite)
})

check <- function(label, path) {
  sqf <- list.files(path, pattern = "\\.sqlite$", full.names = TRUE)[1]
  if (is.na(sqf)) { cat(sprintf("[%s] ❌ no sqlite in %s\n", label, path)); return() }
  con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
  tbls <- DBI::dbListTables(con)
  n_coh <- DBI::dbGetQuery(con, "SELECT COUNT(*) n FROM cohorts")$n
  DBI::dbDisconnect(con)
  cat(sprintf("[%s] ✅ tables=%d, cohorts rows=%d, file=%s\n",
              label, length(tbls), n_coh, basename(sqf)))
}

check("appendectomy/v4",
      "C:/Users/data1/Desktop/atlas_auto_cmdata/appendectomy/v4/cmData/AUMC/v4_1a_cbc_wbc/CmData_l1_t1072_c1074")

check("allergic_diseases",
      "C:/Users/data1/Desktop/atlas_auto_cmdata/allergic_diseases/cmData/AUMC_5.3.1_11/CmData_l1_t1290_c1287")

cat("\nVerification complete.\n")
