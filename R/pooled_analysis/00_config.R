# =============================================================================
# 00_config.R
# Pooled Analysis + Meta-Analysis 설정
# Appendectomy (1072) vs Cholecystectomy (1074) 비교효과 연구
# =============================================================================

# -- 필요 패키지 ---------------------------------------------------------------
library(CohortMethod)
library(Andromeda)
library(Cyclops)
library(FeatureExtraction)
library(EmpiricalCalibration)
library(EvidenceSynthesis)
library(dplyr)
library(ggplot2)
library(ParallelLogger)
library(readr)

# -- 사이트 설정 ---------------------------------------------------------------
# 각 기관의 result 폴더 경로를 지정하세요
# 구조: result/cmOutput/CmData_l1_t1072_c1074.zip + result/export/*.csv

# cmData 로컬 경로 (구글 드라이브가 아닌 로컬 디스크에 저장)
cmDataBaseDir <- "C:/Users/data1/Desktop/atlas_auto_cmdata"

resultFolders <- list(
  AUMC  = "C:/Users/data1/Desktop/atlas_auto_cmdata/results/AUMC/script/extras/result"
  # GNUCH = ".../GNUCH/script/extras/result",
  # CAUHS = ".../CAUHS/script/extras/result",
  # 사이트 추가 시 result.zip 해제 경로 지정
)

siteNames <- names(resultFolders)

# -- 코호트 ID ----------------------------------------------------------------
targetId     <- 1072  # Appendectomy
comparatorId <- 1074  # Cholecystectomy

# -- Outcome IDs (11개) -------------------------------------------------------
outcomeIds <- c(
  1077,  # Ulcerative colitis
  1078,  # Crohn's disease
  1079,  # Asthma
  1080,  # Atopic dermatitis
  1090,  # Rheumatoid arthritis
  1092,  # C. difficile infection
  1093,  # Parkinson's disease
  1094,  # Biliary calculus
  1095,  # Acute myocardial infarction
  1096,  # Type 2 diabetes mellitus
  1097   # Colorectal cancer
)

outcomeNames <- c(
  "Ulcerative colitis", "Crohn's disease", "Asthma",
  "Atopic dermatitis", "Rheumatoid arthritis",
  "C. difficile infection", "Parkinson's disease",
  "Biliary calculus", "Acute myocardial infarction",
  "Type 2 diabetes mellitus", "Colorectal cancer"
)
names(outcomeNames) <- outcomeIds

# -- Negative Control IDs (55개) ----------------------------------------------
negativeControlIds <- c(
  4088290, 4092879, 436634, 75911, 376707, 378424, 374923, 381581,
  81378, 78619, 260134, 76786, 200775, 73008, 4170770, 4050747,
  40481632, 74855, 441818, 4254542, 374375, 140480, 4344500, 139099,
  444132, 196168, 438329, 443285, 4156115, 4134455, 377572, 136368,
  4215978, 140648, 75354, 192606, 373478, 4169984, 141932, 134461,
  4030042, 140641, 380038, 380094, 77965, 379805, 375552, 4329707,
  81878, 377575, 40568467, 4033858, 133141, 133228
)

# 전체 분석 대상 outcome
allOutcomeIds <- c(outcomeIds, negativeControlIds)

# -- 분석 파라미터 (cmAnalysisList.json과 일치) --------------------------------
riskWindowStart <- 1
riskWindowEnd   <- 3650
minDaysAtRisk   <- 1
removeSubjectsWithPriorOutcome <- TRUE
priorOutcomeLookback <- 99999

# -- CmData 파일명 패턴 -------------------------------------------------------
cmDataFileName <- "CmData_l1_t1072_c1074.zip"

# -- 출력 폴더 ----------------------------------------------------------------
outputFolder <- "C:/Users/data1/Desktop/atlas_auto_cmdata/output"
if (!dir.exists(outputFolder)) dir.create(outputFolder, recursive = TRUE)

# -- 병렬 처리 ----------------------------------------------------------------
maxCores <- max(1, parallel::detectCores() - 1)

message(sprintf("Config loaded: %d sites, %d outcomes, %d negative controls",
                length(siteNames), length(outcomeIds), length(negativeControlIds)))
