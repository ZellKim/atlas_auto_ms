# atlas-auto 시스템 repo

> 이 repo는 **시스템 코드 + 연구 공통 참조 데이터**만 포함. 연구별 문서/코호트/결과는 별도 Google Drive 폴더에 저장.

## 대화 시작 시

1. `git log --oneline -5`
2. `cat docs/system_knowledge_base.md` — API 레시피, 체크리스트

## 구조

| 디렉토리 | 역할 |
|----------|------|
| `src/atlas_auto/` | Python 패키지 (pip installable) |
| `data/site_mapping/` | 기관 4종 ID + sourceKey 매핑 |
| `data/concept_frequency/` | Achilles 23기관×5domain |
| `data/atlas_reference/` | API endpoints, ETRI list, PRESET FA |
| `data/biomarker/` | unit 매핑 |
| `data/reference/` | R 환경, 이슈 히스토리 |
| `docs/system_knowledge_base.md` | 운영 지식 (레시피, 함정, 교훈) |
| `cloud_monitor/` | GCP Telegram 모니터링 |

## 연구별 폴더 (Google Drive)

```
KHNMC/{연구명}/
├── CLAUDE.md          ← 연구 컨텍스트 (이 repo 참조 포함)
├── PROGRESS.md
├── docs/              ← paper, IRB
├── cohort_definitions/
└── R/                 ← 분석 스크립트
```

현재 연구: `G:/내 드라이브/KHNMC/appendectomy_study/`
