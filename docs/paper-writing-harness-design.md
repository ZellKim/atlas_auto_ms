# Paper-Writing Harness 설계 문서

> **목적**: 정리된 연구계획(SAP) + 분석결과 → *Scientific Reports* 투고용 논문 초고를 일관되게 생성하는 하네스(SKILL) 설계
> **상태**: 설계 완료, 빌드 미착수
> **다음 단계**: Claude Code에서 L1 입력 스키마부터 구현 시작

---

## 1. 최종 목표

연구계획서와 분석결과가 준비된 상태에서, 한 번의 파이프라인으로 *Scientific Reports* 투고용 논문 초고(본문 + 레퍼런스 + 부속 문서)를 생성. 매번 같은 품질·같은 voice·환각 없는 인용·human-like 문체로 산출.

핵심 제약 3가지:
1. **인용 환각 금지** — Reference Pack 안에 있는 것만 인용
2. **수치 환각 금지** — Input Contract의 results JSON 밖 숫자 금지
3. **AI 냄새 제거** — author voice profile 기반 rewrite 강제

---

## 2. 전체 아키텍처

```
[입력]                          [하네스]                        [출력]
─────────                       ─────────                       ─────────
연구계획서(SAP)         ┐                                ┌─ 초고 .docx
분석결과(테이블/그림)   ├──→  paper-writing 스킬  ──→   ├─ Reference list
타겟 저널 = SR          │     (Scientific Reports용)      ├─ Cover letter
저자 voice profile      ┘                                └─ Submission checklist
```

5-Layer 모듈:

```
L1. Input Contract       — 입력 정형화 (study + results JSON)
L2. Reference Pack       — PubMed 검색 + intended_use 분류
L3. Section Generators   — Methods → Results → Intro/Discussion → Abstract/Title
L4. Voice Layer          — human-like rewrite (ms voice profile 기반)
L5. Validator            — 인용/수치/포맷/AI-tell 검증
```

섹션 생성 의존성:

```
Methods ──┐
          ├──→ Results ──→ Discussion ──┐
L1 ───────┘                              ├──→ Abstract
                                         │
Intro ───────────────────────────────────┤
                                         │
                                         └──→ Title
```

Methods를 먼저 쓰는 이유: SAP에서 직접 옮겨오므로 가장 결정적, 다른 섹션 사실의 기반이 됨.
Abstract/Title은 본문 완성 후 추출 — 본문과 불일치 방지.

---

## 3. *Scientific Reports* 포맷 요구사항

프롬프트에 박아둘 저널 특화 규칙:

- **구조**: Title → Abstract (≤200 words, unstructured) → Introduction → Results → **Discussion → Methods** → References → Figures/Tables/Supplementary
  - ⚠️ Methods가 Discussion **뒤**에 옴 (전통적 IMRaD와 다름)
- **분량**: 본문 ~4,500 words, References ≤60개 기본
- **인용 스타일**: numeric, superscript, Vancouver-like
- **필수 섹션**: Data availability, Code availability, Ethics, Author contributions, Competing interests

---

## 4. Layer별 상세 명세

### L1. Input Contract

연구계획서/결과의 자유 형식 입력을 표준 JSON으로 정규화. 모든 후속 단계의 single source of truth.

```json
{
  "study": {
    "design": "retrospective cohort",
    "data_source": "HIRA 2015-2022",
    "population": { "inclusion": [...], "exclusion": [...], "n": 12345 },
    "exposure": { "definition": "...", "operationalization": "..." },
    "outcome": { "primary": "...", "secondary": [...] },
    "covariates": [...],
    "analysis": ["PSM", "Cox PH", "scenario analysis"]
  },
  "results": {
    "table1": {...},
    "primary": { "metric": "HR", "value": 1.23, "CI": [1.10, 1.38], "p": "<0.001" },
    "secondary": [...],
    "sensitivity": [...]
  },
  "hypotheses": {
    "primary": "...",
    "secondary": [...]
  }
}
```

**디폴트 입력 방식**: 수치만 JSON으로 수동 정리해서 입력 (SAS/R output paste 아님).

### L2. Reference Pack Builder

PubMed 검색 → 30~60건 수집 → 각 항목에 다음 메타데이터 부착:

```json
{
  "pmid": "...",
  "citation_key": "Lee2023",
  "design": "...",
  "population": "...",
  "exposure": "...",
  "outcome": "...",
  "effect_size_95CI": "...",
  "key_finding": "...",
  "limitations": "...",
  "quotable_claim": "정확히 인용 가능한 한 문장",
  "intended_use": "discussion/concordance"
}
```

`intended_use` 분류:
- `intro/burden` — 질병 부담 통계
- `intro/prior_evidence` — 기존 효과 추정
- `intro/gap` — 알려지지 않은 부분
- `discussion/concordance` — 본 결과와 일치
- `discussion/discordance` — **불일치 (1~2개 강제 포함)** ← 사람 냄새 핵심
- `discussion/mechanism` — 메커니즘 가설
- `methods/precedent` — 같은 방법론 선례

**핵심 원칙**: LLM은 자기 결과를 지지하는 인용만 모으는 편향이 있음. `discordance` 강제 포함이 이를 방지하고 동시에 human-like writing의 핵심 장치가 됨.

### L3. Section Generators

각 섹션 독립 프롬프트. 공통 규칙:
- pack에 없는 claim → `[CITATION NEEDED]` 표시, 절대 임의 생성 금지
- results JSON에 없는 수치 → `[NUMBER?]` 표시
- 인용 인덱스 매핑표를 본문과 함께 출력

섹션별 voice 차별화:
- **Introduction**: 4문단(burden → prior evidence → gap → objective), 약간 narrative
- **Methods**: 건조, 짧은 문장, 수동태 OK, 수식어 최소
- **Results**: *해석 없이* 수치만, 한 효과크기 = 한 문장
- **Discussion**: 5문단 고정(principal findings → comparison with literature → mechanisms → strengths/limitations → implications), voice-rich, limitations는 별도 나열이 아닌 본문 흐름에 녹임
- **Abstract**: ≤200 words, unstructured
- **Title**: 본문 완성 후 추출

### L4. Voice Layer

L3 출력(정확한 내용) → L4 rewrite(어떻게 쓸지) 2-pass 구조. 사실/인용은 보존, 문장 구조와 어휘만 재구성.

#### 4-1. Banned Words / Preferred Alternatives

```
❌ delve into       → ✅ examine, look at, study
❌ leverage         → ✅ use, draw on
❌ underscore       → ✅ show, point to
❌ pivotal/crucial role → ✅ role (또는 구체 메커니즘 명시)
❌ Taken together   → ✅ (그냥 다음 문장으로)
❌ In conclusion    → ✅ (내용으로 결론임이 드러나게)
❌ importantly/notably/remarkably → ✅ 대부분 삭제
❌ comprehensive/robust/novel insights → ✅ 구체 서술로 대체
```

#### 4-2. 문장·문단 다양성 규칙

- 한 문단 내 문장 길이 분산: 짧은 문장(8~12 words) + 긴 문장(30+ words) 혼합
- 매 문단 첫 문장은 다른 구조로 시작 (명사구 / 종속절 / 수치 / 대조 접속어 등 순환)
- 토픽 문장 위치 가변 (첫 문장 / 두 번째 / 마지막 섞기)
- 인용을 문장 *중간*에 배치 허용: `...Lee et al.¹² reported a 23% reduction, though...`

#### 4-3. 인간 학자 습관 모방

- 의도적 hedging: *"This is, admittedly, an indirect measure"*
- 한 문단 안 주장 강도 변화: 단정 → 유보 → 재단정
- Discussion에 1~2개의 mechanistic speculation 허용: *"One possible explanation is..."*
- 숫자 표현 다양화 (매번 같은 포맷 금지)

#### 4-4. Author Voice Profile (재사용 자산)

ms님 기존 published paper 2~3편 첨부 → idiolect 추출 → `ms_voice_profile.md`에 저장:
- 자주 쓰는 접속어
- 평균 문장 길이 / 분산
- hedging 빈도
- limitations 서술 방식
- 인용 위치 선호도

모든 후속 논문에 첨부해서 *ms-like writing* 달성. **이게 generic human-like보다 강력함.**

### L5. Validator

ref-validator.jsx 확장판. 자동 통과 안 됨 — 사람 검토 필수.

체크 항목:
- **인용 무결성**: 본문 [N] ↔ refs 매칭, 누락/중복
- **수치 무결성**: 본문 모든 숫자가 L1 results JSON에 존재
- **포맷**: 단어수, 섹션 순서(SR), 필수 declarations
- **AI tell**: banned word 빈도, 문장 길이 표준편차, 문단 시작 패턴 entropy
- **환각 표식**: `[CITATION NEEDED]`, `[VERIFY]`, `[NUMBER?]` 잔존 여부

---

## 5. 폴더 구조

```
paper-writing/
├── SKILL.md                          # 메인 진입점, 워크플로우
├── SKILL_ref_scientific_reports.md   # SR 특화 규칙
├── contracts/
│   ├── study_input.schema.json       # L1 입력 스키마
│   └── reference.schema.json         # L2 레퍼런스 스키마
├── prompts/
│   ├── 00_normalize_input.md
│   ├── 01_build_refpack.md
│   ├── 10_methods.md
│   ├── 11_results.md
│   ├── 12_intro.md
│   ├── 13_discussion.md
│   ├── 14_abstract.md
│   ├── 15_title.md
│   ├── 20_voice_rewrite.md
│   └── 30_validate.md
├── voice/
│   └── ms_voice_profile.md
├── style/
│   ├── banned_words.txt
│   ├── preferred_alternatives.md
│   └── sr_format_rules.md
└── tools/
    ├── ref-validator.jsx             # 기존 자산 재사용
    └── ai-tell-detector.jsx          # 신규
```

다른 저널 추가 시: `SKILL_ref_*.md` 한 장 추가 (claims-research가 HIRA/NHIS 분기하는 패턴 그대로).

---

## 6. 디폴트 결정사항

세션에서 합의된 디폴트:

| 항목 | 결정 |
|------|------|
| 타겟 저널 | *Scientific Reports* (1차), 추후 JAMA Netw Open 등 확장 가능 |
| 작성 언어 | 영문 직접 작성 (한글→영문 변환은 AI tell 증가) |
| 결과 입력 방식 | 수치를 JSON으로 수동 정리 (SAS/R output paste 아님) |
| 검토 단위 | 섹션 단위 사람 검토 |
| 버전 관리 | 논문별 폴더 |

---

## 7. 통합 자산 (재사용 가능)

기존 자산 매핑:
- **ref-validator.jsx** (`ZellKim/theory_ms/tools/`) → L5에서 인용 무결성 검증에 재사용
- **하네스 원칙** ("모르면 물어라, 상상하지 마라, 추측하지 마라") → 모든 L3 프롬프트의 root rule로 명시
- **claims-research 스킬 패턴** → SKILL.md + SKILL_ref_*.md 분기 구조 그대로 적용

---

## 8. 빌드 순서 (Claude Code 작업용)

1. **L1 contract** (`contracts/study_input.schema.json`) — JSON Schema 작성, 예시 instance 1개 동봉
2. **L2 reference schema** (`contracts/reference.schema.json`) + `prompts/01_build_refpack.md`
3. **Style assets** (`style/banned_words.txt`, `preferred_alternatives.md`, `sr_format_rules.md`)
4. **SR format rules** (`SKILL_ref_scientific_reports.md`)
5. **Section prompts** (Methods → Results → Intro → Discussion → Abstract → Title 순)
6. **Voice rewrite prompt** (`prompts/20_voice_rewrite.md`)
7. **Validator** (`prompts/30_validate.md` + `tools/ai-tell-detector.jsx`)
8. **메인 SKILL.md** — 위 모듈을 오케스트레이션
9. **End-to-end dry run** — 가상의 SAP+results 한 세트로 전체 파이프라인 통과 테스트
10. **ms voice profile** — 본인 published paper 2~3편으로 추출 (별도 세션)

---

## 9. Open Questions (빌드 중 결정 필요)

- L2 PubMed 검색 자동화 수준: 키워드 LLM 생성 vs ms가 검색식 직접 제공
- L4 voice rewrite를 한 번에 통째로 vs 문단 단위로
- L5 AI-tell-detector를 정량 임계값 기반 차단 vs 보고만 하고 사람 결정
- 한 논문 = 한 GitHub repo vs paper-writing repo에 `papers/{paper_id}/` 하위 폴더
- Cover letter / response to reviewers는 동일 스킬 안에 vs 별도 스킬

---

## 10. 다음 액션 (Claude Code 첫 세션)

1. 이 문서 읽고 전체 그림 확인
2. `paper-writing/` 디렉토리 초기화
3. **L1 `study_input.schema.json` 작성부터 시작**
   - JSON Schema (draft-07 or 2020-12)
   - 예시 instance 1개 동봉 (예: TZD-fracture-CKD 가상 입력)
4. 진행하면서 Open Questions 하나씩 해결
