# atlas-auto

OHDSI ATLAS / feedernet 다기관 임상연구 자동화 시스템.

## ⛔ 최우선 규칙 — 추측 금지 (No Guessing)

**이 시스템의 모든 사실 진술은 실제 데이터로 검증된 값만 사용한다. 추측·짐작·"아마도"·"곧" 금지.**

적용 대상 (예외 없음):
- API 필드명, 응답 구조, endpoint, 인증 방식
- 실행 상태, site 진행 상황, queue 순번, COMPLETE/FAILED/WAITING 수 — state 파일만 보고 추측 말고 live API 또는 snapshot(`current_status`+`counts` 필드 있는) 조회
- 분석 결과 수치 (HR, SMD, pair 수, event 수) — 파일 읽고 확인, 기억/이전 대화에서 복사 금지
- 파일 출처 — 여러 sensitivity 공존 시 파일명 prefix + pair 수 cross-check 후 해석
- Concept ID, cohort ID, estimation ID — 직접 조회 또는 매핑 파일 확인
- 기관명, sourceKey, cdmId, groupId — `data/site_mapping/` 참조
- Biomarker cutoff, unit — `data/biomarker/` 참조

**사용자에게 숫자/상태 보고 전 체크리스트**:
1. 이 값의 출처 파일/API를 지금 세션에서 직접 읽었는가?
2. 파일이 이력 로그인지 현재 스냅샷인지 필드 구조 확인했는가?
3. 불확실하면 "확인 후 보고" 하고 실제 조회 — "임박", "곧", "아마", "대략"으로 넘어가지 말 것.

**위반 전례** (이 규칙이 생긴 이유):
- 2026-04-19: 파일명 prefix 확인 안 하고 supplemental 결과를 main으로 착각 → Hernia SMD false alarm
- 2026-04-20: state 파일의 `downloaded` 누적만 보고 "15/22, UUH 임박" 추측 → 실제 UUH는 FAILED 상태, DSMC도 queue에 있던 것 누락

## 대화 시작 시

1. `cat docs/system_knowledge_base.md` — API 레시피, 운영 지식, 체크리스트
2. 활성 연구의 `PROGRESS.md`와 `study_knowledge_base.md` 읽기
3. `git log --oneline -5` — 최근 시스템 변경 확인

## IPD Pooled Analysis (R) — 공통 lib 사용

**신규 연구는 `R/v4_*.R` 복제 금지**. `R/lib/ipd_pooled.R` + study-specific driver (60줄) 패턴.

- Driver 템플릿: `R/lib/driver_template.R`
- API: `run_ipd_pooled(config)` → primary + NC + calibrated HR + E-value + time-window
- 2026-04-24 regression 검증: v4 Chole 30 outcome bit-for-bit 일치
- 상세: `docs/system_knowledge_base.md` §7.2

## 현재 활성 연구

**studies/allergic_diseases/** — 소아 알레르기-틱/ADHD 다기관 연구
(studies/appendectomy/ — 충수절제술 연구, estimation 실행 중)

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
