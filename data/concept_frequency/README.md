# data/concept_frequency/ — Achilles Concept Frequency (5 domain × 23 site)

OHDSI Achilles가 집계한 **기관별 concept 사용 빈도**. 새 연구 시작 시 target/comparator/outcome **concept ID 선정의 1차 근거** 자료.

## 빠른 찾기

| 목적 | 파일 |
|---|---|
| "이 concept을 어느 기관이 얼마나 쓰는지" | `by_site/{CODE}_{domain}.csv` |
| KCD native vocab 비교 (KCD → SNOMED 매핑 검증) | `kcd_vocab/{CODE}_kcd_{domain}.csv` |
| OHDSI 공개 benchmark와 비교 | `benchmark/Open_Database_{domain}.csv` |
| Measurement biomarker 이미 추려진 결론 | `data/measurement/site_concept_matrix.csv` (다른 폴더) |

## 구조

```
data/concept_frequency/
├── README.md
├── by_site/                  ← 23 표준 feedernet 사이트 × 5 도메인 = 115 files
│   └── {CODE}_{domain}.csv
├── kcd_vocab/                ← KCD 원본 vocab 기반 dump (10 site × 4 도메인)
│   └── {CODE}_kcd_{domain}.csv
├── benchmark/                ← OHDSI 공개 DB benchmark (참조용, 과거 reference/에서 변경)
│   └── Open_Database_{domain}.csv
├── extras/                   ← 중복/특수 (GNUCH 오래된 snapshot, 인천_세종병원 등)
└── reorganize_plan.csv       ← 2026-04-24 재정리 audit trail
```

**5 도메인**: condition, drug, measurement, observation, procedure

**23 표준 사이트** (feedernet):
AUMC, CHNUH, DCMC, DSMC, EUMC, GNUCH, GNUH, HUMC, ISH, JCMJ, KCCH, KDH, KHMC, KHNMC, KWMC, MJH, PNUH, SCHBC, SCHCA, SCHGM, SCHSU, UUH, WKUH

## 파일 스키마

```csv
conceptId,conceptPath,numPersons,percentPersons,recordsPerPerson
3000963,{component}||Survey||Hemoglobin [Mass/volume] in Blood,1775239,0.604,6.29
```

| 컬럼 | 의미 |
|---|---|
| `conceptId` | OMOP concept ID |
| `conceptPath` | hierarchy 경로 (`\|\|` 구분) |
| `numPersons` | 해당 concept을 가진 person 수 (고유) |
| `percentPersons` | CDM 전체 person 대비 비율 (0.0-1.0) |
| `recordsPerPerson` | 해당 person당 평균 record 수 |

## 신규 연구 concept ID 선정 순서

1. **후보 concept 목록화** — 문헌/OHDSI vocabulary/ATLAS로 1차 후보 수집
2. **기관별 커버리지 확인**:
   ```bash
   for site in AUMC CHNUH DCMC ...; do
     grep -E ",${CONCEPT_ID}," by_site/${site}_condition.csv
   done
   ```
   또는 pandas로:
   ```python
   import pandas as pd, os
   root = 'data/concept_frequency/by_site'
   sites = sorted({f.split('_')[0] for f in os.listdir(root)})
   rows = []
   for s in sites:
       df = pd.read_csv(f'{root}/{s}_condition.csv')
       hit = df[df.conceptId == CONCEPT_ID]
       rows.append({'site': s, 'numPersons': hit.numPersons.sum()})
   pd.DataFrame(rows)
   ```
3. **Threshold 적용**:
   - `numPersons ≥ 100` — rare outcome 최저선
   - `percentPersons ≥ 0.01` — 유병률 1% 이상
4. **Descendants 확장 여부 결정** — ATLAS에서 `includeDescendants=true`로 확장 시 실제 어떤 concept이 포함되는지 `conceptPath`로 추정 가능
5. **Measurement의 경우** → `data/measurement/site_concept_matrix.csv`로 최종 결정된 concept + unit 확인 (이미 filter된 상태)

## KCD vocab 폴더 (`kcd_vocab/`)

일부 기관은 SNOMED 매핑 전 **KCD 원본 코드**로도 Achilles dump를 제공. 경상국립대(GNUH), 경희의료원(KHMC v1/v2), 대구가톨릭(DCMC), 부산대(PNUH), 순천향천안(SCHCA), 아주대(AUMC), 원광대(WKUH), 원주세브란스(WSMC), 이대목동(EUMC) — 10 site × 4 domain (drug 제외).

**용도**:
- KCD → SNOMED 매핑 검증 (mapping 누락 의심 시)
- condition 진단 빈도를 KCD 코드 단위로 확인
- Vocabulary sanity check

## Benchmark (`benchmark/`)

`Open_Database_{domain}.csv` — OHDSI/EHDEN 공개 데이터베이스의 concept frequency. 한국 기관 데이터와 **비교 benchmark**로 사용 (예: 특정 질환의 기록 빈도가 국내 vs 해외 차이).

## Extras (`extras/`)

- `duplicate_GNUCH_*.csv` — GNUCH의 오래된 snapshot (새 snapshot은 by_site/에 있음)
- `KHNMC_measurement_distribution.csv` — measurement value 분포 (standard frequency 아님)
- `인천_세종병원_*.csv` — 표준 23 사이트 아닌 참고 데이터

## 재정리 이력

2026-04-24: 혼용된 네이밍 체계 정리.
- Korean full name → English CODE로 변환 (18 사이트)
- `_kcd` 접미사 파일 → `kcd_vocab/` 분리
- `Open_Database` → `benchmark/`
- 중복 (같은 site-domain에 한/영 둘 다 존재) → row count 많은 쪽 채택, 구 버전은 `extras/duplicate_*.csv`

Audit: `reorganize_plan.csv`, script: `data/scripts/reorganize_concept_frequency.py`

## 관련 데이터

- `data/measurement/` — measurement만 추려서 biomarker 기준으로 정리 (최종 결정 포함)
- `data/atlas_benchmark/` — API endpoint, PRESET FA, ETRI measurement 리스트
- `data/site_mapping/` — site code ↔ cdmName ↔ sourceKey ↔ 한글명 매핑
