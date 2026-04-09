# ============================================================
# 실행 스크립트: atlas-auto 결과 pooled analysis
# ============================================================
#
# 전체 워크플로우:
#   1. Python: atlas-auto로 다기관 estimation 실행 & result.zip 다운로드
#   2. R: 이 스크립트로 메타분석 & Shiny 뷰어 실행
#
# 사용법:
#   Rscript R/run_pooled.R ./results
#   또는 RStudio에서 source("R/run_pooled.R")
# ============================================================

source("R/pooled_analysis.R")

# ── 설정 ──
args <- commandArgs(trailingOnly = TRUE)
results_folder <- if (length(args) > 0) args[1] else "./results"

cat(sprintf("결과 폴더: %s\n", normalizePath(results_folder, mustWork = FALSE)))
cat(sprintf("ZIP 파일: %d개\n", length(list.files(results_folder, pattern = "result\\.zip$", ignore.case = TRUE))))

# ── 실행 ──
run_pooled_analysis(
  results_folder = results_folder,
  method = "DL",                    # "BayesianNonNormal" 또는 "DL"
  max_cores = parallel::detectCores(),
  launch_shiny = TRUE,              # Shiny Evidence Explorer 자동 실행
  blind = FALSE                     # TRUE: 결과 블라인딩
)
