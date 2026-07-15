# Phase 1 — Interview 4-차원 체크리스트 (deep-interview 이식)

한 번에 한 질문(`AskUserQuestion`). 답변으로 아래 필드를 채우고, 4개 차원 모두 "확정"돼야 Phase 2로 gate.
활성 연구(gap 모드)면 이미 채워진/`[UNVERIFIED]` 아닌 필드는 건너뛰고 빈 곳만 질문.

## 차원 1 — Population
- [ ] target cohort 정의 (질환/시술 + concept 방향)
- [ ] comparator cohort(들)
- [ ] inclusion / exclusion 기준
- [ ] index event & washout / new-user 여부
- [ ] 대상 **site 집합** (source_keys) + 선정 rationale  ← appendectomy 22→15 재작업 방지

## 차원 2 — Exposure/Comparator
- [ ] active comparator 최종안 + **rationale** (왜 이 비교군인가)
- [ ] operationalization (concept_id list) — `data/` 조회 후 기재, 추측 X

## 차원 3 — Outcome
- [ ] primary outcome(s): name / definition / endpoint_type / follow-up window
- [ ] secondary outcome(s)
- [ ] **negative control outcomes** 후보 목록 (calibration용)

## 차원 4 — Analysis/Constraints
- [ ] matching (예: 1:1 NN PSM, caliper 0.2 SD logit)
- [ ] PS model (covariate set / large-scale LASSO)
- [ ] primary model (예: site-stratified Cox)
- [ ] calibration (예: empirical calibration on NC HRs)
- [ ] sensitivity / subgroup
- [ ] power/데이터 제약 (event 수 우려 등)

## ambiguity gate 규칙
- 답변이 모순되거나 범위가 커지면 해당 차원 "미확정"으로 되돌리고 재질문 (ambiguity 상승 허용).
- 확정 사실만 `study_design_spec.json`에 기재. 미확인 수치는 `[UNVERIFIED: 출처?]` 마커.
- 4개 차원 전부 확정 → Phase 2.
