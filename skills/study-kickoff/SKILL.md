# study-kickoff skill

> 신규/활성 연구의 **설계 단계**를 "질문 먼저 → 설계 합의(다중검증) → 증거 원장"으로 구조화.
> gajae-code의 `deep-interview → ralplan → ultragoal` 3-루프를 임상연구 도메인으로 이식.
> 코드가 아니라 **연구 설계 산출물**(cohort/estimation/SAP 스펙)을 만든다. 추측 금지 = 원장으로 강제.

## 왜 이 skill인가 (gjc 대조 seed)

gajae-code(`gjc`)의 3-스킬 루프를 **도구 도입 없이** 우리 Claude Code 자산 위에서 재현한 것.
같은 연구 task를 gjc(A)와 이 skill(B)에 던져 맞대결(bake-off)하기 위한 B 쪽 구현.

| gjc 스킬 | 원 역할 | 이 skill의 대응 phase |
|---|---|---|
| `deep-interview` | Socratic 질문으로 요구 확정, ambiguity ≤ threshold까지 gate | **Phase 1 — Interview** |
| `ralplan` | Planner 초안 → Architect/Critic fan-out 합의 → approval gate | **Phase 2 — Design Consensus (다중검증)** |
| `ultragoal` | goals.json + ledger.jsonl 내구 원장, completion gate에 evidence 강제 | **Phase 3 — Evidence Ledger** |

## Root rule (프로젝트 No-Guessing 규칙 상속)

`CLAUDE.md` 최우선 규칙 그대로. 이 skill의 모든 phase에서:

1. **사실 진술은 검증된 값만** — 설계에 들어가는 site 수, concept_id, event 수, biomarker cutoff은 `data/` 실제 파일/live API 조회 후에만 기재. 미확인 값은 `[UNVERIFIED: 출처?]` 마커.
2. **기존 자산 먼저** — cohort/biomarker/site 매핑은 `data/site_mapping/`, `data/measurement/`, `data/concept_frequency/` 우선 참조. 신규 조회는 그 다음.
3. **원장이 곧 증거** — Phase 3에서 각 설계 결정·산출물은 `ledger.jsonl`에 출처 파일/API와 함께 append. "아마/곧/대략" 금지.

## 적용 범위 (신규 + 활성 연구)

이 skill은 두 모드로 동작한다. 진입 시 `studies/{study}/docs/study_design_spec.json` 존재 여부로 자동 분기:

- **신규 연구** (spec 없음): Phase 1 full interview부터 시작 → 설계를 처음부터 확정.
- **활성 연구** (spec 있음, 예: `allergic_diseases`): Phase 1을 **gap-interview**로 축소(비어있거나 `[UNVERIFIED]`인 필드만 질문) → 기존 설계를 Phase 2 다중검증에 태워 약점 재점검 → Phase 3 원장에 검증 결과 append.

활성 연구 재적용 시 기존 `study_design_spec.json`·`ledger.jsonl`은 **덮어쓰지 않고** append/버전업(`_vN`). 기존 결정 이력 보존.

## 진입점

사용자 trigger:
```
/study-kickoff --study allergic_diseases            # 활성 연구 재점검
/study-kickoff --study diabetes_ckd --new           # 신규 연구
```
→ `.claude/agents/study-kickoff-orchestrator.md` agent가 워크플로우 디스패치.

## Phase 1 — Interview (deep-interview 이식)

**목적**: 설계 파라미터를 코호트 생성/실행 전에 못 박아 재작업 차단.
(위반 전례: appendectomy 22→15 site를 뒤늦게 확정 → 전 site 재실행)

**4개 ambiguity 차원** (gjc의 Goal/Constraints/Criteria/Context를 임상 설계로 매핑):

| 차원 | 이 연구에서 확정할 것 |
|---|---|
| **Population** | target/comparator cohort, inclusion/exclusion, index event, 대상 site 집합 |
| **Exposure/Comparator** | active comparator 선정 + rationale, operationalization(concept_id list) |
| **Outcome** | primary/secondary 정의, endpoint_type, follow-up window, negative controls |
| **Analysis/Constraints** | matching, PS model, calibration, sensitivity/subgroup, power 제약 |

**규칙** (gjc deep-interview 계승):
- **한 번에 한 질문** — `AskUserQuestion` 1문항씩, 답변으로 ambiguity 갱신.
- 답변이 모순/범위확장이면 ambiguity **상승** 가능 — 다시 질문.
- 4개 차원 모두 "확정" 되기 전엔 Phase 2로 못 넘어감 (gate).
- 확정 사실은 즉시 `prompts/10_interview_dimensions.md` 체크리스트에 매핑.

**산출**: `studies/{study}/docs/study_design_spec.json` (draft, `contracts/study_design_spec.schema.json` 준수).
→ 이 spec의 `study` 블록은 **paper-writing L1 계약의 `study` 블록과 동일 구조** → 나중에 논문까지 무손실 연결.

**활성 연구 gap 모드**: 기존 spec 로드 → 비거나 `[UNVERIFIED]`인 필드만 질문.

## Phase 2 — Design Consensus (ralplan 이식, **다중검증**)

**목적**: 설계안을 실행에 넣기 전, **독립 렌즈 여러 개가 동시에 공격**해서 함정을 잡는다.

### 2a. DR summary (Planner)
orchestrator가 Phase 1 spec으로 **DESIGN-DR** 요약 작성 (`prompts/20_design_dr.md`):
- 설계 원칙 (principles)
- 결정 동인 (decision drivers — 왜 이 comparator/outcome/matching인가)
- **≥2개 대안**과 tradeoff (예: active comparator 후보 2안, PS 대 IPTW)

### 2b. 다중 렌즈 fan-out (Workflow)
`tools/design_consensus_workflow.js`를 `Workflow`로 실행. 4개 렌즈가 **병렬**로 spec+DR을 리뷰, 각자 verdict 반환:

| 렌즈 | 점검 대상 | 참조 자산 |
|---|---|---|
| **causal-methodology** | confounding, comparator 타당성, immortal time, selection bias, index 정의 | (도메인 지식) |
| **feedernet-execution** | cohort 정의 operationalizable?, **estimation spec의 cohortDefinitions full expression 누락**, sourceKey/site ID 4종, 실행 함정 | `docs/system_knowledge_base.md`, `data/atlas_reference/`, `data/site_mapping/` |
| **data-availability** | 대상 site에 concept 존재?, event 수/power 충분?, biomarker/unit 커버리지 | `data/concept_frequency/`, `data/measurement/`, `data/biomarker/` |
| **statistical** | PS model, NC outcome 구성, calibration(Schuemie), sensitivity/subgroup 타당성 | (도메인 지식) |

각 렌즈 verdict (gjc architect/critic 계승): **CLEAR** / **WATCH** / **BLOCK** + 근거 + 수정 제안.

### 2c. Join gate + iterate
- 어떤 렌즈든 **BLOCK** → orchestrator가 spec 수정 → 2a부터 재실행 (**최대 5 iteration**).
- 전 렌즈 CLEAR/WATCH → **reconciliation**: `AskUserQuestion`으로 WATCH 항목·가정·기존맥락 충돌을 사용자에게 확인.
- 사용자 최종 승인 3-way (gjc 계승): **Refine 더** / **Approve → Phase 3** / **여기서 중단(pending)**.

**실행 경계** (ralplan 계승): 승인 전엔 cohort 생성·feedernet 실행 **금지**. spec은 `pending approval` 상태 유지.
**vague 자동 반려**: "power 높이자" 같은 앵커 없는 요청 반려 — concept_id/site/수치/파일 앵커 요구.

**산출**: `studies/{study}/docs/study_design_plan.md` (승인된 설계 + DR + 렌즈 verdict 이력).

## Phase 3 — Evidence Ledger (ultragoal 이식)

**목적**: 승인된 설계를 실행하며 **모든 산출물·검증을 내구 원장에 기록** → No-Guessing 규칙을 파일로 강제.

**아티팩트** (gjc goals.json/ledger.jsonl 이식):
- `studies/{study}/docs/study_design_spec.json` — 확정 설계 (single source of truth)
- `studies/{study}/docs/kickoff_ledger.jsonl` — 실행 증거 스트림 (append-only)

**원장 엔트리** (append-only, 각 설계 결정/산출물마다 1줄):
```json
{"ts":"<ISO>","phase":"execution","item":"target_cohort","status":"verified",
 "artifact":"<경로 또는 cohort_id>","source":"<data/ 파일 또는 API endpoint>","note":"..."}
```
- `status`: `verified` (출처 확인) / `unverified` (마커) / `blocked`
- **completion gate** (ultragoal 계승): 설계를 "확정"으로 닫으려면 각 핵심 필드(target/comparator/outcome/NC/site set)가 `verified` 원장 엔트리를 가져야 함. `unverified` 남으면 gate 실패 → 실제 조회 후 재기록.
- **blocker 분류**: resolvable(직접 조회 가능) vs human-blocked(IRB·기관 승인·credential). human-blocked만 pause 허용.

**산출**: 완성된 `study_design_spec.json` + `kickoff_ledger.jsonl`.
→ 이후 cohort 생성/feedernet 실행/R 분석/paper-writing은 **기존 도구 그대로** 사용 (이 skill은 설계까지만).

## 폴더 구조

```
skills/study-kickoff/
├── SKILL.md (this)
├── contracts/
│   └── study_design_spec.schema.json   ← Phase 1 산출 계약 (paper-writing study 블록 상위집합)
├── prompts/
│   ├── 10_interview_dimensions.md      ← Phase 1 4-차원 체크리스트
│   ├── 20_design_dr.md                 ← Phase 2a DESIGN-DR 템플릿
│   └── 30_evidence_ledger.md           ← Phase 3 원장 포맷 + completion gate
└── tools/
    └── design_consensus_workflow.js    ← Phase 2b 다중 렌즈 Workflow 스크립트
```

## 산출물 저장 (스킬 vs 연구 분리 — paper-writing 규약 계승)

- 스킬 도구/prompt/contract: `skills/study-kickoff/` (변경 X, 모든 연구 재사용)
- 연구별 설계 산출: `studies/{study}/docs/` (`study_design_spec.json`, `study_design_plan.md`, `kickoff_ledger.jsonl`)

## paper-writing과의 연결

Phase 1 spec의 `study` 블록 = `skills/paper-writing/contracts/study_input.schema.json`의 `study` 블록.
→ kickoff 완료 후 결과(HR/table1 등)만 `results`에 채우면 `/paper start`로 바로 논문 빌드 가능. 설계→논문 무손실.

## bake-off 비교 기준 (A=gjc vs B=이 skill)

같은 연구 설계 task를 양쪽에 던져 비교:
1. 요구 캐묻기 품질 (Phase 1 / deep-interview)
2. 설계 자기비판의 실질성 (Phase 2 다중검증 / ralplan)
3. 함정 포착 (cohortDefinitions full expression 누락, NC 구성, site 선정, power)
4. 증거/출처 추적 강도 (Phase 3 원장 / ultragoal)

## 관련 자산

- `CLAUDE.md` — No-Guessing / No-Reinventing 최우선 규칙 (이 skill의 root rule 출처)
- `docs/system_knowledge_base.md` — feedernet API 함정 (feedernet-execution 렌즈 참조)
- `data/site_mapping/`, `data/concept_frequency/`, `data/measurement/`, `data/biomarker/` — 검증 자산
- `skills/paper-writing/` — 하류 연결 (설계→논문)
- gjc 원 스킬 출처: `Yeachan-Heo/gajae-code` `packages/coding-agent/src/defaults/gjc/skills/{deep-interview,ralplan,ultragoal}/SKILL.md`
