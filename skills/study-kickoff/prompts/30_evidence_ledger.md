# Phase 3 — Evidence Ledger 포맷 + completion gate (ultragoal 이식)

승인된 설계를 실행하며 각 핵심 필드의 출처를 내구 원장에 append. No-Guessing 규칙을 파일로 강제.
`studies/{study}/docs/kickoff_ledger.jsonl` (append-only, 덮어쓰기 금지).

## 엔트리 포맷 (1 결정/산출물 = 1 줄)
```json
{"ts":"2026-07-15T09:00:00Z","phase":"execution","item":"target_cohort","status":"verified","artifact":"cohort_id:1234 또는 경로","source":"data/site_mapping/source_key_mapping.csv","note":"..."}
```

| 필드 | 값 |
|---|---|
| `phase` | interview \| consensus \| execution |
| `item` | target_cohort / comparator_cohort / primary_outcome / negative_controls / site_set / estimation_spec ... |
| `status` | `verified` (출처 확인됨) \| `unverified` (마커) \| `blocked` |
| `artifact` | 산출물 경로 또는 cohort/estimation ID |
| `source` | 검증 근거 `data/` 파일 또는 API endpoint (verified면 필수) |

## Completion gate (ultragoal 계승)
설계를 "확정(approved+closed)"으로 닫으려면 아래 **핵심 item 전부**가 `verified` 원장 엔트리를 가져야 함:
- target_cohort, comparator_cohort(들), primary_outcome(들), negative_controls, site_set, analysis_plan

- `unverified` 남아있으면 gate **실패** → 실제 조회 후 원장 재기록. "곧/대략"으로 닫지 말 것.
- gate 통과 시 `study_design_spec.json`의 `spec_meta.approval_status = "approved"`로 마감.

## Blocker 분류
- **resolvable**: 직접 조회/실행 가능 (concept 매핑, cohort 생성, achilles 조회) → 즉시 처리 후 verified.
- **human-blocked**: 사용자만 해결 (IRB 승인, 기관 데이터 접근, credential) → 이 경우만 pause 허용, 원장에 `blocked` + 사유 기록.

## 마감 후
`study_design_spec.json`(approved) + `kickoff_ledger.jsonl` 완성.
이후 cohort 생성/feedernet 실행/R pooled/paper-writing은 **기존 도구** 사용 — 이 skill은 설계까지만.
