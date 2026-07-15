# Phase 2a — DESIGN-DR 템플릿 (ralplan Planner 이식)

Phase 1 확정 spec으로 orchestrator가 작성. Phase 2b 다중검증 렌즈에 이 문서 + spec을 넘긴다.
`studies/{study}/docs/design_dr.md`에 저장.

```markdown
# DESIGN-DR — {study_code} {version}

## 1. Principles (설계 원칙)
- (예: active-comparator new-user design으로 confounding by indication 최소화)
- (예: site-stratified 분석으로 기관 이질성 흡수)

## 2. Decision drivers (결정 동인)
| 결정 | 선택 | 왜 |
|---|---|---|
| target/comparator | ... | ... |
| primary outcome | ... | ... |
| matching / PS | ... | ... |
| site set | ... | (concept/event 가용성 근거 — data/ 출처 명시) |

## 3. Alternatives considered (≥2개 대안 + tradeoff)
### 대안 A — {선택안}
- 장점 / 단점 / 리스크
### 대안 B — {기각안}
- 장점 / 단점 / 기각 이유
(예: active comparator 후보 2안, PSM 대 IPTW, 단일 primary 대 co-primary)

## 4. Known risks (사전 인지 리스크)
- (예: comparator cohort event 수 부족 가능 → data-availability 렌즈가 확인)
- (예: NC outcome 목록 미검증 → [UNVERIFIED])
```

**규칙**: DR의 모든 수치·site·concept 근거는 실제 `data/` 파일/API에서. 미확인은 `[UNVERIFIED]`.
반드시 **≥2개 대안**을 명시(하나만 있으면 렌즈가 WATCH/BLOCK 처리).
