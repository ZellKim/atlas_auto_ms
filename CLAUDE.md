# atlas-auto 프로젝트 컨텍스트

## 대화 시작 시 자동 실행

매 대화 시작 시 아래 순서로 현재 상태를 파악할 것:

1. `git log --oneline -5` — 최근 커밋 확인
2. `cat PROGRESS.md` — 프로젝트 진행 상황 & TODO 확인
3. 필요 시 feedernet API로 estimation 실행 상태 실시간 조회

## 프로젝트 개요

OHDSI ATLAS / feedernet 다기관 임상연구 자동화 툴킷.
- **repo**: https://github.com/ZellKim/atlas_auto_ms
- **Python 패키지**: `src/atlas_auto/` (client, builder, cohort_designer, protocol, runner, cli)
- **R 분석**: `R/` (pooled analysis — IPD 방식으로 재작성 필요)
- **Cloud 모니터링**: `cloud_monitor/` (GCP Cloud Function, feedernet 상태 → Telegram)
- **레거시 스크립트**: `automation/` (gitignore, 하드코딩 credentials 포함)

## feedernet 접속 정보

- 포탈: https://www.feedernet.com
- 인증: `automation/` 스크립트에서 확인 (email/password)
- 프로젝트 ID: 2908 (충수절제술 연구)
- KHNMC(본원): group_id=7, site_id=203

## 현재 진행중인 연구

| Analysis ID | 이름 | Research Package |
|-------------|------|------------------|
| 10957 | v7b_noStop | E01_E04_clinical_ms_v7b_maxCohort50k_noStop |
| 10961 | biomarker_v1 | B01_B23_biomarker_ms_v1 |
| 10858 | 논문을쓰자 (v6) | E01_E04_clinical_ms_v6_nomatch (이전 버전) |

## GCP 모니터링

- Project: `investment-os-chain`
- Function: `feedernet-monitor` (us-east1)
- Scheduler: `feedernet-monitor-trigger` (매 정시)
- 상태 저장: `gs://investment-os-regiem-state/monitor/feedernet_monitor_state.json`
- 완료 후: `gcloud scheduler jobs pause feedernet-monitor-trigger --location=us-east1`

## 주의사항

- `config.yaml`, `automation/` 내 credentials는 절대 커밋하지 말 것
- feedernet API에서 `project`(단수)와 `projects`(복수) 혼용됨에 주의
- estimation 실행 상태 확인: `/api/v1/project/{pid}/analysis/{aid}/execution` (단수 project)
