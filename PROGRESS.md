# 프로젝트 진행 상황

**repo**: https://github.com/ZellKim/atlas_auto_ms
**최종 업데이트**: 2026-04-15

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
MONITOR_TARGETS: 11000, 11001, 11003, 11004 (4개 analysis)

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

## 진행 중: Estimation v2 실행

| Analysis | ID | 내용 | 상태 |
|----------|:---:|------|:---:|
| clinical_v8_full | 11000 | 11 clinical outcomes (전체) | 🔄 실행 중 |
| biomarker_v2_full | 11001 | 22 biomarker outcomes (전체) | 🔄 실행 중 |
| **clinical_v8_changed** | **11003** | 1270(T2DM), 1271(AMI) — 변경분만 | 🔄 실행 중 |
| **biomarker_v2_changed** | **11004** | 1262~1268 — 변경분만 | 🔄 실행 중 |

13개 기관 + EUMC/KHMC 추가. 11003/11004가 먼저 끝날 예정.

---

## 확보된 자산

### 데이터

| 데이터 | 파일 | 상태 |
|--------|------|:---:|
| Achilles 23기관 × 5 domain | `concept_frequency/{기관}_{domain}.csv` | ✅ |
| Characterization (PRESET 5구간) | `char_preset_all_results.csv` | ✅ 13기관 |
| 바이오마커 concept 매핑 | `biomarker_concept_by_site.csv` | ✅ |
| 기관 4종 ID 매핑 | `site_id_mapping_full.csv` | ✅ 23기관 |
| PRESET FA 목록 | `atlas_preset_fa_list.csv` | ✅ 105개 |
| API 엔드포인트 | `atlas_webapi_endpoints_full.csv` | ✅ 70+ |
| 코호트 네이밍 v2 | `cohort_naming_v2.csv` | ✅ 33 outcomes |
| 바이오마커 unit 정보 | 수집 중 | 🔄 |

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
- [ ] **13-site estimation v2 완료 대기**
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
