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
- Biomarker cutoff, unit — `data/atlas_reference/biomarker_fa_ids.json` + `data/scripts/`(biomarker 관련 스크립트) 참조

**사용자에게 숫자/상태 보고 전 체크리스트**:
1. 이 값의 출처 파일/API를 지금 세션에서 직접 읽었는가?
2. 파일이 이력 로그인지 현재 스냅샷인지 필드 구조 확인했는가?
3. 불확실하면 "확인 후 보고" 하고 실제 조회 — "임박", "곧", "아마", "대략"으로 넘어가지 말 것.

**위반 전례** (이 규칙이 생긴 이유):
- 2026-04-19: 파일명 prefix 확인 안 하고 supplemental 결과를 main으로 착각 → Hernia SMD false alarm
- 2026-04-20: state 파일의 `downloaded` 누적만 보고 "15/22, UUH 임박" 추측 → 실제 UUH는 FAILED 상태, DSMC도 queue에 있던 것 누락

## ⛔ 최우선 규칙 — 기존 자산 먼저 확인 (No Reinventing)

**뭔가 할 때 (스크립트, 데이터, 코드, 분석) 새로 만들기 전에 폴더 내에 이미 존재하는지부터 확인.**

적용 대상:
- **새 스크립트 작성 전**: `Glob`/`Grep`로 `data/scripts/`, `automation/`, `studies/{연구}/`, `R/lib/` 검색. 비슷한 이름·기능 있으면 그것부터 검토.
- **API 호출 전**: 직접 endpoint 추측 X. `data/atlas_reference/atlas_webapi_endpoints.csv` + **`src/atlas_auto/client.py`(캐노니컬 정본, git 추적)** 메서드 + 기존 호출 사례 grep. (`automation/feedernet_client.py`는 gitignored 사본이며 divergence 가능 — 정본은 `src/`.)
- **분석 데이터 수집 전**: `data/measurement/`, `data/concept_frequency/`, `studies/{연구}/docs/`, `C:\Users\data1\Desktop\atlas_auto_cmdata\` 먼저 확인.
- **모니터링/상태 조회 전**: `v4_phase_e_monitor.py` (estimation), monitor state 파일, cloud_monitor 등 캐노니컬 도구 사용. 직접 API call 작성 X.
- **Credential 작성 전**: `automation/credentials.py` 사용 (env → GCP Secret → local file fallback). 하드코딩 X.
- **Cohort/biomarker 매핑 전**: `data/site_mapping/` 우선. `site_concept_matrix.csv`/`stability_summary.csv`는 스냅샷별로 버전됨 → 최신은 `studies/measurement_phenotype_methods/<snapshot>/`, 아카이브는 `data/measurement/archive/2026-04-16_to_18_derived/` 참조.

**⛔ 신규 연구는 기존 `studies/*/scripts/v1_*.py` 복제 금지.** R의
`R/lib/ipd_pooled.R` + 60줄 driver 규칙과 동일하게 Python도
**`examples/study_driver_template.py`를 복사해서 시작**한다.
`atlas_auto.StudyRun`이 build→deploy→inspect→trigger→capture→monitor→snapshot
순서를 강제하고 operation journal·uncertain-create 정지·readback 게이트를
소유한다 (`docs/system_knowledge_base.md` §7.4). 착수 전
`python -c "import atlas_auto; print(atlas_auto.__all__)"`로 이미 강제되는 계약을
확인할 것 — 자체 poll 루프·자체 payload·자체 `isValid` 검사 재작성 금지.
재사용 가능한 계약을 새로 발견하면 `docs/knowledge_promotion_protocol.md` 절차로
`src/atlas_auto/`에 승격한다.

**검색 순서** (어떤 task든):
1. `Glob` — 파일명 패턴 (`*monitor*.py`, `*deploy*char*.py`, `build_table*`)
2. `Grep` — 키워드 (`API endpoint`, `class FedernetClient`, 함수명)
3. 발견된 파일 `Read` 후 사용·확장. 처음부터 새로 작성 X.
4. 정말 없으면 그때 신규 작성 (그리고 PROGRESS.md에 산출물 위치 기록).

**위반 전례** (이 규칙이 생긴 이유):
- 2026-04-30: estimation live status 조회 — `v4_phase_e_monitor.py` 표준 도구 있는데 직접 `dashboard/project/...` URL 추측 → 404 → grep으로 정답 찾고 → 직접 Counter 작성 → cdmName 위치 잘못 → 다시 raw inspect → 5-10분 낭비. 정답: `python data/scripts/v4_phase_e_monitor.py [--pid 5126]` 한 줄.
- 2026-04-29: Δ analysis 위해 char data 새로 수집하려다 → 실은 `data/measurement/characterization/char_preset_all.csv`에 47K rows 이미 존재.
- 2026-08-15: fracture_treatment `scripts/*.py` 64개 중 `client.wait_for_cohort_generation` 호출 0개, 자체 폴링 루프 17개, `isValid` 손수 타이핑 18개 파일. 공유 함수에 가드가 없어서 아무도 안 썼고, 가드 없는 그 함수를 신규 연구가 부르면 AUMC 실패(COMPLETE + isValid=false)를 그대로 재현한다. → `generation_safety` 신설 + client 수정으로 해소.

### ⛔ 작업 착수 전 프로토콜 확인 (문서 = 코드와 동급 자산)

**아래 트리거에 해당하면 코드·문서를 쓰기 전에 해당 프로토콜을 먼저 `Read`한다.**
"이미 있는지 검색"이 코드에만 적용된다고 착각하지 말 것 — 문서 작성에도 적용된다.

| 트리거 (이런 요청·상황이면) | 먼저 읽을 문서 |
|---|---|
| 타당성검토 결과를 **의뢰자/임상의에게 회신**, "의뢰자용", "보고서 써줘", GO/REVISE/STOP 판정 | `docs/feasibility_report_for_requester_protocol.md` |
| 논문·공개문서에 **기관 실명 vs 마스킹** 판단, per-site 결함 귀속 | `docs/site_disclosure_masking_protocol.md` |
| **새 연구 착수·집필·투고 전** 선점 확인, novelty 주장 | `docs/prior_art_novelty_gate_protocol.md` |
| 새 주제 → 코호트 feasibility → estimation 파이프라인 | `docs/new_study_topic_to_estimation_protocol.md` |
| study KB에서 **연구 중립적 WebAPI/CDM 사실**을 확립·재발견, 같은 함정 2회 | `docs/knowledge_promotion_protocol.md` |
| feedernet project/analysis **버전 올리기** | `docs/feedernet_project_analysis_versioning_guideline.md` |
| Concept ID 선정 | `docs/concept_selection_guide.md` |
| Characterization / Feature Analysis 생성·재개·다기관 배포 | `docs/characterization_client_workflow.md` |
| 원고 버전·릴리스 관리 | `docs/manuscript_versioning_policy.md` |
| estimation 산출물 구성 | `docs/estimation_output_template.md` |

- **md → docx 변환은 `python data/scripts/md2docx.py in.md out.docx`** (repo house style: Calibri 11pt / 맑은 고딕, 여백 2.5cm, 표 `Light Grid Accent 1`). 변환기 새로 짜지 말 것.
- 새 프로토콜을 만들면 **이 표에 트리거와 함께 등재**한다. 등재 안 하면 다음 세션이 못 찾는다.

**위반 전례**:
- 2026-08-03: Semaglutide 타당성검토 의뢰자 회신문을 프로토콜 없이 작성 → 판정 체계 누락(GO/REVISE/STOP), 기관 한글명 6곳 추측으로 오기(KDH를 경기도의료원으로), "데이터 없음"과 "처방 기록 미확인"을 구분 안 함 → 재작성. 이후 프로토콜로 정립.

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

`studies/` 아래 다수 연구 폴더가 병존한다. **활성 연구·진행 상태의 정본은 각 `studies/{연구}/PROGRESS.md`** — 단일 연구명을 여기 하드코딩하지 말고 각 PROGRESS.md의 mtime·내용으로 현재 상태 확인.
(최근 활성 예: `measurement_phenotype_methods`, `gi_high_impact_pilots`, `uterine_fibroids`, `appendectomy`, `allergic_diseases` 등)

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
│   ├── atlas_reference/             ← API endpoints, ETRI list, biomarker_fa_ids.json (unit 매핑)
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

## ⛔ Credentials 처리 (2026-04-29 정립)

**모든 새 스크립트는 `automation/credentials.py` 사용**:

```python
import sys
sys.path.insert(0, r"G:\내 드라이브\0.claude_workspace\data_analysis\atlas_auto_with_claude\automation")
from credentials import get_feedernet_credentials, get_telegram_credentials

# feedernet
client.login_portal(*get_feedernet_credentials())

# Telegram
token, chat_id = get_telegram_credentials()
```

**Resolution order** (`automation/credentials.py`):
1. 환경변수: `FEEDERNET_EMAIL` / `FEEDERNET_PASSWORD` (또는 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`)
2. GCP Secret Manager (`investment-os-chain` 프로젝트)
3. 로컬 파일: `~/.atlas_auto_credentials.json` (gitignored)
4. 실패 → 명확한 에러 (어디 설정해야 하는지 알려줌)

**금지**:
- `client.login_portal("user@example.com", "<password>")` 같은 하드코딩
- `EMAIL = "..."` / `PASSWORD = "..."` 변수 직접 정의
- `.env` 파일을 git에 커밋

**기존 스크립트 refactor 도구**: `automation/_refactor_creds.py` (one-time 사용, 신규 스크립트가 같은 패턴 따르면 재사용 X)
