# atlas-auto 프로젝트 컨텍스트

## 대화 시작 시 자동 실행

1. `git log --oneline -5` — 최근 커밋 확인
2. `cat PROGRESS.md` — 현재 상태 & TODO (간결한 스냅샷)
3. 필요 시 feedernet API로 estimation 실행 상태 실시간 조회

## 문서 구조

| 문서 | 역할 |
|------|------|
| `PROGRESS.md` | 현재 상태 + TODO (자주 갱신) |
| `docs/system_knowledge_base.md` | **중앙 지식 저장소** — API, 기관 매핑, 방법론, 이슈 해결, 환경, 실행 기록, 파이프라인, 체크리스트 |
| `docs/concept_selection_guide.md` | Concept ID 선정 가이드 |
| `docs/paper_draft.md` | 논문 본문 |
| `docs/paper_ijs_checklist.md` | IJS 투고 체크리스트 + 논문 구조 |

### API 사용 원칙

- **API 호출 전 반드시 `system_knowledge_base.md §1` 엔드포인트 치트시트를 참조**
- 엔드포인트를 기억에 의존하지 말 것 (하이픈 유무, 단수/복수 혼용)
- 기관 ID는 `site_id_mapping_full.csv` 참조 (group_id ≠ site_id ≠ orgId ≠ cdmId)

### 문서 운영 원칙

- **새 발견 / 변동사항 / 이슈 해결** → `docs/system_knowledge_base.md`에 기록
- **진행 상태 업데이트** → `PROGRESS.md`에 기록
- **논문 관련** → `docs/paper_draft.md` 또는 `docs/paper_ijs_checklist.md`
- 문서 간 중복 금지 — 한 가지 정보는 한 곳에만 존재해야 함

## 프로젝트 개요

OHDSI ATLAS / feedernet 다기관 임상연구 자동화 툴킷.
- **repo**: https://github.com/ZellKim/atlas_auto_ms
- **Python 패키지**: `src/atlas_auto/` (client, builder, cohort_designer, protocol, runner, cli)
- **R 분석**: `R/pooled_analysis/` (IPD Cyclops PS + Cox)
- **Cloud 모니터링**: `cloud_monitor/` (GCP Cloud Function → Telegram)
- **레거시**: `automation/` (gitignore, credentials 포함)

## feedernet 접속 정보

- 포탈: https://www.feedernet.com
- 인증: `automation/` 스크립트에서 확인
- 프로젝트 ID: 2908 (충수절제술 연구)
- KHNMC(본원): group_id=7, site_id=203

## 현재 진행중인 연구

| Analysis ID | 이름 | Research Package |
|-------------|------|------------------|
| 10957 | v7b_noStop | E01_E04_clinical_ms_v7b_maxCohort50k_noStop |
| 10961 | biomarker_v1 | B01_B23_biomarker_ms_v1 |

## 주의사항

- `config.yaml`, `automation/` 내 credentials는 절대 커밋하지 말 것
- feedernet API: `project`(단수) vs `projects`(복수) 혼용 주의
- GCP Scheduler 완료 후: `gcloud scheduler jobs pause feedernet-monitor-trigger --location=us-east1`
