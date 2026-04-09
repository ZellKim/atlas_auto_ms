# ============================================================
# R 의존성 패키지 설치
# ============================================================
# Pooled analysis에 필요한 R 패키지를 설치합니다.
# 최초 1회만 실행하면 됩니다.
#
# 사용법:
#   source("R/install_dependencies.R")
# ============================================================

install.packages("remotes")

# CRAN 패키지
install.packages(c(
  "meta",           # DerSimonian-Laird 메타분석
  "readr",          # CSV 파일 읽기
  "ParallelLogger", # 병렬 실행 & 로깅
  "SqlRender"       # camelCase ↔ snake_case 변환
))

# OHDSI 패키지 (GitHub)
remotes::install_github("OHDSI/EvidenceSynthesis")      # Bayesian 메타분석
remotes::install_github("OHDSI/EmpiricalCalibration")    # 경험적 보정
remotes::install_github("OHDSI/DatabaseConnector")       # ZIP 유틸리티

# (선택) Evidence Explorer Shiny 뷰어용
# remotes::install_github("ohdsi-studies/evidnet")

message("설치 완료!")
