# 프로젝트 진행 상황

**repo**: https://github.com/ZellKim/atlas_auto_ms
**최종 업데이트**: 2026-04-16

> 상세 지식(API, 방법론, 이슈 해결, 기관 매핑, 실행 기록)은 → `docs/system_knowledge_base.md`

---

## 현재 상태

### Python 패키지 (`src/atlas_auto/`) — 완료

| 모듈 | 역할 |
|------|------|
| `client.py` | feedernet 포탈 + WebAPI 클라이언트 + concept 검증 메서드 |
| `builder.py` | Estimation JSON 스펙 빌더 (TCO, PS, covariates) |
| `cohort_designer.py` | YAML → ATLAS CIRCE JSON |
| `protocol.py` | 전체 파이프라인 오케스트레이션 |
| `runner.py` | 본원(R) + 타기관(API) 통합 실행 |
| `cli.py` | CLI: protocol, run, status, download, concepts |

### Cloud 모니터링 (`cloud_monitor/`) — 배포됨

GCP Cloud Function + Scheduler → Telegram 알림.
MONITOR_TARGETS: 11018, 11019 (2개 analysis)

### R 분석 (`R/pooled_analysis/`) — 통합 완료

IPD pooled analysis 파이프라인. Cyclops PS + 1:1 matching + site-stratified Cox.

---

## 확정: 13개 기관 (2026-04-15)

AUMC, CHNUH, DCMC, GNUCH, HUMC, ISH, JCMJ, KDH, KHNMC, KWMC, SCHCA, SCHGM, SCHSU
— multi-concept OR + Achilles 재수집 후 22개 바이오마커 전부 가용.
GNUH만 CRP 누락으로 제외.

### Primary comparators

vs Cholecystectomy, vs Hernia Repair. vs GenPop은 supplementary (maxCohortSize capping + NC bias).

---

## 진행 중: Estimation Final 실행

이전 v2 (11000~11004)에서 오류 수정 후 최종 재실행:
- CRP dual-unit 코호트 수정 (1274 mg/dL, 1275 mg/L)
- Neutro# dual-unit 코호트 수정 (1276 thou/uL, 1277 /uL)
- execution cancel 버그 수정 (EXECUTING 상태 포함)
- cohortDefinitions 누락 수정

| Analysis | ID | 내용 | 상태 |
|----------|:---:|------|:---:|
| **clinical_final_v4** | **11019** | 11 clinical outcomes | 🔄 실행 중 |
| **biomarker_final** | **11018** | 22 biomarker outcomes | 🔄 실행 중 |

13개 기관 대상.

---

## 확보된 자산

### 데이터

참조 데이터를 `data/`로 통합 정리 (원본: `C:\Users\data1\Desktop\atlas_auto_cmdata`)

| 데이터 | 경로 | 상태 |
|--------|------|:---:|
| Achilles 23기관 × 5 domain | `data/concept_frequency/` (168 files) | ✅ |
| Characterization (PRESET 5구간) | `data/characterization/char_preset_all_results.csv` | ✅ 13기관 |
| 바이오마커 concept 매핑 | `data/biomarker/biomarker_concept_by_site.csv` | ✅ |
| 바이오마커 unit 정보 | `data/biomarker/biomarker_units_by_site.csv` | ✅ |
| 기관 4종 ID 매핑 | `data/site_mapping/site_id_mapping_full.csv` | ✅ 23기관 |
| PRESET FA 목록 | `data/atlas_reference/atlas_preset_fa_list.csv` | ✅ 105개 |
| API 엔드포인트 | `data/atlas_reference/atlas_webapi_endpoints_full.csv` | ✅ 70+ |
| 코호트 네이밍 v2 | `data/atlas_reference/cohort_naming_v2.csv` | ✅ 33 outcomes |
| 코호트 정의 JSON | `data/cohort_definitions/` (10 files) | ✅ |
| Python 생성 스크립트 | `data/scripts/` (5 files) | ✅ |
| R 분석 참고 스크립트 | `R/reference_scripts/` (20 files) | ✅ |

### 이전 분석 결과 (참고용)

| 분석 | 상태 |
|------|:---:|
| 14-site v7b/bio/NC + calibration | ✅ |
| 10-site 민감도 분석 | ✅ |
| 7-site v7b/bio/NC + calibration | ✅ |
| IPD baseline (7-site) | ✅ |

---

## TODO

- [x] 기관별 데이터 검증 → 13개 기관 확정
- [x] Outcome 코호트 v2 확정 (clinical 2 + biomarker 7 수정)
- [x] feedernet estimation v2 설계 + 실행 트리거
- [x] 23기관 × 5 domain Achilles 수집 완료
- [x] API 엔드포인트 치트시트 정리
- [x] 기관 4종 ID 매핑 완성
- [x] client.py concept 검증 메서드 추가
- [x] 참조 데이터 `data/`로 통합 정리
- [ ] **13-site estimation final 완료 대기 (11018, 11019)**
- [ ] 결과 다운로드 + CmData 추출
- [ ] 13-site IPD 분석 (v7b + bio + NC + calibration)
- [ ] 13-site time-window HR
- [ ] IPD baseline characteristics (13-site)
- [ ] KM curves 생성
- [ ] Characterization 결과 → Table 5 (weighted mean ± pooled SD)
- [ ] STROCSS 형식으로 논문 재정리
- [ ] IRB 확인
- [ ] Research Registry 등록
- [ ] Cover letter 작성
- [ ] 공저자 확정
- [ ] Cloud monitor scheduler 정리 (전체 완료 후)
