Sys.setenv(JAVA_HOME = "C:/Users/data1/java/jdk-21.0.10+7")

library(Andromeda)
library(survival)
library(dplyr)

BASE_DIR <- "C:/Users/data1/Desktop/atlas_auto_cmdata"
OUTPUT_DIR <- file.path(BASE_DIR, "pooled_results_timewindow")
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

# v7b와 biomarker 둘 다 분석
STUDIES <- list(
  list(name = "v7b", cmdir = "cmData_v7b",
       outcomes = c(1077, 1078, 1079, 1080, 1090, 1092, 1093, 1094, 1095, 1096, 1097),
       outcome_names = c("1077"="UC", "1078"="CD", "1079"="Asthma", "1080"="AtopicDerm",
                         "1090"="RA", "1092"="CDI", "1093"="PD", "1094"="BilCalc",
                         "1095"="AMI", "1096"="T2DM", "1097"="CRC")),
  list(name = "biomarker", cmdir = "cmData_biomarker",
       outcomes = c(1098, 1099, 1100, 1101, 1102, 1103, 1104, 1105,
                    1108, 1109, 1112, 1116, 1119),
       outcome_names = c("1098"="WBC", "1099"="Neutro", "1100"="Lympho",
                         "1101"="Eosino", "1102"="Mono", "1103"="Baso",
                         "1104"="CRP", "1105"="ESR", "1108"="GlucDM",
                         "1109"="GlucPreDM", "1112"="TG", "1116"="ALT",
                         "1119"="Albumin"))
)

COMPARISONS <- list(
  list(target = 1072, comparator = 1074, name = "vs_Chol"),
  list(target = 1072, comparator = 1076, name = "vs_GenPop"),
  list(target = 1072, comparator = 1121, name = "vs_Hernia")
)

TIME_WINDOWS <- list(
  list(name = "1_30d",     start = 1,   end = 30),
  list(name = "31_90d",    start = 31,  end = 90),
  list(name = "91_365d",   start = 91,  end = 365),
  list(name = "366_1095d", start = 366, end = 1095),
  list(name = "1096_3650d",start = 1096,end = 3650),
  list(name = "1_3650d",   start = 1,   end = 3650)  # 전체 (기존과 동일)
)

# --- 데이터 로딩 함수 ---
loadSiteData <- function(cmdata_dir, site, targetId, compId) {
  cm_dir <- file.path(cmdata_dir, site, sprintf("CmData_l1_t%d_c%d", targetId, compId))
  if (!dir.exists(cm_dir)) return(NULL)

  sqlite_files <- list.files(cm_dir, pattern = "\\.sqlite$", full.names = TRUE)
  if (length(sqlite_files) == 0) return(NULL)

  conn <- DBI::dbConnect(RSQLite::SQLite(), sqlite_files[1])
  cohorts <- DBI::dbReadTable(conn, "cohorts")
  outcomes <- DBI::dbReadTable(conn, "outcomes")
  covariates <- DBI::dbReadTable(conn, "covariates")
  DBI::dbDisconnect(conn)

  list(cohorts = cohorts, outcomes = outcomes, covariates = covariates)
}

# --- PS matching 함수 (Cyclops) ---
fitPsAndMatch <- function(allCohorts, allCovariates, sites) {
  # 간소화된 Cyclops PS (공변량 + site)
  # sparse matrix 구성
  covMatrix <- Matrix::sparseMatrix(
    i = match(allCovariates$rowId, allCohorts$rowId),
    j = as.integer(as.factor(allCovariates$covariateId)),
    x = allCovariates$covariateValue,
    dims = c(nrow(allCohorts), length(unique(allCovariates$covariateId)))
  )

  # site dummy 추가
  siteDummy <- model.matrix(~ as.factor(allCohorts$site) - 1)
  X <- cbind(as.matrix(covMatrix), siteDummy[, -1])
  y <- allCohorts$treatment

  # Cyclops
  cyclopsData <- Cyclops::createCyclopsData(y ~ X, modelType = "lr")
  prior <- Cyclops::createPrior("laplace", useCrossValidation = TRUE)
  fit <- Cyclops::fitCyclopsModel(cyclopsData, prior = prior)

  ps <- predict(fit)
  allCohorts$ps <- ps
  allCohorts$logitPs <- log(ps / (1 - ps + 1e-10))

  # 1:2 matching
  caliper <- 0.2 * sd(allCohorts$logitPs)
  treated <- allCohorts[allCohorts$treatment == 1, ]
  control <- allCohorts[allCohorts$treatment == 0, ]

  matchedT <- c()
  matchedC <- c()
  controlAvail <- control

  for (i in seq_len(nrow(treated))) {
    if (nrow(controlAvail) == 0) break
    diffs <- abs(controlAvail$logitPs - treated$logitPs[i])
    within <- which(diffs <= caliper)
    if (length(within) == 0) next
    nMatch <- min(2, length(within))
    nearest <- within[order(diffs[within])][1:nMatch]
    matchedT <- c(matchedT, treated$rowId[i])
    matchedC <- c(matchedC, controlAvail$rowId[nearest])
    controlAvail <- controlAvail[-nearest, ]
  }

  allCohorts[allCohorts$rowId %in% c(matchedT, matchedC), ]
}

# --- 시간 구간별 Cox 함수 ---
runCoxForWindow <- function(matched, allOutcomes, oid, windowStart, windowEnd) {
  # 해당 구간 내 첫 이벤트만
  oc <- allOutcomes[allOutcomes$outcomeId == oid &
                    allOutcomes$daysToEvent >= windowStart &
                    allOutcomes$daysToEvent <= windowEnd, ]

  if (nrow(oc) > 0) {
    firstEvent <- aggregate(daysToEvent ~ rowId, data = oc, FUN = min)
    names(firstEvent) <- c("rowId", "timeToEvent")
  } else {
    firstEvent <- data.frame(rowId = integer(0), timeToEvent = numeric(0))
  }

  df <- merge(matched[, c("rowId", "treatment", "daysToObsEnd", "site")],
              firstEvent, by = "rowId", all.x = TRUE)

  # follow-up: 구간 끝 또는 관찰 끝 중 작은 값
  df$maxFollow <- pmin(df$daysToObsEnd, windowEnd)
  df <- df[df$maxFollow >= windowStart, ]  # 이 구간까지 생존한 환자만

  df$event <- 0
  hasEvent <- !is.na(df$timeToEvent) & df$timeToEvent <= df$maxFollow
  df$event[hasEvent] <- 1

  # 시간: 구간 시작부터의 상대 시간
  df$time <- df$maxFollow - windowStart + 1
  df$time[hasEvent] <- df$timeToEvent[hasEvent] - windowStart + 1
  df$time <- pmax(df$time, 0.5)

  nEvents <- sum(df$event)
  if (nEvents < 3) return(NULL)

  tryCatch({
    nSites <- length(unique(df$site))
    if (nSites > 1) {
      df$site <- as.factor(df$site)
      fit <- coxph(Surv(time, event) ~ treatment + site, data = df)
    } else {
      fit <- coxph(Surv(time, event) ~ treatment, data = df)
    }

    hr <- exp(coef(fit)["treatment"])
    ci <- exp(confint(fit)["treatment", ])
    p <- summary(fit)$coefficients["treatment", "Pr(>|z|)"]

    data.frame(hr = round(hr, 4), ci_lower = round(ci[1], 4),
               ci_upper = round(ci[2], 4), p_value = round(p, 6),
               n_events = nEvents,
               n_target = sum(df$treatment == 1),
               n_comparator = sum(df$treatment == 0))
  }, error = function(e) NULL)
}

# === Main ===
all_results <- data.frame()

for (study in STUDIES) {
  cat(sprintf("\n\n########## %s ##########\n", study$name))
  cmdata_base <- file.path(BASE_DIR, study$cmdir)
  SITES <- sort(list.dirs(cmdata_base, recursive = FALSE, full.names = FALSE))

  for (comp in COMPARISONS) {
    cat(sprintf("\n=== %s %s ===\n", study$name, comp$name))

    # 데이터 풀링
    allCohorts <- data.frame()
    allOutcomes <- data.frame()
    allCovariates <- data.frame()
    offset <- 0

    for (site in SITES) {
      d <- loadSiteData(cmdata_base, site, comp$target, comp$comparator)
      if (is.null(d)) next

      d$cohorts$rowId <- as.integer(d$cohorts$rowId) + offset
      d$outcomes$rowId <- as.integer(d$outcomes$rowId) + offset
      d$covariates$rowId <- as.integer(d$covariates$rowId) + offset
      d$cohorts$site <- site

      allCohorts <- rbind(allCohorts, d$cohorts)
      allOutcomes <- rbind(allOutcomes, d$outcomes)
      allCovariates <- rbind(allCovariates, d$covariates)
      offset <- offset + 10000000
    }

    if (nrow(allCohorts) == 0) next

    nT <- sum(allCohorts$treatment == 1)
    nC <- sum(allCohorts$treatment == 0)
    cat(sprintf("  Pooled: T=%d, C=%d from %d sites\n", nT, nC, length(unique(allCohorts$site))))

    # PS matching
    cat("  PS matching...\n")
    matched <- tryCatch(
      fitPsAndMatch(allCohorts, allCovariates, SITES),
      error = function(e) { cat(sprintf("  PS failed: %s\n", e$message)); NULL }
    )
    if (is.null(matched)) next

    cat(sprintf("  Matched: T=%d, C=%d\n", sum(matched$treatment==1), sum(matched$treatment==0)))

    # 시간 구간별 Cox
    for (tw in TIME_WINDOWS) {
      cat(sprintf("\n  --- %s (day %d-%d) ---\n", tw$name, tw$start, tw$end))

      for (oid in study$outcomes) {
        oname <- study$outcome_names[as.character(oid)]
        result <- runCoxForWindow(matched, allOutcomes, oid, tw$start, tw$end)

        if (!is.null(result)) {
          sig <- ifelse(result$p_value < 0.05, "*", "")
          cat(sprintf("  %-15s HR=%.3f (%.3f-%.3f) p=%.4f%s ev=%d\n",
                      oname, result$hr, result$ci_lower, result$ci_upper,
                      result$p_value, sig, result$n_events))

          row <- data.frame(
            study = study$name, comparison = comp$name,
            time_window = tw$name, window_start = tw$start, window_end = tw$end,
            outcome_id = oid, outcome_name = oname,
            result, stringsAsFactors = FALSE
          )
          all_results <- rbind(all_results, row)
        }
      }
    }
  }
}

# 저장
out_path <- file.path(OUTPUT_DIR, "timewindow_hr_results.csv")
write.csv(all_results, out_path, row.names = FALSE)
cat(sprintf("\n\nSaved: %s (%d results)\n", out_path, nrow(all_results)))
