# paper-writing skill

> 정리된 SAP + 분석결과 → JAMA Network Open / Scientific Reports 투고용 초고를 일관 voice로 생성.
> 5-Agent 팀 + skeleton-first 워크플로우. 인용·수치 환각 금지, AI 냄새 제거.

## 진입점

사용자 trigger (예: `/paper start --journal jama_no --study studies/appendectomy`) → `paper-orchestrator` agent가 워크플로우 디스패치.

## 5-Agent 팀

| Agent | 책임 | 입력 | 출력 |
|---|---|---|---|
| `paper-orchestrator` | 워크플로우 디스패치, skeleton 합의, 최종 어셈블 | 사용자 trigger + study/results JSON | 본문 + supplement + cover letter |
| `researcher-pubmed` | L2 Reference Pack 빌더 — PubMed 검색 + intended_use 분류 | study JSON + 키워드 | `refpack.json` (30~60건) |
| `paper-writer` | 본문 6 섹션 (Methods/Results/Intro/Discussion/Abstract/Title) 통합 작성 | skeleton + study JSON + results JSON + refpack | 각 섹션 `.md` |
| `voice-rewriter` | 6 섹션 받아 banned_words + canonical_terms + voice profile 강제 | 6 섹션 + style/voice 자산 | rewritten 본문 |
| `validator` | L5 audit checklist 6-item 자동 sweep | 본문 + supplement + refpack + results JSON | `validation_report.md` |

**5 agent로 줄인 이유**: 통일성 ↑ (1개 paper-writer가 voice·용어 동기화), 단일 final voice pass.

## 워크플로우 (skeleton-first)

```
[trigger]
   │
   ├── paper-orchestrator: study/results JSON 정규화 (L1 contract)
   │
   ├─→ researcher-pubmed: refpack.json (병렬 가능)
   │
   ├─→ paper-orchestrator: 6 섹션 skeleton 1-paragraph each (사용자 검토 ★)
   │
   ├─→ paper-writer: skeleton + JSON + refpack → 6 섹션 .md
   │
   ├─→ voice-rewriter: 6 섹션 통합 rewrite (어조 동기화)
   │
   ├─→ validator: audit checklist sweep
   │     ├── PASS → paper-orchestrator: 최종 어셈블 (.docx)
   │     └── FAIL → paper-writer 재호출 (수정 지시 동봉)
   │
   └─→ paper-orchestrator: 최종 산출물 → studies/{study}/docs/
```

**Skeleton checkpoint ★**: paper-writer 호출 전 6 섹션 skeleton 1-paragraph each 사용자 검토 — 통일성 보장 핵심.

## 3대 환각 금지 (모든 agent root rule)

1. **인용 환각** — `refpack.json` 밖 citation 금지. 없으면 `[CITATION NEEDED]` 마커.
2. **수치 환각** — `results JSON` 밖 숫자 금지. 없으면 `[NUMBER?]` 마커.
3. **AI 냄새** — `style/banned_words.txt` 위반 금지. `voice/ms_voice_profile.md` 강제.

## 입력 spec (L1 Input Contract)

`contracts/study_input.schema.json` 참조. 모든 후속 단계의 single source of truth.

```json
{
  "study": { "design", "data_source", "population", "exposure", "outcome", "covariates", "analysis" },
  "results": { "table1", "primary", "secondary", "sensitivity" },
  "hypotheses": { "primary", "secondary" },
  "journal_target": "jama_network_open" | "scientific_reports"
}
```

`contracts/reference.schema.json` — L2 refpack 엔트리 형식.

## 저널 분기

- `SKILL_ref_jama_network_open.md` — JAMA NO 특화 (≤3,000 words main, 350w abstract, 50-75 refs, 5 tables+figures, STROBE checklist, CRediT, AMA refs)
- `SKILL_ref_scientific_reports.md` — SR 특화 (≤4,500 words, 200w unstructured abstract, ≤60 refs, Methods가 Discussion 뒤)

paper-orchestrator가 `journal_target` 보고 해당 SKILL_ref_*.md 로드.

## 폴더 구조

```
skills/paper-writing/
├── SKILL.md (this)
├── SKILL_ref_jama_network_open.md
├── SKILL_ref_scientific_reports.md
├── contracts/
│   ├── study_input.schema.json
│   └── reference.schema.json
├── prompts/
│   ├── 00_normalize_input.md
│   ├── 01_build_refpack.md
│   ├── 05_skeleton.md      ← skeleton-first checkpoint
│   ├── 10_methods.md ... 15_title.md
│   ├── 20_voice_rewrite.md
│   └── 30_validate.md
├── voice/
│   └── ms_voice_profile.md (CHANGELOG에서 추출)
├── style/
│   ├── banned_words.txt
│   ├── preferred_alternatives.md
│   ├── canonical_terms.md  ← lookback / prespecified 등 정착어
│   ├── sr_format_rules.md
│   └── jama_no_format_rules.md
├── tools/
│   ├── audit_checklist.md  ← L5 validator 6-item
│   ├── ref-validator.jsx (TBD)
│   └── ai-tell-detector.jsx (TBD)
└── examples/
    └── appendectomy_v9_4/  ← dry-run seed
        ├── study_input.json
        ├── results.json
        └── refpack.json
```

## 산출물 저장

산출물은 `studies/{study}/docs/`에 저장 (기존 v9_4 구조 유지). paper-writing/은 도구만.

## 통일성 보장 4-장치

1. **L1 Input Contract** — 모든 agent가 같은 JSON 참조 → 수치 무결성
2. **canonical_terms.md** — lookback/prespecified 등 정착어 single ledger
3. **Final voice pass** — voice-rewriter 1개 agent가 6 섹션 받아 통합 rewrite → 어조 동기화
4. **L5 audit sweep** — internal consistency 6-item (audit_checklist.md 참조)

## 호출 예

```
사용자: "/paper start --journal jama_no --study appendectomy --version v10"
→ paper-orchestrator 호출
→ studies/appendectomy/docs/study_input_v10.json 로드 (또는 신규 정규화)
→ refpack 생성 → skeleton 합의 (사용자 review) → 본문 → voice → validator → 최종 .docx
```

## 관련 자산

- `docs/paper-writing-harness-design.md` — 본 skill 5-Layer 설계
- `studies/appendectomy/docs/paper_draft_v9_4_*.md` — v9.4 reference template
- `studies/appendectomy/docs/paper_draft_CHANGELOG.md` — canonical_terms 추출 source
- memory `feedback_paper_audit_pass.md` — audit_checklist.md 출처
- memory `feedback_no_feedernet_in_papers.md` — FeederNet 용어 금지 (banned_words에 반영)
