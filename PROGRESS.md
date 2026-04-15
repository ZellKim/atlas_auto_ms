# 프로젝트 진행 상황

**repo**: https://github.com/ZellKim/atlas_auto_ms
**최종 업데이트**: 2026-04-15

> 상세 지식(API, 방법론, 이슈 해결, 기관 매핑, 실행 기록)은 → `docs/system_knowledge_base.md`

---

## 현재 상태

### Python 패키지 (`src/atlas_auto/`) — 완료

| 모듈 | 역할 |
|------|------|
| `client.py` | feedernet 포탈 + WebAPI 클라이언트 |
| `builder.py` | Estimation JSON 스펙 빌더 (TCO, PS, covariates) |
| `cohort_designer.py` | YAML → ATLAS CIRCE JSON |
| `protocol.py` | 전체 파이프라인 오케스트레이션 |
| `runner.py` | 본원(R) + 타기관(API) 통합 실행 |
| `cli.py` | CLI: protocol, run, status, download, concepts |

### Cloud 모니터링 (`cloud_monitor/`) — 배포됨

GCP Cloud Function + Scheduler → Telegram 알림. Project: `investment-os-chain`, Region: `us-east1`.

### R 분석 (`R/pooled_analysis/`) — 통합 완료

IPD pooled analysis 파이프라인 10개 파일. Cyclops PS + 1:1 matching + site-stratified Cox.

---

## 확정: 13개 기관 (2026-04-15 재확정)

AUMC, CHNUH, DCMC, GNUCH, HUMC, ISH, JCMJ, KDH, KHNMC, KWMC, SCHCA, SCHGM, SCHSU
— multi-concept OR 코호트 + Achilles 재수집 후 17개 바이오마커 전부 가용.
GNUH만 CRP 누락으로 제외 (1개 기관).

### IPD Pooled Analysis

| 분석 | 14-site | 10-site | **7-site** |
|------|---------|---------|-----------|
| v7b (clinical) | ✅ | ✅ | ✅ |
| biomarker | ✅ | ✅ | ✅ |
| NC + calibration | ✅ | ✅ | ✅ |

### Characterization (PRESET × 5구간)

7개 기관 × 5구간 = 35개 Characterization 완료. 결과: `char_preset_all_results.csv`

---

## 확정된 결과 (7-site, 1:1 matching, calibration 후)

**Primary comparators: vs Chol, vs Hernia. vs GenPop은 supplementary** (maxCohortSize=50K capping + NC bias 심함).

### Clinical — 유의한 결과 (primary)

| Comparison | Outcome | HR | cal p |
|------------|---------|---:|------:|
| vs Chol | Biliary calculus | 0.729 | 0.003 |
| vs Chol | T2DM | 0.689 | 0.041 |
| vs Hernia | Biliary calculus | 1.984 | 0.007 |

### Biomarker — vs Hernia 유의한 결과

| Biomarker | HR | cal p | 방향 |
|-----------|---:|------:|:----:|
| WBC | 0.600 | <0.001 | 감소 |
| Neutrophils | 0.475 | <0.001 | 감소 |
| Lymphocytes | 0.409 | <0.001 | 감소 |
| CRP | 0.674 | <0.001 | 감소 |
| GlucPreDM | 0.774 | 0.032 | 감소 |
| Albumin | 1.527 | <0.001 | 증가 |

### Baseline Characteristics (pre-matching)

| | Appendectomy | Cholecystectomy | Hernia Repair |
|--|--:|--:|--:|
| N | 16,013 | 27,244 | 8,966 |
| Female (%) | 8,319 (52.0%) | 13,744 (50.4%) | 2,727 (30.4%) |
| Mean age | ~47 | ~56 | ~62 |

---

## TODO

- [x] 기관별 데이터 검증 → 7개 → Achilles 재수집 + multi-concept OR → **13개 기관 재확정**
- [x] 7-site v7b + bio + NC + calibration 완료 (참고용)
- [x] Outcome 코호트 v2 확정 (clinical 수정 2건 + biomarker 수정 7건)
- [ ] **feedernet estimation v2 재설계 + 13개 기관 실행**
- [ ] 13-site v7b + bio + NC + calibration
- [ ] Table 1 생성 (baseline characteristics)
- [ ] Figure 2 (time-window HR plot), Figure 3 (NC calibration plot)
- [ ] Characterization 결과 → Table 5 (weighted mean ± pooled SD)
- [ ] STROCSS 형식으로 논문 재정리
- [ ] IRB 확인
- [ ] Research Registry 등록
- [ ] Cover letter 작성
- [ ] 공저자 확정
- [ ] Cloud monitor scheduler 정리
