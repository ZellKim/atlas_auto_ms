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

## 진행 중인 작업

### Estimation 실행

| Analysis | 상태 | 비고 |
|----------|------|------|
| 10957 (v7b_noStop) | 16 COMPLETE, 2 RUNNING, 5 FAILED | SCHBC/KHMC 대기 중 |
| 10961 (biomarker_v1) | 17 COMPLETE, 5 RUNNING, 5 FAILED | EUMC/KHMC 등 대기 |

### IPD Pooled Analysis (로컬 R)

| 분석 | 상태 |
|------|------|
| 14-site v7b (1:1) | ✅ 완료 |
| 14-site biomarker (1:1) | ✅ 완료 |
| 14-site NC + calibration | ✅ 완료 |
| 10-site v7b (민감도) | ✅ 완료 (199 HR) |
| 10-site biomarker (민감도) | 🔄 실행 중 |
| 10-site NC + calibration | ⏳ bio 완료 후 |

### 17bio Characterization (14개 기관)

85 FAs (17 biomarker × 5 time window). 7/14 완료, 6 실행 중, 1 실패 (JCMJ).

---

## 확정된 결과 (14-site, 1:1 matching, calibration 후)

### Clinical — 유의한 결과

| Comparison | Outcome | HR | cal p |
|------------|---------|---:|------:|
| vs Chol | T2DM | 0.711 | 0.021 |
| vs GenPop | Biliary calculus | 1.629 | 0.016 |
| vs Hernia | Acute MI | 0.480 | 0.017 |

### Biomarker — vs Hernia 유의한 결과

| Biomarker | HR | cal p | 방향 |
|-----------|---:|------:|:----:|
| WBC | 0.603 | <0.001 | 감소 |
| Neutrophils | 0.542 | <0.001 | 감소 |
| Lymphocytes | 0.441 | <0.001 | 감소 |
| Monocytes | 1.450 | 0.018 | 증가 |
| Basophils | 1.457 | 0.028 | 증가 |
| CRP | 0.796 | <0.001 | 감소 |
| Glucose preDM | 0.740 | <0.001 | 감소 |
| Albumin | 1.697 | <0.001 | 증가 |

---

## TODO

- [ ] 10-site 민감도 분석 완료 (bio + NC + calibration)
- [ ] 10-site vs 14-site 비교 → 최종 기관 수 결정
- [ ] 17bio Characterization 결과 수집 (14개 기관)
- [ ] 추가 기관 완료 대기 (EUMC, KHMC, SCHBC)
- [ ] Table 1 생성 (baseline characteristics)
- [ ] Figure 2 (time-window HR plot), Figure 3 (NC calibration plot)
- [ ] Characterization 결과 → Table 5 (weighted mean ± pooled SD)
- [ ] STROCSS 형식으로 논문 재정리
- [ ] IRB 확인
- [ ] Research Registry 등록
- [ ] Cover letter 작성
- [ ] 공저자 확정
- [ ] Cloud monitor scheduler 정리 (전체 완료 후)
