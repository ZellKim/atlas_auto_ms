# ============================================================
# Pooled Analysis (Meta-Analysis) for Multi-site CES Results
# ============================================================
#
# atlas-auto로 다운로드한 result.zip 파일들을 통합 분석합니다.
#
# 파이프라인:
#   1. result.zip들을 한 폴더에 모음
#   2. synthesizeResults()로 메타분석 실행
#   3. Evidence Explorer Shiny 앱으로 결과 확인
#
# 필요한 R 패키지:
#   install.packages("remotes")
#   remotes::install_github("OHDSI/EvidenceSynthesis")
#   remotes::install_github("OHDSI/EmpiricalCalibration")
#   remotes::install_github("OHDSI/CohortMethod")
#   install.packages(c("meta", "readr", "ParallelLogger", "SqlRender"))
#
# 사용법:
#   source("R/pooled_analysis.R")
#   run_pooled_analysis("./results")
# ============================================================


#' 전체 pooled analysis 파이프라인 실행
#'
#' @param results_folder result.zip 파일들이 있는 폴더
#' @param output_folder  메타분석 결과 저장 폴더 (NULL이면 results_folder 사용)
#' @param method         "BayesianNonNormal" (권장) 또는 "DL" (DerSimonian-Laird)
#' @param max_cores      최대 CPU 코어 수
#' @param launch_shiny   완료 후 Evidence Explorer 자동 실행 여부
#' @param blind          Shiny에서 블라인딩 적용 여부
run_pooled_analysis <- function(results_folder,
                                output_folder = NULL,
                                method = "BayesianNonNormal",
                                max_cores = parallel::detectCores(),
                                launch_shiny = TRUE,
                                blind = FALSE) {

  results_folder <- normalizePath(results_folder)
  if (is.null(output_folder)) output_folder <- results_folder

  message("=" |> rep(60) |> paste(collapse = ""))
  message("atlas-auto Pooled Analysis")
  message("=" |> rep(60) |> paste(collapse = ""))

  # ── Step 1: result.zip 확인 ──
  zip_files <- list.files(results_folder, pattern = "result\\.zip$", ignore.case = TRUE)
  message(sprintf("결과 파일: %d개 발견", length(zip_files)))
  for (f in zip_files) message(sprintf("  %s", f))

  if (length(zip_files) < 2) {
    stop("메타분석에 최소 2개 기관의 결과가 필요합니다.")
  }

  # ── Step 2: zip 파일명 표준화 (Results_*.zip 형식으로) ──
  staging_folder <- file.path(output_folder, "staging")
  dir.create(staging_folder, showWarnings = FALSE, recursive = TRUE)

  for (f in zip_files) {
    src <- file.path(results_folder, f)
    # CDM명 추출 (예: CAUHS_5.3.1_03_241515_result.zip → CAUHS_5.3.1_03)
    db_id <- extract_database_id(f)
    dst <- file.path(staging_folder, sprintf("Results_%s.zip", db_id))
    file.copy(src, dst, overwrite = TRUE)
    message(sprintf("  %s → Results_%s.zip", f, db_id))
  }

  # ── Step 3: 메타분석 실행 ──
  message(sprintf("\n메타분석 실행 (method=%s, cores=%d)...", method, max_cores))
  ma_folder <- file.path(output_folder, "meta_analysis")
  dir.create(ma_folder, showWarnings = FALSE, recursive = TRUE)

  synthesize_results(
    all_dbs_folder = staging_folder,
    ma_export_folder = ma_folder,
    max_cores = max_cores,
    method = method
  )

  message(sprintf("메타분석 완료: %s", ma_folder))

  # ── Step 4: Evidence Explorer 준비 & 실행 ──
  if (launch_shiny) {
    shiny_data <- file.path(output_folder, "shiny_data")
    dir.create(shiny_data, showWarnings = FALSE, recursive = TRUE)

    # 개별 기관 + 메타분석 결과 모두 Shiny용으로 변환
    all_zips <- list.files(staging_folder, pattern = "Results_.*\\.zip", full.names = TRUE)
    ma_zip <- list.files(ma_folder, pattern = "Results_.*\\.zip", full.names = TRUE)
    all_zips <- c(all_zips, ma_zip)

    for (zip_file in all_zips) {
      message(sprintf("  Shiny 데이터 준비: %s", basename(zip_file)))
      tryCatch(
        prepare_for_shiny(zip_file, shiny_data),
        error = function(e) message(sprintf("    경고: %s", e$message))
      )
    }

    message(sprintf("\nEvidence Explorer 실행: %s", shiny_data))
    launch_evidence_explorer(shiny_data, blind = blind)
  }

  invisible(list(
    staging_folder = staging_folder,
    ma_folder = ma_folder,
    method = method,
    n_sites = length(zip_files)
  ))
}


#' result.zip 파일명에서 database ID 추출
#'
#' 패턴: {CDM명}_{exec_id}_result.zip → CDM명
#' 예: CAUHS_5.3.1_03_241515_result.zip → CAUHS_5.3.1_03
extract_database_id <- function(filename) {
  # _result.zip 제거
  name <- sub("_result\\.zip$", "", filename, ignore.case = TRUE)
  # 마지막 _숫자 (exec_id) 제거
  name <- sub("_\\d+$", "", name)
  # 공백/특수문자 정리
  name <- gsub("[^A-Za-z0-9._-]", "_", name)
  return(name)
}


# ============================================================
# Core: Meta-Analysis (synthesizeResults 호환)
# ============================================================
# 원본: evidnet R 패키지의 MetaAnalysis.R
# OHDSI EvidenceSynthesis + meta 패키지 사용
# ============================================================

#' 다기관 결과 메타분석
#'
#' @param all_dbs_folder  Results_*.zip 파일들이 있는 폴더
#' @param ma_export_folder 메타분석 결과 저장 폴더
#' @param max_cores       최대 코어 수
#' @param method          "BayesianNonNormal" 또는 "DL"
synthesize_results <- function(all_dbs_folder,
                               ma_export_folder = all_dbs_folder,
                               max_cores = 1,
                               method = "BayesianNonNormal") {

  if (!requireNamespace("ParallelLogger", quietly = TRUE)) stop("ParallelLogger 패키지 필요")
  if (!requireNamespace("readr", quietly = TRUE)) stop("readr 패키지 필요")
  if (!requireNamespace("SqlRender", quietly = TRUE)) stop("SqlRender 패키지 필요")
  if (!requireNamespace("meta", quietly = TRUE)) stop("meta 패키지 필요")

  all_dbs_folder <- normalizePath(all_dbs_folder)
  dir.create(ma_export_folder, showWarnings = FALSE, recursive = TRUE)

  result_sets <- list.files(all_dbs_folder, pattern = "^Results_.*\\.zip")
  message(sprintf("Found %d result sets for meta-analysis", length(result_sets)))

  if (length(result_sets) < 2) {
    stop("메타분석에 최소 2개의 결과 세트가 필요합니다.")
  }

  # 각 사이트의 결과 로드
  main_results <- lapply(result_sets, load_database_results, all_dbs_folder = all_dbs_folder)
  main_results <- do.call(rbind, main_results)
  main_results <- split(main_results, paste(main_results$targetId, main_results$comparatorId, main_results$analysisId))

  if (method == "BayesianNonNormal") {
    if (!requireNamespace("EvidenceSynthesis", quietly = TRUE)) {
      warning("EvidenceSynthesis 패키지 미설치. DL 방식으로 전환합니다.")
      method <- "DL"
    } else {
      profiles <- lapply(result_sets, load_likelihood_profiles, all_dbs_folder = all_dbs_folder)
      profiles <- do.call(rbind, profiles)
      if (!is.null(profiles) && nrow(profiles) > 0) {
        profiles <- split(profiles, paste(profiles$targetId, profiles$comparatorId, profiles$analysisId))
        groups <- lapply(names(main_results), function(name) {
          list(mainResults = main_results[[name]],
               profiles = if (name %in% names(profiles)) profiles[[name]] else NULL)
        })
      } else {
        message("Likelihood profiles 없음. DL 방식으로 전환.")
        method <- "DL"
        groups <- lapply(names(main_results), function(name) list(mainResults = main_results[[name]]))
      }
    }
  }

  if (method == "DL") {
    groups <- lapply(names(main_results), function(name) list(mainResults = main_results[[name]]))
  }

  rm(main_results)

  # 메타분석 실행
  message("Performing meta-analysis...")
  cluster <- ParallelLogger::makeCluster(min(max_cores, 10))
  results <- ParallelLogger::clusterApply(cluster, groups, compute_group_meta, method)
  ParallelLogger::stopCluster(cluster)

  results <- do.call(rbind, results)
  if ("trueEffectSize" %in% colnames(results)) {
    results$trueEffectSize <- NULL
  }

  # CSV 저장 & ZIP
  temp_folder <- tempfile()
  dir.create(temp_folder, recursive = TRUE)
  on.exit(unlink(temp_folder, recursive = TRUE, force = TRUE))

  colnames(results) <- SqlRender::camelCaseToSnakeCase(colnames(results))
  write.csv(results, file.path(temp_folder, "cohort_method_result.csv"), row.names = FALSE)

  database <- data.frame(
    database_id = "Meta-analysis",
    database_name = "Random effects meta-analysis",
    description = ifelse(method == "BayesianNonNormal",
      "Random effects using non-normal likelihood approximation (Schuemie et al. 2021)",
      "Random effects using DerSimonian-Laird estimator"),
    is_meta_analysis = 1
  )
  write.csv(database, file.path(temp_folder, "database.csv"), row.names = FALSE)

  zip_name <- file.path(ma_export_folder, "Results_MetaAnalysis.zip")
  files <- list.files(temp_folder, pattern = ".*\\.csv$")
  old_wd <- setwd(temp_folder)
  on.exit(setwd(old_wd), add = TRUE)

  if (requireNamespace("DatabaseConnector", quietly = TRUE)) {
    DatabaseConnector::createZipFile(zipFile = zip_name, files = files)
  } else {
    zip(zip_name, files)
  }
  setwd(old_wd)

  message(sprintf("Meta-analysis 완료: %s", zip_name))
}


# ── 내부 함수: 결과 로드 ──

load_database_results <- function(zip_file, all_dbs_folder) {
  message("Loading: ", zip_file)
  temp <- tempfile()
  dir.create(temp)
  on.exit(unlink(temp, recursive = TRUE, force = TRUE))

  suppressWarnings(utils::unzip(
    file.path(all_dbs_folder, zip_file),
    files = c("cohort_method_result.csv", "negative_control_outcome.csv", "positive_control_outcome.csv"),
    exdir = temp, overwrite = TRUE
  ))

  result_file <- file.path(temp, "cohort_method_result.csv")
  if (!file.exists(result_file)) {
    warning(sprintf("No cohort_method_result.csv in %s", zip_file))
    return(NULL)
  }

  results <- readr::read_csv(result_file, col_types = readr::cols(), show_col_types = FALSE)
  colnames(results) <- SqlRender::snakeCaseToCamelCase(colnames(results))

  # Negative controls
  nc_file <- file.path(temp, "negative_control_outcome.csv")
  results$trueEffectSize <- NA
  if (file.exists(nc_file)) {
    ncs <- readr::read_csv(nc_file, col_types = readr::cols(), show_col_types = FALSE)
    colnames(ncs) <- SqlRender::snakeCaseToCamelCase(colnames(ncs))
    results$trueEffectSize[results$outcomeId %in% ncs$outcomeId] <- 1
  }

  # Positive controls
  pc_file <- file.path(temp, "positive_control_outcome.csv")
  if (file.exists(pc_file)) {
    pcs <- readr::read_csv(pc_file, col_types = readr::cols(), show_col_types = FALSE)
    colnames(pcs) <- SqlRender::snakeCaseToCamelCase(colnames(pcs))
    idx <- results$outcomeId %in% pcs$outcomeId
    results$trueEffectSize[idx] <- pcs$effectSize[match(results$outcomeId[idx], pcs$outcomeId)]
  }

  return(results)
}

load_likelihood_profiles <- function(zip_file, all_dbs_folder) {
  temp <- tempfile()
  dir.create(temp)
  on.exit(unlink(temp, recursive = TRUE, force = TRUE))

  suppressWarnings(utils::unzip(
    file.path(all_dbs_folder, zip_file),
    files = "likelihood_profile.csv",
    exdir = temp
  ))

  profile_file <- file.path(temp, "likelihood_profile.csv")
  if (!file.exists(profile_file)) return(NULL)

  profiles <- readr::read_csv(profile_file, col_types = readr::cols(), show_col_types = FALSE)
  colnames(profiles) <- SqlRender::snakeCaseToCamelCase(colnames(profiles))
  return(profiles)
}


# ── 내부 함수: 메타분석 계산 ──

compute_group_meta <- function(group, method) {
  main <- group$mainResults
  if (is.null(main) || nrow(main) == 0) return(NULL)

  outcome_ids <- unique(main$outcomeId)
  results <- lapply(outcome_ids, function(oid) {
    compute_single_meta(oid, group, method)
  })
  group_results <- do.call(rbind, results)

  # Empirical calibration
  group_results <- apply_empirical_calibration(group_results)

  return(group_results)
}

compute_single_meta <- function(outcome_id, group, method) {
  rows <- group$mainResults[group$mainResults$outcomeId == outcome_id, ]
  ma_row <- rows[1, ]
  ma_row$databaseId <- "Meta-analysis"

  ma_row$targetSubjects <- sum_min_cell(rows$targetSubjects)
  ma_row$comparatorSubjects <- sum_min_cell(rows$comparatorSubjects)
  ma_row$targetDays <- sum(rows$targetDays, na.rm = TRUE)
  ma_row$comparatorDays <- sum(rows$comparatorDays, na.rm = TRUE)
  ma_row$targetOutcomes <- sum_min_cell(rows$targetOutcomes)
  ma_row$comparatorOutcomes <- sum_min_cell(rows$comparatorOutcomes)

  if (method == "BayesianNonNormal" && !is.null(group$profiles)) {
    profiles <- group$profiles[group$profiles$outcomeId == outcome_id, ]
    if (nrow(profiles) > 1) {
      profile_data <- strsplit(profiles$profile, ";")
      profile_data <- as.data.frame(t(sapply(profile_data, as.numeric)))
      colnames(profile_data) <- seq(log(0.1), log(10), length.out = 1000)

      estimate <- EvidenceSynthesis::computeBayesianMetaAnalysis(profile_data)
      ma_row$rr <- exp(estimate$mu)
      ma_row$ci95Lb <- exp(estimate$mu95Lb)
      ma_row$ci95Ub <- exp(estimate$mu95Ub)
      ma_row$logRr <- estimate$logRr
      ma_row$seLogRr <- estimate$seLogRr
      ma_row$p <- EmpiricalCalibration::computeTraditionalP(estimate$logRr, estimate$seLogRr)
      ma_row$i2 <- NA
      return(ma_row)
    }
  }

  # DL fallback
  valid <- rows[!is.na(rows$seLogRr), ]
  if (nrow(valid) < 2) {
    ma_row$rr <- NA; ma_row$ci95Lb <- NA; ma_row$ci95Ub <- NA
    ma_row$p <- NA; ma_row$logRr <- NA; ma_row$seLogRr <- NA; ma_row$i2 <- NA
    return(ma_row)
  }

  m <- meta::metagen(TE = valid$logRr, seTE = valid$seLogRr, sm = "RR", method.tau = "DL")
  s <- summary(m)
  rnd <- s$random
  ma_row$rr <- exp(rnd$TE)
  ma_row$ci95Lb <- exp(rnd$lower)
  ma_row$ci95Ub <- exp(rnd$upper)
  ma_row$p <- rnd$p
  ma_row$logRr <- rnd$TE
  ma_row$seLogRr <- rnd$seTE
  ma_row$i2 <- s$I2$TE

  return(ma_row)
}

apply_empirical_calibration <- function(group_results) {
  if (!requireNamespace("EmpiricalCalibration", quietly = TRUE)) {
    group_results$calibratedP <- NA
    group_results$calibratedRr <- NA
    group_results$calibratedCi95Lb <- NA
    group_results$calibratedCi95Ub <- NA
    return(group_results)
  }

  ncs <- group_results[!is.na(group_results$trueEffectSize) & group_results$trueEffectSize == 1, ]
  valid_ncs <- ncs[!is.na(ncs$seLogRr), ]

  if (nrow(valid_ncs) >= 5) {
    null <- EmpiricalCalibration::fitMcmcNull(valid_ncs$logRr, valid_ncs$seLogRr)
    group_results$calibratedP <- EmpiricalCalibration::calibrateP(
      null = null, logRr = group_results$logRr, seLogRr = group_results$seLogRr
    )$p

    model <- EmpiricalCalibration::convertNullToErrorModel(null)
    cal_ci <- EmpiricalCalibration::calibrateConfidenceInterval(
      logRr = group_results$logRr, seLogRr = group_results$seLogRr, model = model
    )
    group_results$calibratedRr <- exp(cal_ci$logRr)
    group_results$calibratedCi95Lb <- exp(cal_ci$logLb95Rr)
    group_results$calibratedCi95Ub <- exp(cal_ci$logUb95Rr)
  } else {
    group_results$calibratedP <- NA
    group_results$calibratedRr <- NA
    group_results$calibratedCi95Lb <- NA
    group_results$calibratedCi95Ub <- NA
  }

  return(group_results)
}

sum_min_cell <- function(counts) {
  total <- sum(abs(counts), na.rm = TRUE)
  if (any(counts < 0, na.rm = TRUE)) total <- -total
  return(total)
}


# ── Evidence Explorer (Shiny) ──

#' 결과 zip을 Shiny 데이터로 변환
prepare_for_shiny <- function(results_zip_file, data_folder) {
  if (requireNamespace("evidnet", quietly = TRUE)) {
    evidnet::prepareForEvidenceExplorer(
      resultsZipFile = results_zip_file,
      dataFolder = data_folder
    )
  } else {
    message("  evidnet 패키지 미설치. Shiny 데이터 준비를 건너뜁니다.")
    message("  설치: remotes::install_github('ohdsi-studies/evidnet')")
  }
}

#' Evidence Explorer Shiny 앱 실행
launch_evidence_explorer <- function(data_folder, blind = FALSE) {
  if (requireNamespace("evidnet", quietly = TRUE)) {
    evidnet::launchEvidenceExplorer(
      dataFolder = data_folder,
      blind = blind,
      launch.browser = TRUE
    )
  } else {
    message("evidnet 패키지 미설치. Shiny 뷰어를 시작할 수 없습니다.")
  }
}
