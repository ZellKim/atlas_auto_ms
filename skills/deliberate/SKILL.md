# deliberate skill

> **어떤 작업이든** "질문 먼저 → 계획 합의(다중검증) → 증거 남기며 실행"으로 진행하는 범용 규율.
> gajae-code의 `deep-interview → ralplan → ultragoal` 3-루프를 도메인 무관 Claude Code skill로 흡수.
> 코딩·연구·글쓰기·기획·분석·의사결정·운영 전부 적용. Opus·무과금·약관 안전 — gjc 도구 없이 워크플로우만 이식.

## 왜 이 skill인가

gjc의 매력은 도구가 아니라 **일 처리 규율**이다: 모호하면 먼저 묻고, 실행 전에 계획을 스스로 공격하고,
"됐다"를 증거로만 선언하는 것. 이건 코딩에 국한되지 않는 보편 규율이라 어떤 작업에도 적용된다.
gjc를 Opus로 쓰려면 종량제 API가 필요하지만, 이 skill은 구독 Claude Code에서 같은 규율을 **비용 0**으로 준다.

| gjc 스킬 | 원 역할 | 이 skill의 phase |
|---|---|---|
| `deep-interview` | 모호한 요구를 Socratic 질문으로 확정, ambiguity gate | **Phase 1 — Clarify** |
| `ralplan` | 계획 초안 → 독립 리뷰어 fan-out 합의 → approval gate | **Phase 2 — Consensus (다중검증)** |
| `ultragoal` | 내구 원장, completion gate에 verification+evidence 강제 | **Phase 3 — Execute + Evidence** |

**자매 skill**: `skills/study-kickoff/` — 같은 3-루프의 임상연구 설계 특화판.

## 언제 쓰나 (규모에 맞춰 scale)

작업 규모/가역성으로 경로를 나눈다 (작은 일에 무거운 절차 금지):

- **Trivial** (명확·소규모·쉽게 되돌림): 3-phase 생략, 바로 실행 + 간단 확인.
- **Standard** (보통 작업): Phase 1 짧게 + Phase 2 경량(단일 리뷰어) + Phase 3.
- **Substantial** (모호하거나·되돌리기 어렵거나·영향 큰): full 3-phase + Phase 2 **다중검증 Workflow**.

## 진입점

```
/deliberate <작업 설명>
/deliberate --heavy <작업>     # 다중검증 강제
/deliberate --light <작업>     # 단일 리뷰어
```
→ `.claude/agents/deliberate-orchestrator.md` agent가 디스패치. 작업 도메인은 orchestrator가 자동 판별.

## Root rules (전 phase 공통)

1. **되돌리기 어려운 행동은 승인 후** — Phase 2 승인 전엔 비가역·외부영향 행동(파일 덮어쓰기, 발송, 배포, 제출, 삭제) 금지. 계획은 `pending approval`.
2. **근거 있는 주장만** — 계획·리뷰의 사실은 실제 읽은 자료/실행 결과에 근거. 미확인은 `[UNVERIFIED]` 표기. (연구 repo면 `CLAUDE.md` No-Guessing 규칙과 동일.)
3. **증거가 곧 완료** — "됐다"는 검증 산출물(테스트·구동·대조·재현)로만 선언. 통과 안 한 걸 완료라 하지 말 것.

## Phase 1 — Clarify (deep-interview 이식)

**목적**: 모호한 요구를 착수 전에 확정 → 빗나간 결과물 방지.

**4개 ambiguity 차원** (도메인 무관):

| 차원 | 확정할 것 | 코딩 예 | 연구/글쓰기/기획 예 |
|---|---|---|---|
| **Goal** | 무엇을·왜, 성공 시 관측 가능한 변화 | 어떤 기능/버그 | 어떤 질문/주장/결정 |
| **Scope/Constraints** | 대상·범위, 손대면 안 되는 것, 제약 | 대상 파일·기술 | 대상 데이터·기간·형식·금지사항 |
| **Acceptance** | 완료 판정 기준 | 테스트·동작 | 판단 근거·수용 기준·품질 |
| **Context** | 기존 자료·컨벤션·유사 사례 | 기존 코드 | 기존 문서·선행연구·이해관계자 |

**규칙** (gjc 계승):
- **한 번에 한 질문** (`AskUserQuestion`), 답변으로 ambiguity 갱신. 모순/범위확장이면 ambiguity 상승.
- 4 차원이 "착수 가능할 만큼" 명확해지면 gate 통과. trivial이면 즉시 통과.
- **vague 반려**: 앵커(구체 대상·수치·기준·재현) 없는 요청은 앵커를 요구.
- 관련 기존 자료는 `Glob`/`Grep`/`Read`(또는 도메인 조회)로 확인 후 spec 반영 — 추측 X.

**산출**: `spec` (요구 요약 — 작은 작업 2~3줄, 큰 작업 구조화). scratchpad 또는 작업 위치에 기록.

## Phase 2 — Consensus (ralplan 이식, **다중검증**)

**목적**: 계획을 실행에 넣기 전 **독립 렌즈 여러 개가 동시에 공격**해 결함을 잡는다.

### 2a. PLAN-DR (Planner)
orchestrator가 spec으로 계획 + **PLAN-DR** 작성:
- 원칙 (principles)
- 결정 동인 (decision drivers — 왜 이 접근/구조)
- **≥2개 접근**과 tradeoff
- 영향 대상·산출물 목록, 롤백/되돌리기 방법

### 2b. 다중 렌즈 fan-out (Workflow)
`tools/plan_consensus_workflow.js`를 `Workflow`로 실행. **4개 보편 렌즈**가 병렬 리뷰:

| 보편 렌즈 | 점검 | 작업별 초점(orchestrator가 주입) |
|---|---|---|
| **soundness** | 논리·가정·접근의 타당성, 실패 모드 | 코딩: 정확성/엣지케이스 · 연구: 인과·bias · 글쓰기: 논증 타당성 |
| **completeness** | 빠진 것, 놓친 케이스·이해관계자·시나리오 | 코딩: 회귀·미처리 입력 · 연구: 누락 covariate·NC · 글: 반론·근거 공백 |
| **feasibility** | 실행 가능성, 자원·의존성·리스크, 되돌리기 | 코딩: 실행/배포 · 연구: 데이터·power 가용 · 기획: 일정·자원 |
| **alternatives** | 더 단순/나은 접근, tradeoff, 과설계 | 전 도메인 공통 |

각 렌즈 verdict (gjc 계승): **CLEAR** / **WATCH** / **BLOCK** + 근거 + 수정 제안.
orchestrator는 작업 도메인에 맞는 초점을 각 렌즈 프롬프트에 `lens_focus`로 주입. (`--light`면 단일 리뷰어 1회.)

### 2c. Join gate + iterate
- 어떤 렌즈든 **BLOCK** → 계획 수정 → 2a부터 재실행 (**최대 5**).
- 전 렌즈 CLEAR/WATCH → **reconciliation**: WATCH 항목·가정을 사용자에게 확인.
- 최종 승인 3-way: **Approve → Phase 3** / **Refine 더** / **여기서 중단**.

**산출**: 승인된 `plan.md` (계획 + PLAN-DR + 렌즈 verdict 이력).

## Phase 3 — Execute + Evidence (ultragoal 이식)

**목적**: 승인 계획대로 실행하며 **각 단계의 검증 증거를 남긴다**.

**실행 루프**:
1. 계획을 step 단위로 실행 (한 번에 하나).
2. 각 step 완료 시 **completion gate** — 도메인에 맞는 검증:
   - 코딩: 테스트/구동/diff (`verify`·`code-review` skill)
   - 연구: 출처 파일·API 대조, 수치 재현
   - 글쓰기: 인용·사실 대조, 기준 충족 확인
   - 결정/운영: 근거 대조, 되돌리기 가능성 확인
3. **증거 원장** (append-only, `.deliberate_ledger.jsonl` 또는 scratchpad):
   ```json
   {"ts":"<ISO>","step":"<설명>","status":"verified","output":["<산출물>"],"evidence":"<검증 근거>","note":""}
   ```
   - `status`: `verified` / `unverified` / `blocked`
   - **gate**: `unverified`·미검증 step 남으면 "완료" 선언 금지 → 실제 검증 후 재기록.
4. **blocker 분류**: resolvable(직접 처리) vs human-blocked(credential·외부승인·의사결정)만 pause.

**산출**: 결과물 + 검증 증거 원장. 발송·커밋·제출 등 외부 행동은 **사용자 지시 시에만**.

## 규모별 요약

| 규모 | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| Trivial | skip | skip | 바로 실행 + 간단 확인 |
| Standard | 짧게 | 단일 리뷰어 | 실행 + gate |
| Substantial | full | **다중검증 Workflow** | 실행 + gate + 원장 |

## 폴더 구조
```
skills/deliberate/
├── SKILL.md (this)
└── tools/
    └── plan_consensus_workflow.js   ← Phase 2b 4 보편 렌즈 Workflow (lens_focus 주입식)
```

## 기존 skill과의 관계
- `verify` / `code-review` — 코딩 작업 Phase 3 검증에 활용
- `study-kickoff` — 임상연구 설계 특화 자매 skill (같은 3-루프)
- `paper-writing` — 논문 작업 시 Phase 3 실행 도구로 연계
- Claude Code 기본 Plan mode — 이 skill은 그 위에 자기비판+증거 gate를 더한 것

## 관련 자산
- gjc 원 스킬: `Yeachan-Heo/gajae-code` `packages/coding-agent/src/defaults/gjc/skills/{deep-interview,ralplan,ultragoal}/SKILL.md`
- gjc role agents: `.../src/prompts/agents/{architect,critic,planner,executor}.md`
