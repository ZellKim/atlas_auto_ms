# L5 Audit Checklist — validator 자동 sweep 6-item

> 출처: memory `feedback_paper_audit_pass.md` (2026-05-06 v8 submission pre-check 사고 후 의무화)
> 적발 사례: v8 회람 직전 4개 critical internal inconsistency 발견
> 적용: paper_draft / supplement / cover letter 통합 산출물 작성·통합 시 자동 적용

## Why this exists

Assembly mode (CSV → markdown → docx 변환)에 갇혀서 audit mode (skeptical fact-checking)로 전환 못 한 사례:
1. 본문 sample size 13,225/7,151 vs eTable 4·8 13,223/7,148 (같은 사람이 같은 세션에서 양쪽 작성하고 cross-check 안 함)
2. σ-grid 본문 "core retained sig in both up to σ=0.30" vs supplement table "vs Hernia σ=0.30: 0 sig" — 모순 못 봄
3. T2D "concordance" 표현인데 실제 방향 반대 (glucose protective + T2D elevated) — directional logic 점검 실패
4. eFigure 6, 7 본문 인용하는데 supplement에 caption 없음 — `grep` 1줄이면 잡혔을 일

Root cause: v(N-1)에서 inherited content를 의심 없이 가져감. "이전 버전에 있었으니 OK"는 No-Guessing 위반.

## Checklist (6-item, ALL must pass before deliverable 보고)

### 1. Numerical cross-check (본문 ↔ supplement source)

- 모든 sample size, matched pairs, event count, HR, σ threshold 본문 → source file (CSV / script output) 확인
- 검증 query 예시:
  ```bash
  grep -E "13,225|13,223|N=|n=|HR|cHR" paper_draft.md
  # 각 숫자 → study_input.json 또는 results.json 직접 lookup
  ```
- **action**: 본문 모든 숫자가 `results JSON`에 존재 — 없으면 `[NUMBER?]` 마커 + reject.

### 2. Cross-reference scan

- 본문이 `Table N` / `eTable N` / `Figure N` / `eFigure N` 인용하는 모든 곳 검출
- 각 인용에 대응 caption/file 존재 확인
- 검증 query:
  ```bash
  grep -E "eTable [0-9]+|eFigure [0-9]+|Table [0-9]+|Figure [0-9]+" paper_draft.md
  grep -E "^### eTable|^### eFigure" supplement.md
  # 두 결과 set 비교
  ```
- **action**: 인용은 있는데 caption 없음 → reject. caption은 있는데 인용 없음 → warning.

### 3. Directional logic check

- "concordance / discordance / parallel / converge / consistent with / opposite to" 등장 시 실제 effect direction 양쪽 확인
- HR<1 vs HR>1, protective vs harmful 직접 비교 후 단어 선택
- 검증 query:
  ```bash
  grep -E "concordan|discordan|parallel|converg|consistent with|in line with|opposite" paper_draft.md
  ```
- **action**: 각 매치 line 옆에 results JSON의 effect direction 표시 — 단어와 방향 mismatch면 reject.

### 4. Format constraint hard-check (target journal)

저널 format rules (jama_no_format_rules.md / sr_format_rules.md) hard-check:
- JAMA NO: title ≤100 char, Key Points 75-100w, Abstract ≤350w, main ≤3,000w, tables+figures=5, refs 50-75
- SR: title ≤200 char, Abstract ≤200w unstructured, main ~4,500w, refs ≤60
- **하드 한계는 옵션 아님** — 위반 시 reject.
- word count 자동 측정 후 보고 (각 섹션별).

### 5. Internal consistency sweep (3-way 일치)

- Cohort 정의: eMethods ↔ Table caption ↔ 본문 Methods
- Outcome 정의: eMethods ↔ eTable header ↔ Discussion 해석
- Sample size: 본문 Results ↔ Table 1 ↔ Table 2/3 ↔ eTable
- Period: study/data_source ↔ Methods ↔ Results
- **action**: 3-way 어디라도 mismatch → reject + 어느 두 source인지 명시.

### 6. Inherited content audit

- v(N-1)에서 가져온 문장은 새 데이터/새 framing과 logical consistency 재검증
- "이전 버전에 있었으니 OK"는 No-Guessing 위반
- 새 results JSON과 옛 본문 inherit 부분 — refpack 인용 / 효과 방향 / N — 변화 부분 자동 추출
- **action**: previous version vs current 본문 diff에서 numerical / directional claim 변경 부분 highlight.

## Validation report 출력 format

```markdown
# validation_report.md

## Run metadata
- timestamp: ...
- input: paper_draft_v{N}.md + supplement_v{N}.md + study_input.json + results.json + refpack.json
- journal: jama_network_open | scientific_reports

## Item 1 — Numerical cross-check
- [ ] PASS / FAIL
- Mismatches: ...

## Item 2 — Cross-reference scan
- [ ] PASS / FAIL
- Orphan citations: ...
- Orphan captions: ...

... (3, 4, 5, 6)

## Summary
- Overall: PASS / FAIL
- Hard rejects: [list]
- Warnings: [list]
- Action items for paper-writer / voice-rewriter / paper-orchestrator
```

## 적용 트리거

`paper_draft_v*.md`, `supplementary_v*.md`, `cover_letter_v*.md` 등 submission-related 산출물 작성·통합 시 자동 적용 (validator agent 호출).

## 검증 완료 보고 format

```
audit pass 완료:
- [x] Numerical cross-check
- [x] Cross-reference scan
- [x] Directional logic check
- [x] Format constraint hard-check (JAMA NO ≤3,000w main: actual 2,957w)
- [x] Internal consistency sweep
- [x] Inherited content audit
```

## 관련

- `feedback_no_guessing.md` — 외부 사실 검증 (API/ID/상태)
- `feedback_verify_result_file_source.md` — 결과 파일 출처 cross-check
- 본 checklist는 두 규칙의 **internal consistency 확장판** ("내부 문서 사이의 numerical/logical claim 일치")
