# Prompt 30 — Validate

> 호출자: `validator` (voice-rewriter 완료 후)
> 목적: audit_checklist 6-item 자동 sweep → PASS / FAIL + action items
> 출력 위치: `studies/{study}/docs/draft/{version}/validation_report.md`

## Root rules

1. **자동 PASS 금지** — 하나라도 hard reject 항목 있으면 FAIL
2. **추측 금지** — 모든 finding은 file content + grep 결과로 증명
3. **출처 명시** — 매 finding마다 file:line citation

## Inputs

- `studies/{study}/docs/draft/{version}/{6 sections}.md` (voice-rewriter 출력)
- `studies/{study}/docs/supplement_v{version}.md` (있으면)
- `studies/{study}/docs/study_input_{version}.json`
- `studies/{study}/docs/results_{version}.json`
- `studies/{study}/docs/refpack_{version}.json`
- `skills/paper-writing/tools/audit_checklist.md`
- `skills/paper-writing/style/{jama_no|sr}_format_rules.md`
- (있으면) `studies/{study}/docs/paper_draft_v{N-1}.md` — inherited audit

## 6-item 점검 (audit_checklist.md 따라)

### Item 1: Numerical cross-check

```bash
# 본문 모든 숫자 추출 (markdown 마커 제외)
grep -oE "[0-9,]+(\.[0-9]+)?" {6 sections}.md | sort -u > body_numbers.txt

# results JSON flatten
python -c "
import json
def flatten(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flatten(v, path + '.' + k if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from flatten(v, path + f'[{i}]')
    else:
        yield path, o
for p, v in flatten(json.load(open('results_v{N}.json'))):
    print(f'{p}\t{v}')
" > results_flat.tsv
```

각 본문 숫자 검증:
- HR 1.34 → results.json `primary[i].value == 1.34` 존재?
- N=13,225 → study_input.json `study.population.n_target == 13225` 존재?
- CI 0.72-1.01 → `ci_lower=0.72, ci_upper=1.01` 존재?

`[NUMBER?]` 마커 잔존 → hard reject.

### Item 2: Cross-reference scan

```bash
# 본문 인용
grep -oE "(eTable|eFigure|Table|Figure) [0-9]+" {6 sections}.md | sort -u > cited.txt

# supplement caption
grep -oE "^### (eTable|eFigure) [0-9]+|^## (Table|Figure) [0-9]+" supplement.md | sort -u > captions.txt

comm -23 cited.txt captions.txt  # orphan citations (reject)
comm -13 cited.txt captions.txt  # orphan captions (warning)
```

refpack 인용:
```bash
grep -oE "\[refpack:[A-Z][a-zA-Z]+[0-9]{4}[a-z]?\]" {6 sections}.md | sort -u > body_refs.txt
jq -r '.[].citation_key' refpack_v{N}.json | sort -u > pack_keys.txt
comm -23 body_refs.txt pack_keys.txt  # 본문 citation_key가 refpack에 없음 (reject)
```

`[CITATION NEEDED]` 마커 잔존 → reject.

### Item 3: Directional logic check

```bash
grep -nE "concordan|discordan|parallel|converg|consistent with|in line with|opposite|elevated|reduced|protective" {6 sections}.md
```

각 매치 line에서:
- "concordant with [refpack:Chen2022]" → refpack `Chen2022.effect_size_95CI` direction (HR <1 vs >1) vs 본 연구 `results.primary[i].value` direction 비교
- mismatch → reject

### Item 4: Format constraint hard-check

저널 분기 (`study_input_v{N}.json.journal_target`):

**JAMA NO**:
- Main text word count (Methods + Results + Intro + Discussion 합) ≤ 3,000
- Abstract ≤ 350
- Key Points 75-100
- References (refpack에서 본문 citation된 것만) 50-75
- Tables + Figures (본문 + Figure file count) = 5
- Standalone P-value (without 95% CI) — `grep -nE "P[<=][.0-9]+" {6 sections}.md` 후 같은 line에 95% CI 없으면 reject
- STROBE checklist 별도 file 존재
- Article information sections (Data sharing / Code / CRediT / Funding / COI / IRB) 존재

**SR**:
- Abstract ≤ 200 (unstructured, headers X)
- References ≤ 60
- Methods가 Discussion 뒤에 위치 — 본문 어셈블 검증

word count 계산:
```python
import re
def word_count(file):
    text = open(file).read()
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)  # remove HTML comments
    text = re.sub(r'\[refpack:[^\]]+\]', '', text)  # remove refpack markup
    text = re.sub(r'\[[A-Z][^\]]*\]', '', text)  # remove [CITATION NEEDED] etc
    text = re.sub(r'`[^`]*`', '', text)  # remove inline code
    return len(text.split())
```

### Item 5: Internal consistency sweep

3-way 일치:

| Source 1 | Source 2 | Source 3 | check |
|---|---|---|---|
| eMethods §1 | Table 1 caption | methods.md §Cohort | cohort definition |
| eMethods §2 | eTable header | discussion.md 해석 | outcome 정의 |
| methods.md | Table 1 | Table 2/3 | sample size |
| study_input.data_source.period | methods.md | results.md | period |

각 항목 grep으로 추출 후 cross-compare. mismatch → reject.

### Item 6: Inherited content audit

`paper_draft_v{N-1}.md` 있으면:
```bash
diff paper_draft_v{N-1}.md paper_draft_v{N}.md > diff.txt
```

unchanged 부분 (inherited)의:
- 수치 → results.json (new) 일치 검증
- refpack 인용 → refpack_v{N}.json (new) citation_key 존재 검증
- 효과 방향 ("elevated", "reduced") → results.json (new) primary[].value sign 검증

mismatch → "stale inherited claim" reject + 어느 line인지 명시.

## 출력 format

`validation_report.md`:

```markdown
# Validation Report — {study} v{version}

## Run metadata
- timestamp: 2026-05-15T14:23:00Z
- input: paper_draft_v{N}.md + supplement_v{N}.md + study_input_v{N}.json + results_v{N}.json + refpack_v{N}.json
- journal: jama_network_open

## Item 1 — Numerical cross-check
**Status**: PASS
**Findings**:
- 24 unique numbers in body
- All matched to results.json or study_input.json
- [NUMBER?] markers: 0

## Item 2 — Cross-reference scan
**Status**: PASS
**Findings**:
- Table/Figure citations: 8 (all matched to captions)
- refpack citations: 32 (all matched to refpack.json)
- [CITATION NEEDED] markers: 0

## Item 3 — Directional logic check
**Status**: PASS
**Findings**:
- "concordance" mentions: 3, all match direction
- "discordance" mentions: 2, all valid (Chen2022 null vs our elevated — OK)

## Item 4 — Format constraint hard-check (JAMA NO)
**Status**: FAIL
**Word counts**:
- Main text: 2,957 / ≤3,000 ✓
- Abstract: 348 / ≤350 ✓
- Key Points: 92 / 75-100 ✓
- References: 39 / 50-75 ✗ FAIL (need 11 more)
- Tables + Figures: 5 / =5 ✓
**P-value standalone**: 0 violations

## Item 5 — Internal consistency sweep
**Status**: PASS
**Findings**:
- Cohort definition 3-way: OK
- Sample size 4-way: OK
- Period: OK

## Item 6 — Inherited content audit
**Status**: PASS (no v{N-1} or all inherited content checked)

## Summary
- Overall: **FAIL** (Item 4: refs <50)
- Hard rejects:
  - References 39 < 50 — researcher-pubmed 추가 호출 11+ entries
- Warnings: none
- Action items:
  - paper-orchestrator → researcher-pubmed 재호출 (target +11)
  - 추가 keyword 제안: "appendectomy long-term outcomes", "immune function colectomy comparison"
```

## PASS / FAIL 규칙

| Item | hard reject 조건 |
|---|---|
| 1 | `[NUMBER?]` 마커 잔존 / 본문 숫자 results JSON 외 |
| 2 | `[CITATION NEEDED]` 마커 잔존 / orphan citation / refpack 외 citation |
| 3 | directional word ↔ effect direction mismatch |
| 4 | JAMA NO word limit / refs <50 or >75 / tables+figs ≠5 / STROBE 없음 |
| 5 | 3-way mismatch |
| 6 | inherited claim ↔ new results 충돌 |

하나라도 reject → 전체 FAIL.

## Action items 작성 룰

FAIL 시 paper-orchestrator에게 어느 agent를 어느 input으로 재호출할지 구체 명시:

- paper-writer 재호출 (sections X, Y, Z 수정 + 어느 수치를 어느 results.json field로 변경)
- voice-rewriter 재호출 (어느 banned_words 잔존, 어느 canonical_terms 변형)
- researcher-pubmed 재호출 (refs 부족 N개 + 검색 키워드 제안)
- orchestrator 자체 처리 (어느 file format 수정, supplement caption 추가)

## PASS 시 보고

```
audit pass 완료:
- [x] Numerical cross-check (0 mismatch)
- [x] Cross-reference scan (0 orphan)
- [x] Directional logic check (0 conflict)
- [x] Format constraint (JAMA NO main 2,957w / abstract 348w / refs 64 / tables+figs 5)
- [x] Internal consistency (3-way OK)
- [x] Inherited content (0 stale)

→ orchestrator: 어셈블 단계 진행 가능.
```
