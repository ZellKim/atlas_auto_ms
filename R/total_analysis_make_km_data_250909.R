rm(list = ls())

library(data.table)
library(stringr)
library(survminer)
library(survival)
library(ggplot2)

################################################################################
# 1. 경로 및 폴더 구조 정의
################################################################################

cohort_id <- "cohortId" # v2120
# cohort_id <- "cohortDefinitionId" # v276

# (1) 경로 세팅

base_path <- "C:/Users/adam/Desktop/차재명/250909"

# base_path <- r"(C:\Users\adam\Desktop\차재명\새 폴더)"
to_r_path <- function(path) gsub("\\\\", "/", path)
project_path <- to_r_path(base_path)
data_path <- file.path(project_path, "data")
result_path <- file.path(project_path, "result2")
setwd(result_path)

################################################################################
# 2. 연구 폴더 순회 (study별로 반복)
################################################################################

study_folders <- list.dirs(data_path, recursive = FALSE, full.names = TRUE)

for (study_folder in study_folders) {   # ① study 루프 시작
  
  study_name <- basename(study_folder)
  cat("\n\n====================================\n")
  cat("▶ Study:", study_name, "\n")
  
  # (2) 각 study 폴더 내 병원별 폴더 리스트
  hospital_folders <- list.dirs(study_folder, recursive = FALSE, full.names = TRUE)
  if (length(hospital_folders) == 0) {
    cat("   → 병원 폴더 없음, skip\n")
    next
  }
  
  # (3) 병원별로 StratPop 파일이 있는 병원만 필터링
  hospital_with_stratpop <- Filter(function(hf) {
    sp_path <- file.path(hf, "script/extras/result/cmOutput/")
    length(list.files(sp_path, pattern = "StratPop_l1_s2", full.names = TRUE)) > 0
  }, hospital_folders)
  
  if (length(hospital_with_stratpop) == 0) {
    cat("   → StratPop 없는 병원만 있음, skip\n")
    next
  }
  hospital_folders <- hospital_with_stratpop
  cat("   → StratPop 있는 병원 수:", length(hospital_folders), "\n")
  
  # (5) 첫 병원의 CohortCounts.csv 읽기
  first_cohort_counts_path <- file.path(hospital_folders[1], "script/extras/result/CohortCounts.csv")
  if (!file.exists(first_cohort_counts_path)) {
    cat("   → CohortCounts.csv 없음, skip\n")
    next
  }
  CohortCounts <- fread(first_cohort_counts_path)
  try(CohortCounts[, cohortId := as.character(cohortId)], silent = TRUE)
  
  # (6) 병원별 StratPop 파일 수집
  stratpop_files_all <- unlist(lapply(hospital_folders, function(hf) {
    cmOutput_path <- file.path(hf, "script/extras/result/cmOutput/")
    list.files(cmOutput_path, pattern = "StratPop_l1_s1", full.names = TRUE)
  }))
  
  if (length(stratpop_files_all) == 0) {
    cat("   → StratPop 파일 없음, skip\n")
    next
  }
  
  # (7) StratPop 파일명에서 정보 추출
  get_stratpop_info <- function(x) {
    fname <- basename(x)
    target_num  <- str_match(fname, "t(\\d+)_c")[,2]
    comparator_num <- str_match(fname, "_c(\\d+)_s")[,2]
    study_num   <- str_match(fname, "_s(\\d+)_o")[,2]
    outcome_num <- str_match(fname, "_o(\\d+)\\.")[,2]
    data.table(target_num, comparator_num, outcome_num, study_num)
  }
  stratpop_info <- rbindlist(lapply(stratpop_files_all, get_stratpop_info))
  unique_studies <- unique(stratpop_info)
  cat("   → 조합 수:", nrow(unique_studies), "\n")
  
  # (8) Cohort/outcome 이름 매핑
  t_nums <- unique(stratpop_info$target_num)
  c_nums <- unique(stratpop_info$comparator_num)
  o_nums <- unique(stratpop_info$outcome_num)
  t_table <- data.table(cohort_num = t_nums)
  c_table <- data.table(cohort_num = c_nums)
  o_table <- data.table(outcome_num = o_nums)
  try(t_table <- CohortCounts[t_table, on = .(cohortDefinitionId = cohort_num)], silent = TRUE)
  try(t_table <- CohortCounts[t_table, on = .(cohortId = cohort_num)], silent = TRUE)
  try(c_table <- CohortCounts[c_table, on = .(cohortDefinitionId = cohort_num)], silent = TRUE)
  try(c_table <- CohortCounts[c_table, on = .(cohortId = cohort_num)], silent = TRUE)
  try(o_table <- CohortCounts[o_table, on = .(cohortDefinitionId = outcome_num)], silent = TRUE)
  try(o_table <- CohortCounts[o_table, on = .(cohortId = outcome_num)], silent = TRUE)
  
  ################################################################################
  # 3. 조합별 분석
  ################################################################################
  
  for (study_idx in seq_len(nrow(unique_studies))) {   # ② 조합 루프 시작

    this_target     <- unique_studies$target_num[study_idx]
    this_comparator <- unique_studies$comparator_num[study_idx]
    this_outcome    <- unique_studies$outcome_num[study_idx]
    this_study      <- unique_studies$study_num[study_idx]
    
    t_name <- t_table[get(cohort_id) == this_target, cohortName][1]
    c_name <- c_table[get(cohort_id) == this_comparator, cohortName][1]
    o_name <- o_table[get(cohort_id) == this_outcome, cohortName][1]
    
    cat("\n   ▶▶ 조합 루프:", study_idx, "/", nrow(unique_studies), "\n")
    cat("      Target:", t_name, " Comparator:", c_name, " Outcome:", o_name, "\n")
    
    # (1) 병원별 해당 조합 StratPop 파일 통합
    temp <- rbindlist(
      lapply(hospital_folders, function(hf) {
        stratpop_dir <- file.path(hf, "script/extras/result/cmOutput/")
        pattern <- paste0("t", this_target, "_c", this_comparator, "_s", this_study, "_o", this_outcome, "\\.rds$")
        file1 <- list.files(stratpop_dir, pattern = pattern, full.names = TRUE)
        if (length(file1) == 0) return(NULL)
        agg1 <- as.data.table(readRDS(file1[1]))
        agg1[, hospital := basename(hf)]
        return(agg1)
      }),
      fill = TRUE
    )
    
    if (is.null(temp) || nrow(temp) == 0) {
      cat("      → temp 데이터 없음, skip\n")
      next
    }
    
    temp
    
    # (2) treatment labeling
    temp[, treatment := as.character(treatment)]
    temp[treatment == "1", treatment := "target"]
    temp[treatment == "0", treatment := "comparator"]
  
    # outcometable <- dcast(temp, hospital ~ treatment,  fun.aggregate = length)
    
    outcometable <- dcast(temp, hospital ~ treatment + outcomeCount, value.var = "outcomeCount", fun.aggregate = length)
    
    required_cols <- c("target_0","target_1","comparator_0", "comparator_1")
    for (col in required_cols) {
      if (!(col %in% colnames(outcometable))) outcometable[[col]] <- 0
    }
    setcolorder(outcometable, c("hospital", required_cols))
    
    print(outcometable)
    
    # (3) outcome 없는 병원 제외
    outcometable <- outcometable[, .(hospital, target_1, comparator_1)]
    colnames(outcometable) <- c("hospital", "target_outcomes", "comparator_outcomes")
    zero_hospital <- outcometable[target_outcomes == 0 & comparator_outcomes == 0, hospital]
    temp <- temp[!(hospital %in% zero_hospital)]
    
    print(zero_hospital)
    
    if (nrow(temp) == 0) {
      cat("      → outcome 없는 병원만 존재, skip\n")
      next
    }
    
    ################################################################################
    # 4. 생존분석 (데이터 저장)
    ################################################################################
    cox_data <- temp
    cox_data[, survtime_day := survivalTime]
    cox_data[, treatment := factor(treatment, levels = c("target","comparator"))]
    
    out_csv <- paste0("s2_km_",t_name,"_",c_name,"_",o_name,".csv")
    fwrite(cox_data, out_csv)
    cat("      → CSV 저장 완료:", out_csv, "\n")
    
  }  # --- ② 조합 루프 끝
}    # --- ① study 루프 끝
