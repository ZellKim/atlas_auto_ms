d <- "C:/Users/data1/Desktop/atlas_auto_cmdata/v4_ipd_workspace/CHNUH/v4_1a_cbc_wbc/CmData_l1_t1072_c1074"
sqf <- list.files(d, pattern = "\\.sqlite$", full.names = TRUE)[1]
con <- DBI::dbConnect(RSQLite::SQLite(), sqf)
cat("tables:", paste(DBI::dbListTables(con), collapse = ","), "\n")
for (t in DBI::dbListTables(con)) {
  d2 <- DBI::dbGetQuery(con, paste0("SELECT * FROM ", t, " LIMIT 1"))
  cat(sprintf("  %s: %s\n", t, paste(names(d2), collapse = ",")))
}
cat("\n-- cohorts preview --\n")
cohorts <- DBI::dbGetQuery(con, "SELECT * FROM cohorts LIMIT 5")
print(cohorts)
cat("\n-- outcomes counts per ID --\n")
oc <- DBI::dbGetQuery(con, "SELECT outcomeId, COUNT(*) AS n FROM outcomes GROUP BY outcomeId ORDER BY outcomeId")
print(oc)
cat("\n-- nrow summary --\n")
for (t in c("cohorts", "outcomes", "covariates", "covariateRef", "analysisRef")) {
  n <- DBI::dbGetQuery(con, paste0("SELECT COUNT(*) AS n FROM ", t))$n
  cat(sprintf("  %s: %d\n", t, n))
}
DBI::dbDisconnect(con)
