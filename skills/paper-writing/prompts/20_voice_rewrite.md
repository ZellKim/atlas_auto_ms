# Prompt 20 — Voice Rewrite

> 호출자: `voice-rewriter` (paper-writer 완료 후)
> 목적: 6 섹션 통합 voice pass — banned_words 제거 + canonical_terms 통일 + 어조 동기화
> 출력: 같은 6 파일 in-place 덮어쓰기 (`.pre_voice.md` backup)

## Root rules (위반 시 reject)

1. **사실 보존** — 수치 / 인용 / 효과 방향 절대 변형 금지
2. **인용 markup 보존** — `[refpack:citation_key]` placeholder 그대로
3. **마커 보존** — `[CITATION NEEDED]` / `[NUMBER?]` 마커 손대지 말 것 (validator 처리 대상)

## Inputs

- `studies/{study}/docs/draft/{version}/{methods,results,intro,discussion,abstract,title}.md` (6 파일)
- `skills/paper-writing/style/banned_words.txt`
- `skills/paper-writing/style/preferred_alternatives.md`
- `skills/paper-writing/style/canonical_terms.md`
- `skills/paper-writing/voice/ms_voice_profile.md` (있으면)
- (선택) `studies/{study}/docs/paper_draft_v{N-1}.md` — voice reference

## 워크플로우

### Step 1: Backup

각 6 파일 → `*.pre_voice.md`로 copy (paper-orchestrator가 사전 처리, voice-rewriter는 검증만).

### Step 2: banned_words sweep

```bash
grep -niEf banned_words.txt {6 files}
```

각 매치:
1. **단순 substitution 대신 문장 구조 재작성 우선** — `preferred_alternatives.md` context 보고 선택
2. 1 문단 내 동일 transitional ("however", "furthermore") 2회 이상 → 분산 or 삭제
3. "It is important to note" 같은 filler는 삭제 후 본문 직접 서술

처리 후 file in-place edit.

### Step 3: canonical_terms 통일

`canonical_terms.md`의 표 읽고 variant 패턴 추출:
- "pre-specified" → "prespecified"
- "post-appendectomy" / "post appendectomy" → "postappendectomy"
- "FeederNet" → 검출 시 즉시 alert (canonical_terms에 따라 "federated OMOP CDM network of N Korean tertiary hospitals" 표현으로 치환)

각 6 파일 grep 후 substitution.

### Step 4: 문장 / 문단 다양성

각 6 파일에 대해 측정:
- 평균 문장 길이 (words/sentence)
- 문장 길이 SD — 낮으면 (e.g., <8) AI tell
- 문단 시작 패턴 entropy — 같은 구조 ("In this study", "We found that") 반복 시 alert
- 인용 위치 — 모두 문장 끝에 있으면 일부 중간 배치로 분산

수정 룰:
- 짧은 문장(8-12 words) + 긴 문장(30+ words) 혼합
- 매 문단 첫 문장은 다른 구조로 시작 (명사구 / 종속절 / 수치 / 대조 접속어 순환)
- 토픽 문장 위치 가변 (첫 / 두 번째 / 마지막)
- 인용을 문장 *중간*에 배치 허용: `...Lee et al.[refpack:Lee2023] reported a 23% reduction, though...`

### Step 5: 인간 학자 습관 (디자인 doc §4-3)

Discussion §3 mechanisms 안:
- 1-2개 mechanistic speculation 보존 ("One possible explanation is...")
- 추가 speculation 없으면 자연스럽게 1개 보강 (단, 사실 변형 X)

Discussion §4 limitations 안:
- 의도적 hedging 1-2회 ("This is, admittedly, an indirect measure")
- 단정 → 유보 → 재단정 강도 변화 보존

전체 본문:
- 숫자 표현 자연 흐름 — 매번 같은 포맷 강제 X
- canonical HR format 유지하되 본문 흐름에 따라 약간의 어휘 다양 OK ("the hazard ratio was X" / "we observed an HR of X")

### Step 6: ms_voice_profile 강제 (있으면)

`voice/ms_voice_profile.md` 로드 후:
- 자주 쓰는 접속어 / 평균 문장 길이 분포 / hedging 빈도 / limitations 서술 방식 / 인용 위치 선호도
- 본 paper 6 섹션 metrics와 비교
- 편차 크면 본문 일부 재구성 (사실 보존)

### Step 7: 섹션 간 어조 일관성

- Methods 건조 유지 — "interestingly" / "notably" 잠입 제거
- Results 해석 없이 유지 — "as expected" / "consistent with" 제거 (Discussion으로 이동 X, 그냥 삭제)
- Discussion / Intro narrative 톤 일관성

### Step 8: metadata 출력 + 보고

각 파일 끝에 추가:
```
<!-- voice_pass: 2026-05-15T...; banned_substituted: 8; canonical_unified: 3; sentence_length_sd: 12.4; paragraph_starts_distinct: 4 -->
```

paper-orchestrator에 보고:
```
voice rewrite 완료:
- methods.md: banned 3 / canonical 2 / metrics OK
- results.md: banned 1 / canonical 0 / metrics OK
- intro.md: banned 5 / canonical 1 / "however" 4 in §2 → 분산
- discussion.md: banned 7 / canonical 4 / "Taken together" 1 → 삭제
- abstract.md: banned 2 / canonical 1
- title.md: clean
Total: 18 banned substituted, 8 canonical unified.
```

## 사용자 인터랙션

직접 호출 X — paper-orchestrator가 위임. 결과만 보고.

## 주의

- 인용 markup `[refpack:Lee2024]` — 절대 변형 금지 (validator superscript 변환 시 키 필요)
- 수치 변형 금지 — "13,225" → "approximately 13,000" 같은 paraphrase 금지
- `[CITATION NEEDED]` / `[NUMBER?]` 마커 보존
- 본문 길이가 hard limit 위반하지 않게 — 추가 시 word count 재측정

## Edge cases

- 본문에 banned_words 합법적 사용 (예: "leverage" in "leveraged from EHR")? → context보고 keep OK. 단 본문 흐름에 거슬리면 더 자연스러운 단어로
- canonical_terms에 변형 없는데 새 약어 도입 (예: "PSM") → first mention full + 약어 도입 OK. canonical_terms.md에 entry 추가 권장 (orchestrator에 알림)
