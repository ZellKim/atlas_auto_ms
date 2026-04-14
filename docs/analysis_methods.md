# 분석 방법론 정리

## 1. IPD Pooled Analysis (Main Analysis)

### 데이터 구조
- 16개 기관 CmData (SQLite) — result.zip에서 추출
- CmData 내부: cohorts, outcomes, covariates, covariateRef, analysisRef
- outcomes 테이블: `rowId, outcomeId, daysToEvent` — **이벤트 발생 시점마다 한 행**, 수술 전/후 모두 기록

### PS Matching
- **방법**: Cyclops (Laplace prior, cross-validation)
- **공변량**: CmData covariates (condition, drug, demographic 등) + site dummy
- **매칭**: 1:2 nearest-neighbor, caliper = 0.2 × SD(logit PS)
- **매칭은 1회만**: 수술 시점 baseline 공변량 기준으로 매칭 → matched cohort 확정

### Outcome Model
- Site-stratified (또는 site covariate) Cox proportional hazard regression
- `Surv(time, event) ~ treatment + site`

### 시간 구간별 분석 (Time-window Stratified Analysis)

**핵심**: PS matching은 한번만. 매칭된 동일 코호트에서 outcome 판정 시 시간만 구간별로 다르게 적용.

```
Step 1: Cyclops PS matching (1회)
  → baseline 공변량으로 매칭
  → matched cohort 확정

Step 2: 구간별 Cox (같은 matched cohort)
  → 각 구간에서 "해당 구간 내 첫 이벤트" + "구간까지 생존한 환자만" 분석
```

#### 시간 구간 정의

| 구간 | 기간 | 목적 |
|------|------|------|
| 1-30d | 급성기 | 수술 스트레스 영향 (모든 수술군 동일 예상) |
| 31-90d | 아급성기 | 수술 스트레스 회복 후 차이 시작? |
| 91-365d | 단기 만성 | 충수 특이적 효과 확인 |
| 366-1095d | 중기 | 면역 shift 지속 여부 |
| 1096-3650d | 장기 | 장기 면역 변화 |
| 1-3650d | 전체 | 기존 분석과 동일 (reference) |

#### 구간별 분석 로직

```r
# 해당 구간 내 이벤트만 필터
oc <- outcomes[daysToEvent >= windowStart & daysToEvent <= windowEnd]

# 구간까지 생존한 환자만 포함
df <- df[df$maxFollow >= windowStart]

# follow-up: 구간 끝 또는 관찰 끝 중 작은 값
df$maxFollow <- pmin(daysToObsEnd, windowEnd)

# 이벤트 판정: 구간 내 첫 발생
df$event <- ifelse(timeToEvent <= maxFollow, 1, 0)

# 시간: 구간 시작부터의 상대 시간
df$time <- maxFollow - windowStart + 1  (censored)
df$time[event] <- timeToEvent - windowStart + 1  (event)
```

#### 해석 전략

- **급성기(1-30d)에서만 유의** → 수술 스트레스 영향, 충수 특이적 아닐 가능성
- **급성기 이후(31d+)에서 유의** → 충수 제거의 면역 효과
- **장기(1y+)까지 지속** → 만성 면역 변화 확인
- **비교군(담낭절제/탈장수술)도 수술** → 차이는 "어떤 장기를 뺐느냐"만

#### Landmark Analysis와의 관계
- 각 구간을 독립 분석으로 취급 (landmark analysis 방식)
- 같은 환자가 여러 구간에서 분석 대상이 될 수 있음 (구간별 at-risk 환자 다름)
- 통계적으로 문제없음 — 각 구간이 다른 연구 질문

---

## 2. Characterization (보조 근거)

### 목적
- 수술 전후 바이오마커 실제 값(mean, SD, median, Q1, Q3) 기술통계
- Main analysis(HR)의 기전 설명 보조

### 방법
- ATLAS Characterization + Custom Feature Analysis
- `WindowedCriteria` + `statType=DISTRIBUTION` + `aggregate=Value as number`
- 시간 구간별 × concept별 FA 생성 (copy+PUT 방식)

### 다기관 통합
- **weighted mean ± pooled SD**: 기관별 N, mean, SD로 계산
- 개별 환자 데이터 없이도 정확한 통합 가능
- median/Q1/Q3는 기관별로 개별 보고 (supplementary)

### 제시 방법
- **본문 Table**: 다기관 weighted mean ± pooled SD (시점별 × 코호트별)
- **Supplementary**: 기관별 N, mean, SD 개별 데이터
- **주석**: "PS 매칭 전 전체 코호트 대상 기술통계, 주 분석(HR)과 별도"

---

## 3. Concept Frequency (참고 자료)

### 수집 방법
- ATLAS Achilles 결과: `/cdmresults/{sourceKey}/measurement/{conceptId}`
- measurement drilldown: min, P10, P25(Q1), median, P75(Q3), P90, max
- CDM 전체 환자 대상 (코호트 특이적 아님)
- 20/29개 기관 수집 완료 + KCD 매핑 기반 10개 기관 추가

---

## 4. 환경 설정

| 항목 | 값 |
|------|-----|
| R | 4.5.2 |
| Rtools | 4.5 (C:\rtools45) |
| Java | JDK 21 (C:\Users\data1\java\jdk-21.0.10+7) |
| CohortMethod | 4.2.2 (CmData 호환) |
| Andromeda | 0.6.0 (CmData 호환) |
| FeatureExtraction | 3.2.0 |
| Cyclops | latest |
| duckdb | **제거 필요** (RSQLite dispatch 충돌) |
| CmData 경로 | C:\Users\data1\Desktop\atlas_auto_cmdata\ |
| ATLAS | v2.12.0 (feedernet) |

### 패키지 호환성 주의
- CmData는 CohortMethod 4.2.2 + Andromeda 0.6.0으로 생성됨
- 최신 CohortMethod 6.x / Andromeda 1.x와 호환 안 됨
- duckdb 설치 시 RSQLite method dispatch 충돌 → duckdb 제거 필수

---

## 5. 분석 규모

| 항목 | 수 |
|------|---:|
| 기관 | 16 |
| 비교군 | 3 (Cholecystectomy, General Pop, Hernia repair) |
| Clinical outcomes | 11 |
| Biomarker outcomes | 13 (주요) |
| 시간 구간 | 6 (5개 구간 + 전체) |
| 총 HR 산출 | ~430 |
