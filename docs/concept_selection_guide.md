# Concept ID 선정 가이드

## 목적

연구 설계 문서(프로토콜)에서 **코호트 정의에 필요한 OMOP Standard Concept ID**를 체계적으로 찾고 검증하는 절차.

---

## 1. Concept ID 찾기 — 방법별 장단점

### 1.1 ATLAS Vocabulary Search (권장)

```python
# atlas_auto 패키지
client.connect_site(7, 203)
results = client.search_concepts("appendectomy", domain="Procedure")
```

또는 ATLAS 웹 UI: Vocabulary → Search → 키워드 입력

**장점**: Standard concept만 필터, descendant 포함 여부 확인 가능
**단점**: 한글 검색 제한, 정확한 영문 의학 용어 필요

### 1.2 atlas_auto 내장 Concept DB

```python
from atlas_auto.data.concepts import search_concept, CONDITIONS, DRUGS, PROCEDURES, MEASUREMENTS
search_concept("diabetes")  # → [("type_2_diabetes", 201826, "condition"), ...]
PROCEDURES["appendectomy"]  # → 4198190
```

`src/atlas_auto/data/concepts.py`에 300+ concept 수록. CLI:
```bash
atlas-auto concepts appendectomy
```

**장점**: 오프라인, 빠름
**단점**: 수록 범위 제한 (주요 concept만)

### 1.3 Achilles CDM Results (실제 빈도 확인)

```python
# 기관별 실제 사용 중인 concept + 빈도
GET /cdmresults/{sourceKey}/{domain}
→ conceptId, numPersons, percentPersons
```

**장점**: 실제 CDM에 있는 concept만 확인, 빈도 기반 선택
**단점**: 기관마다 다를 수 있음

### 1.4 KCD → Concept ID 매핑 (한국 특화)

`KCDtoConcept_id/all_kcd_map.csv`: KCD 코드 → OMOP concept ID + 기관별 빈도

```
hospital, common_cd, local_cd1, frequency, concept_id, concept_name
아주대, I109, 110789, 1385626, 320128, Essential hypertension
```

**장점**: 한국 KCD 코드 기반, 기관별 빈도 포함
**단점**: 일부 기관만 (10개)

### 1.5 PubMed/Consensus + OMOP 매핑

```
연구 가설 → 문헌에서 질환명 확인 → OMOP concept 매핑
```

Claude에서 PubMed/Consensus 검색 가능:
```
mcp__claude_ai_PubMed__search_articles("appendectomy Parkinson disease")
mcp__claude_ai_Consensus__search("appendectomy immunological consequences")
```

---

## 2. Concept ID 선정 절차

### Step 1: 연구 설계서에서 변수 목록 작성

```yaml
Target: 충수절제술
Comparators: 담낭절제술, 탈장수술, 일반인구
Outcomes:
  Clinical: UC, CD, Asthma, Atopic derm, RA, CDI, PD, Biliary calc, AMI, T2DM, CRC
  Biomarker: WBC, Neutro, Lympho, Eosino, Mono, Baso, CRP, ESR, RF, ANA,
             Glucose, HbA1c, LDL, TG, HDL, GFR, Uric acid, ALT, GGT, ALP, Albumin, Hgb
Negative Controls: 55개 (충수절제와 관련 없는 질환)
```

### Step 2: OMOP Concept ID 매핑

| 변수 | 검색 방법 | Domain |
|------|---------|--------|
| 수술/시술 | ATLAS Vocabulary "appendectomy" | Procedure |
| 진단 (outcome) | ATLAS Vocabulary "Crohn's disease" | Condition |
| 바이오마커 (outcome) | ATLAS Vocabulary "Leukocytes" | Measurement |
| 약물 (covariate) | ATLAS Vocabulary "metformin" | Drug |
| Negative control | OHDSI NC 목록 또는 자동 선택 | Condition |

### Step 3: 검증

각 concept ID에 대해:

1. **Standard concept인가?** (STANDARD_CONCEPT = 'S')
2. **Descendant 포함 필요?** (`includeDescendants: true`)
3. **실제 CDM에 존재하는가?** (Achilles로 확인)
4. **빈도가 충분한가?** (numPersons > 최소 기준)
5. **다기관 간 일관적인가?** (기관별 빈도 비교)

### Step 4: Concept Set 구성

```json
{
  "items": [
    {
      "concept": {
        "CONCEPT_ID": 4198190,
        "CONCEPT_NAME": "Appendectomy",
        "DOMAIN_ID": "Procedure",
        "STANDARD_CONCEPT": "S"
      },
      "includeDescendants": true,
      "isExcluded": false
    }
  ]
}
```

---

## 3. 바이오마커 코호트 설계 패턴

### 3.1 이진 outcome (HR 분석용)

"수술 전 정상 → 수술 후 첫 이상 발생"을 포착:

```
PrimaryCriteria:
  Measurement: concept = WBC, ValueAsNumber > 11
InclusionRules:
  1. Prior normal value exists (365d)    ← 수술 전 정상이었음
  2. No prior abnormal value (all time)  ← 과거에 한번도 이상 없었음
```

### 3.2 Cutoff 설정 근거

| 카테고리 | 근거 | 예시 |
|---------|------|------|
| 혈액세포 | CBC 정상 참고 범위 | WBC 4.5~11 |
| 염증 마커 | 임상 검사 기준 | CRP < 0.5~1.0 |
| 대사 | ADA, WHO 가이드라인 | Glucose ≥ 126 (당뇨) |
| 간 기능 | 임상 정상 범위 | ALT < 40 |
| 영양 | 임상 기준 | Albumin 3.5~5.5 |

### 3.3 Characterization용 Feature Analysis

**연속값 기술통계**가 필요할 때:

```
WindowedCriteria + DISTRIBUTION + Value as number (aggregate id=7)
→ mean, SD, median, Q1, Q3, min, max 산출

시간 구간: StartWindow.Start.Coeff (-1=before, 1=after index)
concept: conceptSets에 지정
```

API 생성: 기존 FA `copy` → `PUT`으로 시간/concept 변경

---

## 4. Negative Control 선정

### 4.1 원칙

- Target(충수절제술)과 **인과 관계가 없는** 질환
- CDM에서 **충분한 빈도**로 발생
- 최소 **50개 이상** 권장 (EmpiricalCalibration 정확도)

### 4.2 이 연구에서 사용한 NC (55개)

```
4088290 (Absence of breast), 4092879 (Absent kidney),
436634 (Acariasis), 75911 (Acquired hallux valgus), ...
```

`00_config.R`에 전체 목록 정의됨.

### 4.3 NC 품질 확인

```python
# NC HR 분포 확인
median HR ≈ 1.0 → 양호
유의 비율 ≈ 5% → 양호
유의 비율 >> 5% → systematic bias 존재
```

이 연구에서:
- vs Chol: median 1.089, 유의 17.8% ⚠️
- vs GenPop: median 0.654, 유의 27.7% 🔴 (심각한 bias)
- vs Hernia: median 1.222, 유의 9.1% ⚠️

---

## 5. 다기관 Concept Frequency 수집

### 5.1 ATLAS WebAPI (20/29개 기관 수집)

```python
GET /cdmresults/{sourceKey}/{domain}
```

응답: conceptId, numPersons, percentPersons, recordsPerPerson
저장: `concept_frequency/{기관명}_{domain}.csv`

### 5.2 타임아웃 기관 대응

- 120초 타임아웃으로 재시도
- 504 Gateway Timeout → feedernet nginx 180초 제한, 클라이언트 측 조치 불가
- 서버 다운 기관 → KCD 매핑 데이터로 대체

### 5.3 Achilles Measurement Distribution

```python
GET /cdmresults/{sourceKey}/measurement/{conceptId}
→ measurementValueDistribution: min, P10, P25, median, P75, P90, max
```

CDM 전체 환자 대상. **코호트 특이적 아님**.

---

## 6. 연구 설계서 → Concept ID 변환 워크플로우

```
연구 설계서 (프로토콜)
    ↓
[1] 변수 목록 추출 (Target, Comparator, Outcome, NC)
    ↓
[2] ATLAS Vocabulary 검색 → OMOP Concept ID 매핑
    ↓
[3] Achilles로 다기관 빈도 확인
    ↓
[4] 빈도 부족 concept → descendant 추가 또는 대체 concept 선택
    ↓
[5] Concept Set JSON 구성
    ↓
[6] 코호트 정의 (PrimaryCriteria + InclusionRules)
    ↓
[7] ATLAS에 import → feedernet 배포
```

### Claude 활용

```
사용자: "충수절제술과 면역 질환 연구를 설계해줘"
Claude:
  1. PubMed/Consensus로 관련 질환 검색
  2. atlas_auto.data.concepts에서 concept ID 매핑
  3. study_protocol.yaml 자동 생성
  4. atlas-auto protocol --study my_study.yaml --dry-run
```

---

## 7. 주의사항

1. **Standard concept만 사용**: Non-standard concept은 기관마다 매핑이 다를 수 있음
2. **includeDescendants 신중히**: 너무 넓으면 의도치 않은 concept 포함
3. **기관별 concept 차이**: 같은 검사도 기관마다 다른 concept ID 사용 가능 (특히 한국 EDI 코드)
4. **Measurement unit 주의**: 같은 concept이라도 단위가 다를 수 있음 (mg/dL vs mmol/L)
5. **Negative control은 연구 시작 전에 선정**: 결과를 보고 선정하면 bias
