# atlas-auto 시스템 컨텍스트

## 대화 시작 시 자동 실행

1. `git log --oneline -5` — 최근 커밋 확인
2. `cat docs/system_knowledge_base.md` — API 레시피, 운영 지식, 체크리스트 확인
3. 연구별 작업 시 해당 연구 폴더의 `CLAUDE.md`와 `PROGRESS.md` 확인

## 저장 구조 (3계층)

| 계층 | 위치 | 내용 |
|------|------|------|
| **시스템** | GitHub (`atlas_auto_ms`) | Python 패키지, 참조 데이터, 지식 베이스 |
| **연구** | Google Drive (`KHNMC/{연구명}/`) | 논문, IRB, 코호트, PROGRESS |
| **결과** | Local Desktop (`{연구명}_cmdata/`) | result.zip, CmData, pooled 결과 |

## 문서 구조

| 문서 | 역할 |
|------|------|
| `docs/system_knowledge_base.md` | **중앙 지식 저장소** — API 레시피, 운영 지식, 체크리스트 |
| `docs/concept_selection_guide.md` | Concept ID 선정 가이드 |
| `data/` | 참조 데이터 (기관 매핑, Achilles, API 엔드포인트) |

### API 사용 원칙

- **API 호출 전 반드시 `system_knowledge_base.md §1-2` 참조** — 추측 금지
- 엔드포인트 전체 목록: `data/atlas_reference/atlas_webapi_endpoints_full.csv`
- 기관 ID: `data/site_mapping/site_id_mapping_full.csv` (group_id ≠ site_id ≠ orgId ≠ cdmId)
- sourceKey: `data/site_mapping/source_key_mapping.csv` (cdmName과 다름!)
- 인증: `automation/` 스크립트에서 login_portal 호출부 확인

### 문서 운영 원칙

- **시스템 지식 (API, 이슈 해결, 레시피)** → `docs/system_knowledge_base.md`
- **연구별 진행상황** → 해당 연구 폴더의 `PROGRESS.md`
- **연구별 논문/IRB** → 해당 연구 폴더의 `docs/`
- 문서 간 중복 금지

## 프로젝트 개요

OHDSI ATLAS / feedernet 다기관 임상연구 자동화 툴킷.
- **repo**: https://github.com/ZellKim/atlas_auto_ms
- **Python 패키지**: `src/atlas_auto/` (client, builder, cohort_designer, protocol, runner, cli)
- **R 분석**: `R/pooled_analysis/` (IPD Cyclops PS + Cox)
- **Cloud 모니터링**: `cloud_monitor/` (GCP Cloud Function → Telegram)

## feedernet 접속 정보

- 포탈: https://www.feedernet.com
- 인증: `automation/` 스크립트에서 확인
- KHNMC(본원): group_id=7, site_id=203

## 주의사항

- `config.yaml`, `automation/` 내 credentials는 절대 커밋하지 말 것
- feedernet API: `project`(단수) vs `projects`(복수) 혼용 주의
- estimation spec 수정 시 cohortDefinitions에 코호트 full expression 반드시 포함
