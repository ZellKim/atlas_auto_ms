# data/site_mapping/ — 기관 ID·DB 매핑 표준

다기관 feedernet 연구에서 **기관 식별·데이터베이스 연결·API 호출에 필요한 모든 매핑**이 모인 곳.

## 빠른 찾기

| 목적 | 파일 |
|---|---|
| 기관 코드 ↔ 이름 ↔ 모든 ID 4종 | `site_id_mapping_full.csv` |
| 기관 코드 ↔ PostgreSQL sourceKey | `source_key_mapping.csv` |
| **기관별 총 환자수 + 데이터 기간 + DB명** | `site_summary_23.csv` |
| 매핑 검증 결과 (JSON, 구조화) | `site_mapping_verified.json` |

## 파일 상세

### `site_id_mapping_full.csv` — 4종 ID + 한글명

```csv
code,group_id,site_id,portal_orgId,cdmId,cdmName,institution,in_13sites
AUMC,9,191,16,588,AUMC_5.3.1_11,아주대학교병원,Y
```

| 컬럼 | 의미 | 사용처 |
|---|---|---|
| `code` | 짧은 영문 코드 | 스크립트에서 site 식별 |
| `group_id` | ATLAS WebAPI group 경로 | `/api/v1/atlas/{group_id}/{site_id}/...` |
| `site_id` | ATLAS WebAPI site 경로 | 동상 |
| `portal_orgId` | feedernet 포탈 organization ID | 포탈 UI |
| `cdmId` | feedernet CDM ID | execution 트리거 `cdmIds=[...]` |
| `cdmName` | CDM 인스턴스 이름 | 포탈 dashboard 표시 |
| `institution` | 한글 기관명 | 보고서 |
| `in_13sites` | 13-site 분석 포함 여부 | 연구 design 참고 |

### `source_key_mapping.csv` — sourceKey

```csv
code,cdmName,sourceKey,group_id,site_id
AUMC,AUMC_5.3.1_11,cdmpv53_251128,9,191
```

**sourceKey** = PostgreSQL 스키마 이름 (Achilles 쿼리에서 사용).
주의: `sourceKey ≠ cdmName`.

### `site_summary_23.csv` — 총 환자수 + 기간 + DB명

```csv
code,source,source_key,period_start,period_end,total_persons,in_20sites
AUMC,AUMC_5.3.1_11,cdmpv53_251128,1993,2026,"2,938,928",Y
```

| 컬럼 | 의미 |
|---|---|
| `code` | 기관 코드 |
| `source` | CDM 인스턴스 이름 (`cdmName`) |
| `source_key` | **조회된 PostgreSQL DB 스키마** (Achilles 쿼리 대상) |
| `period_start` | 데이터 시작 연도 |
| `period_end` | 데이터 종료 연도 |
| `total_persons` | CDM 내 person 총수 (feedernet dashboard API 기준) |
| `in_20sites` | 20-site 분석 포함 여부 (Y/N/조건부) |

**업데이트**: `python data/scripts/update_site_summary.py` — feedernet dashboard API에서 최신 값을 가져와 덮어씀.

### `site_mapping_verified.json`

API로 검증된 매핑 상세 (JSON). 각 기관의 atlas version, engine ID, accessAtlas 등 부가 정보 포함.

## 코드 사용 예

```python
import csv
with open('data/site_mapping/site_summary_23.csv', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        print(r['code'], r['total_persons'], r['source_key'])
```

```python
# cdmId 리스트로 execution 트리거
import csv
cdm_ids = []
with open('data/site_mapping/site_id_mapping_full.csv', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        if r['in_13sites'] == 'Y':
            cdm_ids.append(int(r['cdmId']))
```

## 관련

- `data/concept_frequency/by_site/` — 23 기관 × 5 도메인 Achilles concept frequency
- `data/measurement/site_concept_matrix.csv` — biomarker 단위 기관 선택
- `docs/system_knowledge_base.md` §1.3 — feedernet API 매핑 함정
