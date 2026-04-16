# atlas-auto

OHDSI ATLAS / feedernet 다기관 임상연구 자동화 시스템.

## 대화 시작 시

1. `cat docs/system_knowledge_base.md` — API 레시피, 운영 지식, 체크리스트
2. 활성 연구의 `PROGRESS.md`와 `study_knowledge_base.md` 읽기
3. `git log --oneline -5` — 최근 시스템 변경 확인

## 현재 활성 연구

**studies/appendectomy/** — 충수절제술 다기관 비교효과 연구

## feedernet 핵심 함정 (매번 확인)

- **`project`(단수) vs `projects`(복수)** 혼용 — 실행은 단수, 목록은 복수
- **`cohortdefinition` 하이픈 없음**, `cohort-characterization`은 하이픈 있음
- **sourceKey ≠ cdmName** → `data/site_mapping/source_key_mapping.csv`
- **기관 ID 4종 다름** → `data/site_mapping/site_id_mapping_full.csv`
- **execution 응답 중첩**: `content[] → executionList[] → executionStatus`
- **estimation spec 수정 시 cohortDefinitions에 코호트 full expression 필수** (누락 시 에러 없이 실패)
- **API 추측 금지** — 반드시 `docs/system_knowledge_base.md` 또는 `data/atlas_reference/` 참조
- **인증**: `automation/` 스크립트에서 login_portal 호출부 확인

## 구조

```
이 디렉토리 (Google Drive + git)
├── src/atlas_auto/                  ← Python 패키지 (git push → GitHub)
├── data/                            ← 연구 공통 참조 데이터 (git push)
│   ├── site_mapping/                ← 기관 ID, sourceKey
│   ├── concept_frequency/           ← Achilles 23기관×5domain
│   ├── atlas_reference/             ← API endpoints, ETRI list
│   ├── biomarker/                   ← unit 매핑
│   └── reference/                   ← R 환경, 이슈 히스토리
├── docs/system_knowledge_base.md    ← 시스템 운영 지식 (git push)
├── studies/                         ← 연구별 폴더 (.gitignore, Drive 백업)
│   └── appendectomy/
│       ├── PROGRESS.md
│       ├── study_knowledge_base.md
│       ├── docs/                    ← paper, IRB
│       ├── cohort_definitions/
│       └── R/reference_scripts/
└── (무거운 결과: C:\Users\data1\Desktop\atlas_auto_cmdata\)
```

## 문서 운영 원칙

- **시스템 지식** (API, 이슈, 레시피) → `docs/system_knowledge_base.md`
- **연구별 지식** (설계, 매핑, 이슈) → `studies/{연구}/study_knowledge_base.md`
- **연구별 진행** → `studies/{연구}/PROGRESS.md`
- credentials 절대 커밋 금지
