# atlas-auto 시스템 repo

> 시스템 코드 + 연구 공통 참조 데이터. 연구별 파일은 Google Drive 연구 폴더에.

## 대화 시작 시

1. `git log --oneline -5`
2. `cat docs/system_knowledge_base.md` — API 레시피, 체크리스트

## feedernet/ATLAS 작업 규칙

- **API 호출 전 반드시 `docs/system_knowledge_base.md` 참조** — 추측 금지
- 엔드포인트: `data/atlas_reference/atlas_webapi_endpoints_full.csv`
- 기관 ID: `data/site_mapping/site_id_mapping_full.csv` (4종 모두 다름)
- sourceKey: `data/site_mapping/source_key_mapping.csv` (cdmName과 다름!)
- 인증: `automation/` 스크립트에서 login_portal 호출부 확인
- execution 응답 중첩 구조: `content[] → executionList[] → executionStatus`
- estimation spec 수정 시 cohortDefinitions에 코호트 full expression 반드시 포함

## 구조

| 디렉토리 | 역할 |
|----------|------|
| `src/atlas_auto/` | Python 패키지 (pip installable) |
| `data/site_mapping/` | 기관 4종 ID + sourceKey |
| `data/concept_frequency/` | Achilles 23기관×5domain |
| `data/atlas_reference/` | API endpoints, ETRI list, PRESET FA |
| `data/biomarker/` | unit 매핑 |
| `docs/system_knowledge_base.md` | 운영 지식 |
| `cloud_monitor/` | GCP Telegram 모니터링 |

## 현재 연구 폴더

`G:/내 드라이브/KHNMC/appendectomy_study/`
