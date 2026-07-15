# deliberate skill

> 범용 코딩 작업을 "질문 먼저 → 계획 합의(다중검증) → 증거 남기며 실행"으로 진행.
> gajae-code의 `deep-interview → ralplan → ultragoal` 3-루프를 Claude Code 범용 코딩 skill로 흡수.
> Opus·무과금·약관 안전 — gjc 도구 없이 그 워크플로우만 이식.

## 왜 이 skill인가

gjc(`gajae-code`)의 매력은 도구가 아니라 **워크플로우 로직**(요구 확정 → 계획 자기비판 → 증거 기반 실행)이다.
그 로직은 프롬프트라서 Claude Code 위에서 Opus로 재현 가능. gjc를 Opus로 쓰려면 종량제 API가 필요하지만,
이 skill은 구독으로 도는 Claude Code에서 같은 규율을 **비용 0**으로 준다.

| gjc 스킬 | 원 역할 | 이 skill의 phase |
|---|---|---|
| `deep-interview` | Socratic 질문으로 요구 확정, ambiguity ≤ threshold까지 gate | **Phase 1 — Clarify** |
| `ralplan` | Planner 초안 → Architect/Critic fan-out 합의 → approval gate | **Phase 2 — Plan Consensus (다중검증)** |
| `ultragoal` | 내구 goal 원장, completion gate에 verification+evidence 강제 | **Phase 3 — Execute + Evidence** |

**연구 설계용 자매 skill**: `skills/study-kickoff/` (같은 3-루프의 임상연구 버전).

## 언제 쓰나 (규모에 맞춰 scale)

gjc처럼 작업 규모로 경로를 나눈다:

- **Trivial** (오타·1줄 수정·명확한 소작업): 3-phase 생략, 바로 실행. deliberate 불필요.
- **Standard** (기능 추가·버그 수정·리팩터): Phase 1 짧게 + Phase 2 경량(단일 critic) + Phase 3.
- **Substantial** (아키텍처 변경·다중 파일·마이그레이션·모호한 요구): full 3-phase + Phase 2 **다중검증 Workflow**.

작은 일에 무거운 합의를 강제하지 말 것. 반대로 되돌리기 어렵거나 모호한 일은 반드시 gate를 통과시킬 것.

## 진입점

```
/deliberate <작업 설명>
/deliberate --heavy <작업>     # 다중검증 강제
/deliberate --light <작업>     # 단일 critic
```
→ `.claude/agents/deliberate-orchestrator.md` agent가 디스패치.

## Root rules (전 phase 공통)

1. **승인 전 mutation 금지** — Phase 2 승인 전엔 소스 수정·커밋·실행 금지. 계획은 `pending approval`.
2. **근거 있는 주장만** — 계획·리뷰의 사실은 실제 읽은 파일/실행 결과에 근거. 미확인은 `[UNVERIFIED]` 표기.
3. **증거가 곧 완료** — Phase 3에서 "됐다"는 verification 산출물(테스트·실행·diff)로만 선언. 통과 안 한 걸 완료라 하지 말 것.

## Phase 1 — Clarify (deep-interview 이식)

**목적**: 모호한 요구를 코드 건드리기 전에 확정. 빗나간 구현 방지.

**4개 ambiguity 차원**:

| 차원 | 확정할 것 |
|---|---|
| **Goal** | 무엇을·왜. 성공 시 관측 가능한 변화 |
| **Scope/Constraints** | 대상 파일·모듈, 건드리면 안 되는 것, 기술/버전 제약, 하위호환 |
| **Acceptance** | 완료 판정 기준 (테스트·동작·성능 목표) |
| **Context** | 기존 코드·컨벤션·유사 구현, 의존성 |

**규칙** (gjc 계승):
- **한 번에 한 질문** (`AskUserQuestion`), 답변으로 ambiguity 갱신. 모순/범위확장이면 ambiguity 상승.
- 4 차원이 "실행 가능할 만큼" 명확해지면 gate 통과. trivial이면 즉시 통과.
- **vague 반려**: "성능 개선해줘"처럼 앵커(파일·함수·수치·재현) 없는 요청은 앵커를 요구.

**산출**: `spec` (요구 요약 — 간단한 작업은 2~3줄, 큰 작업은 구조화). scratchpad 또는 작업 브랜치에 기록.

## Phase 2 — Plan Consensus (ralplan 이식, **다중검증**)

**목적**: 계획을 실행에 넣기 전 **독립 렌즈 여러 개가 동시에 공격**해 결함을 잡는다.

### 2a. PLAN-DR (Planner)
orchestrator가 spec으로 계획 + **PLAN-DR** 작성:
- 원칙 (principles)
- 결정 동인 (decision drivers — 왜 이 접근/구조/라이브러리)
- **≥2개 접근**과 tradeoff (예: 리팩터 대 재작성, 라이브러리 A 대 B)
- 영향 파일·함수 목록, 롤백 방법

### 2b. 다중 렌즈 fan-out (Workflow)
`tools/plan_consensus_workflow.js`를 `Workflow`로 실행. 4개 렌즈 **병렬** 리뷰:

| 렌즈 | 점검 |
|---|---|
| **architecture** | 구조 적합성, 결합도, 확장성, 기존 패턴 정합, 과설계/부족 |
| **correctness** | 엣지케이스, 실패모드, race/null/경계, 숨은 가정 |
| **test-verification** | 어떻게 검증하나, 테스트 가능한가, 회귀 위험, 검증 계획 존재 |
| **security-ops** | 입력검증, 권한, 시크릿, 되돌리기·배포 리스크 |

각 렌즈 verdict (gjc 계승): **CLEAR** / **WATCH** / **BLOCK** + 근거 + 수정 제안.
(`--light` 모드면 단일 critic 1회로 축소.)

### 2c. Join gate + iterate
- 어떤 렌즈든 **BLOCK** → 계획 수정 → 2a부터 재실행 (**최대 5**).
- 전 렌즈 CLEAR/WATCH → **reconciliation**: WATCH 항목·가정을 사용자에게 확인.
- 최종 승인 3-way: **Approve → Phase 3** / **Refine 더** / **여기서 중단**.

**산출**: 승인된 `plan.md` (계획 + PLAN-DR + 렌즈 verdict 이력).

## Phase 3 — Execute + Evidence (ultragoal 이식)

**목적**: 승인 계획대로 구현하며 **각 단계의 검증 증거를 남긴다**.

**실행 루프**:
1. 계획을 story 단위로 실행 (한 번에 하나).
2. 각 story 완료 시 **completion gate**:
   - 대상 검증 (테스트 실행 / 실제 동작 구동 / diff 확인) — `verify` skill 있으면 활용
   - 변경 파일 + 검증 증거 기록
   - 리뷰 (correctness 재점검) — 필요 시 `code-review` skill
3. **증거 원장** (append-only, 작업 브랜치의 `.deliberate_ledger.jsonl` 또는 scratchpad):
   ```json
   {"ts":"<ISO>","story":"add auth guard","status":"verified","changed":["src/auth.ts"],"evidence":"test: 12 pass; manual: 401 on no-token","note":"..."}
   ```
   - `status`: `verified` (검증 통과) / `unverified` / `blocked`
   - **gate**: `unverified`·미검증 story 남으면 "완료" 선언 금지. 실제 검증 후 재기록.
4. **blocker 분류**: resolvable(직접 처리) vs human-blocked(credential·외부 승인·의사결정)만 pause.

**산출**: 구현 + 검증 증거 원장. 커밋/푸시/PR은 사용자 지시 시에만.

## 규모별 요약

| 규모 | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| Trivial | skip | skip | 바로 실행 + 간단 검증 |
| Standard | 짧게 | 단일 critic | 실행 + gate |
| Substantial | full | **다중검증 Workflow** | 실행 + gate + 원장 |

## 폴더 구조

```
skills/deliberate/
├── SKILL.md (this)
└── tools/
    └── plan_consensus_workflow.js   ← Phase 2b 다중 렌즈 Workflow
```

## 기존 skill과의 관계

- `verify` skill — Phase 3 검증에 활용 (동작 구동으로 완료 증명)
- `code-review` skill — Phase 3 리뷰 렌즈에 활용
- `study-kickoff` skill — 임상연구 설계용 자매 skill (같은 3-루프)
- Claude Code 기본 Plan mode — 이 skill은 그 위에 자기비판+증거 gate를 더한 것

## 관련 자산
- gjc 원 스킬: `Yeachan-Heo/gajae-code` `packages/coding-agent/src/defaults/gjc/skills/{deep-interview,ralplan,ultragoal}/SKILL.md`
- gjc role agents: `.../src/prompts/agents/{architect,critic,planner,executor}.md`
