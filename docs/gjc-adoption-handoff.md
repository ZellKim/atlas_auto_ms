# gjc 도입 검토 & 워크플로우 흡수 — 핸드오프

> 이 세션(원격/웹 Claude Code)에서 한 작업을 **로컬 Claude Code에서 이어받기** 위한 요약.
> 브랜치: `claude/gajae-code-review-vil2ej` · 세션 날짜: 2026-07-21

---

## 0. TL;DR

- gajae-code(`gjc`, `Yeachan-Heo/gajae-code`)를 신규 연구 설계에 도입할지 검토함.
- **결론**: gjc **도구 자체는 도입 안 함**(Opus를 종량제 없이 쓸 방법이 없고 = 약관/비용 문제).
  대신 gjc의 워크플로우 규율(`deep-interview → ralplan → ultragoal`)을 **Claude Code skill로 흡수**.
- 산출물 skill 2개 (브랜치에 커밋·푸시 완료):
  - `skills/study-kickoff/` — **임상연구 설계** 특화 (dry-run 검증 완료)
  - `skills/deliberate/` — **도메인 무관 범용** (연구·코딩·글쓰기·기획·분석·의사결정)
- 남은 일: **네 로컬에서** `김세희` 등 실제 폴더로 dry-run (원격 컨테이너는 `G:\` 접근 불가).

---

## 1. 왜 gjc 도구는 안 쓰기로 했나

| Opus 얻는 법 | 종량제? | gjc에서 |
|---|---|---|
| Anthropic API key (Console) | **과금 O** | 가능하나 비용 발생 |
| Claude 구독 (Pro/Max) | 과금 X | ⚠️ **1st-party 클라이언트 전용** — 서드파티 도구(gjc)에 넣으면 약관 위반·계정 리스크 |
| 무료 티어(Gemini 등)/로컬 모델 | 과금 X | 가능하나 **모델이 Claude 아님** → 품질↓ |

→ **"Opus + 무과금"의 유일한 합법 조합 = Claude Code 그 자체.** gjc라는 껍데기로는 재현 불가.
→ 그래서 **워크플로우 로직만 skill로 이식**하는 게 정답 (Opus·무과금·약관 안전).

(참고: 이 원격 컨테이너엔 gjc 0.10.2가 설치돼 있지만 **임시**라 세션 끝나면 사라짐. 무료 모델 붙여 별도로 쓰고 싶으면 로컬에 `npm i -g bun && bun install -g gajae-code`.)

---

## 2. 만든 것 — skill 2개

### gjc 3-루프 매핑 (두 skill 공통)
| gjc | 이식된 phase |
|---|---|
| `deep-interview` (Socratic 요구 확정, ambiguity gate) | **Phase 1 — Clarify/Interview** (한 번에 한 질문, vague 반려) |
| `ralplan` (Planner→리뷰어 fan-out 합의, approval gate) | **Phase 2 — Consensus (다중검증 Workflow)** |
| `ultragoal` (내구 원장, completion gate에 evidence 강제) | **Phase 3 — Execute + Evidence** |

### A. `skills/study-kickoff/` — 임상연구 설계 특화
- 신규/활성 연구 모두 지원 (`study_design_spec.json` 존재로 자동 분기).
- Phase 2b 다중검증 4렌즈: **causal-methodology / feedernet-execution / data-availability / statistical**.
  - `data/site_mapping/`, `data/concept_frequency/`, `docs/system_knowledge_base.md` 등 실제 자산에 근거.
- 설계 spec을 `paper-writing`의 `study` 블록 상위집합으로 설계 → **설계→논문 무손실 연결**.
- 파일:
  - `skills/study-kickoff/SKILL.md`
  - `skills/study-kickoff/contracts/study_design_spec.schema.json`
  - `skills/study-kickoff/prompts/{10_interview_dimensions,20_design_dr,30_evidence_ledger}.md`
  - `skills/study-kickoff/tools/design_consensus_workflow.js`
  - `.claude/agents/study-kickoff-orchestrator.md`

### B. `skills/deliberate/` — 도메인 무관 범용
- 어떤 작업이든 적용. 규모별 scale (trivial 생략 / standard 경량 / substantial 다중검증).
- Phase 2b **보편 4렌즈**: **soundness / completeness / feasibility / alternatives**.
  - orchestrator가 도메인 판별 후 각 렌즈에 `lens_focus`(작업별 초점) 주입.
- Root rule: 승인 전 **비가역·외부영향 행동 금지**(덮어쓰기·발송·배포·제출·삭제).
- 파일:
  - `skills/deliberate/SKILL.md`
  - `skills/deliberate/tools/plan_consensus_workflow.js`
  - `.claude/agents/deliberate-orchestrator.md`

### 커밋 (브랜치 `claude/gajae-code-review-vil2ej`)
```
afb3a36 refactor(deliberate): 코딩 전용 → 완전 도메인 무관 범용 skill
d1bb9e6 feat(skill): deliberate — gjc 3-loop 범용 코딩 skill로 흡수
6e392b4 fix(study-kickoff): 렌즈 verdict가 아닌 finding.severity로 집계
af13b80 feat(skill): study-kickoff — gjc 3-loop을 연구 설계로 이식
```

---

## 3. dry-run 검증 이력 (이 세션에서 실제 실행)

`study-kickoff`의 Phase 2b 다중검증을 **allergic_diseases 파일럿 설계**로 돌림
(입력: `R/archive/allergic_ipd_pilot.R`의 실제 설계 — Target 1290 알레르기비염 / Comparator 1287 비알레르기 / Primary ADHD·Tic / NC 54 appendectomy 재사용 / 3 pilot site).

**결과: 4렌즈 전부 BLOCK, gate=ITERATE.** 실제 `data/` 파일에 근거해 잡은 것:
- **causal**: "active-comparator" 표방했지만 비알레르기=unexposed → surveillance/detection bias가 가설 방향으로 유입 (BLOCK)
- **feedernet**: `site_set`이 sourceKey 아닌 cdmName → 실제 sourceKey 제시, cdmpv533은 순천향 4site 공유까지 지적 (BLOCK)
- **data-availability**: `concept_frequency/by_site` 읽어 ADHD event 상한 AUMC 104·CHNUH 45·**SCHCA 13** → 검정력 red flag (BLOCK)
- **statistical**: appendectomy 성인 NC가 소아에 부적합 → calibration 무효화 (BLOCK)

→ 다중검증 게이트가 **실제로 함정을 잡는다**는 게 검증됨(환각 아님, 파일 근거).
→ 부수로 스크립트 집계 버그 1개 발견·수정(`6e392b4`).

---

## 4. 로컬에서 이어받기 — 셋업

### 4-1. 브랜치 가져오기
로컬 저장소(`atlas_auto_ms`)에서:
```bash
git fetch origin claude/gajae-code-review-vil2ej
git checkout claude/gajae-code-review-vil2ej
```
→ `skills/deliberate/`, `skills/study-kickoff/`, `.claude/agents/*-orchestrator.md`가 로컬에 생김.

### 4-2. skill 인식 확인
로컬 Claude Code에서 skill/agent가 로드되는지 확인 (SKILL.md는 `skills/`, agent는 `.claude/agents/`).
`/deliberate`, `/study-kickoff` trigger 또는 orchestrator agent 호출로 작동.

---

## 5. 로컬에서 `김세희` 폴더 dry-run 하기

원격 컨테이너는 `G:\내 드라이브\...\NHIS_work\김세희`에 접근 못 함 → **로컬 Claude Code에서** 실행.

이게 **NHIS 청구데이터 연구**면 `study-kickoff`가 더 특화됨. 절차:

```
/study-kickoff --study <김세희연구코드> --new
```
또는 범용으로:
```
/deliberate <김세희 폴더의 연구/분석 작업 설명>
```

orchestrator가:
1. **Phase 1**: 폴더 문서(`G:\...\김세희\*`)를 읽고 4차원(Goal/Scope/Acceptance/Context) 확정 — 한 번에 한 질문.
2. **Phase 2**: PLAN-DR 작성 → 다중검증 Workflow 4렌즈 병렬 리뷰 → BLOCK 있으면 iterate.
3. **Phase 3**: 승인 후 실행 + 증거 원장.

> ⚠️ **개인정보 주의**: NHIS 청구데이터는 환자 식별정보 포함 가능. 렌즈는 설계/계획만 봐도 되니, 원시 환자데이터가 아니라 **연구계획서·SAP·설계문서**를 대상으로 돌릴 것.

### 렌즈 초점 참고 (deliberate를 청구데이터 연구에 쓸 때 orchestrator가 주입할 lens_focus 예)
- soundness: 인과 설계, confounding, comparator 타당성, 청구코드 정의 타당성
- completeness: 누락 covariate, 민감도/subgroup, negative control, 결측·검열
- feasibility: 청구데이터 변수 가용성, 표본수·event·power, IRB/DUA
- alternatives: 설계 대안(코호트 정의·분석모형), 더 단순한 접근

---

## 6. 남은 선택지 / 다음 단계

- [ ] 로컬에서 `김세희` 폴더로 `study-kickoff` 또는 `deliberate` dry-run.
- [ ] (원하면) gjc를 무료 모델(Gemini)로 로컬 설치해 별도 범용 도구로 사용.
- [ ] (원하면) A(gjc) vs B(이 skill) bake-off — 단 A는 종량제/무료모델 필요, 로컬에서.
- [ ] skill을 main에 병합할지 결정 (현재 브랜치에만 있음).

---

## 관련 자산
- gjc 원 스킬 원문: `Yeachan-Heo/gajae-code` `packages/coding-agent/src/defaults/gjc/skills/{deep-interview,ralplan,ultragoal}/SKILL.md`
- `CLAUDE.md` — No-Guessing / No-Reinventing 규칙 (두 skill의 root rule 출처)
- `skills/paper-writing/` — study-kickoff의 하류 연결 (설계→논문)
