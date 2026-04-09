# atlas-auto 프로젝트 진행 상황

**repo**: https://github.com/ZellKim/atlas_auto_ms
**최종 업데이트**: 2026-04-09

---

## 전체 파이프라인 목표

```
연구설계 YAML → 코호트 JSON → ATLAS 업로드 → Estimation 실행 → 결과 다운로드 → IPD Pooled Analysis
├─────────────────── Python (atlas-auto) ───────────────────┤  ├──── R ────┤
```

---

## 1. Python 패키지 (완료, push됨)

### src/atlas_auto/

| 모듈 | 상태 | 역할 |
|------|:----:|------|
| `client.py` | ✅ 완료 | feedernet 포탈 로그인 + 기관별 WebAPI 클라이언트 |
| `builder.py` | ✅ 완료 | Estimation JSON 스펙 빌더 (TCO, PS, Cox 설정) |
| `cohort_designer.py` | ✅ 완료 | YAML 코호트 정의 → ATLAS CIRCE JSON 자동 변환 |
| `protocol.py` | ✅ 완료 | StudyProtocol: YAML 하나로 전체 파이프라인 오케스트레이션 |
| `runner.py` | ✅ 완료 | 본원(R 직접실행) + 타기관(API) 통합 실행 |
| `cli.py` | ✅ 완료 | CLI: protocol, run, status, download, concepts |
| `data/concepts.py` | ✅ 완료 | OMOP Concept ID 레퍼런스 (300+ concepts) |

### 지원 기능

- feedernet 포탈 로그인 (이메일/PW, 쿠키, Bearer 토큰)
- 기관 ATLAS 연결 (group_id/site_id 또는 URL 파싱)
- 코호트 CRUD + Generate + 완료 대기
- Estimation Import + 실행 + 완료 대기 + 결과 다운로드
- 포탈 프로젝트/Analysis 실행 트리거 + 상태 모니터링
- 다기관 result.zip 일괄 다운로드
- YAML 연구설계 → 코호트 JSON 자동 생성 (5가지 domain 지원)
- dry run 모드 (JSON만 생성, ATLAS 실행 안 함)

---

## 2. R 코드 (수정 필요)

### 현재 상태

| 파일 | 상태 | 문제 |
|------|:----:|------|
| `R/pooled_analysis.R` | ❌ 잘못됨 | meta-analysis(DL/Bayesian)로 작성. IPD pooled가 아님 |
| `R/run_pooled.R` | ❌ 잘못됨 | 위와 동일 |
| `R/install_dependencies.R` | ⚠️ 부분 | survival, MatchIt 등 IPD용 패키지 누락 |

### 필요한 IPD Pooled Analysis 워크플로우

```
1. 각 기관 result.zip에서 환자 개별 데이터 추출
   - StudyPop*.rds (subjectId, treatment, survivalTime, outcomeCount)
   - Ps*.rds (subjectId, propensityScore, preferenceScore)
   - CmData*.zip (전체 공변량 SQLite) — PS 재추정 시 필요

2. 전체 기관 데이터 합침
   - rbind로 환자 데이터 통합
   - site 변수 추가 (기관 식별)

3. PS 재추정 & 재매칭
   - site 포함하여 PS 재추정
   - 기관별로 재매칭 (1:1 또는 1:N)

4. Cox regression
   - site-stratified Cox regression (strata = site)
   - 또는 site를 공변량으로 포함

5. 결과 산출
   - Hazard ratio + 95% CI
   - Kaplan-Meier 곡선
   - Forest plot (기관별 + pooled)
```

### result.zip 내 환자수준 데이터 구조 (확인됨)

```
result.zip/script/extras/result/cmOutput/
├── CmData_l1_t1072_c1074.zip      # 환자별 공변량 (SQLite)
├── CmData_l1_t1072_c1076.zip
├── CmData_l1_t1072_c1121.zip
├── StudyPop_l1_t1072_c1074_*.rds   # 환자별 생존 데이터 (33개)
├── Ps_l1_t1072_c1074_*.rds         # 환자별 PS (36개)
├── StratPop_l1_t1072_c1074_*.rds   # PS 층화 데이터 (33개)
└── om_*.rds                        # 결과 모델 (193개)
```

| 파일 | 컬럼 | 용도 |
|------|------|------|
| StudyPop*.rds | subjectId, treatment, survivalTime, outcomeCount, timeAtRisk | 생존 데이터 풀링 |
| Ps*.rds | subjectId, propensityScore, preferenceScore, treatment | 재매칭용 PS |
| StratPop*.rds | StudyPop + stratumId | 이미 층화된 데이터 |
| CmData*.zip | 전체 환자별 공변량 (SQLite) | PS 재추정 |

### 기존 R 코드

- 로컬에 IPD pooled analysis R 코드가 작성되어 있으나 구글드라이브에 동기화 안 됨
- 찾아서 올리거나 새로 작성 필요

---

## 3. 예제 & 문서 (완료, push됨)

| 파일 | 상태 |
|------|:----:|
| `examples/study_protocol_example.yaml` | ✅ 연구설계 YAML 템플릿 |
| `examples/config_example.yaml` | ✅ 인증/DB 설정 템플릿 |
| `examples/quick_start.py` | ✅ 단계별 예제 |
| `examples/new_study_from_scratch.py` | ✅ 새 연구 설계 예제 |
| `examples/download_results.py` | ✅ 결과 다운로드 예제 |
| `README.md` | ✅ 전체 사용 문서 |
| `.gitignore` | ✅ credentials, 대용량 파일 제외 |
| `pyproject.toml` | ✅ pip install 지원 |

---

## 4. git에 포함되지 않는 것 (.gitignore)

| 폴더 | 이유 |
|------|------|
| `automation/` | 레거시 스크립트, 하드코딩된 credentials (비밀번호 평문) |
| `results/` | 대용량 result.zip (수백 MB) |
| `estimation_model/` | 기존 R 패키지 (E01_E04_clinical_ms_v6_nomatch) |
| `tool_package/` | 참고용 Data2Evidence 패키지 |
| `config.yaml` | feedernet 비밀번호 포함 |

---

## 5. 다른 환경에서 사용법

```bash
# Python 패키지 설치
pip install git+https://github.com/ZellKim/atlas_auto_ms.git

# config.yaml 작성 (feedernet 인증 정보)
# my_study.yaml 작성 (연구설계)

# 실행
atlas-auto protocol --study my_study.yaml --config config.yaml

# R pooled analysis (TODO: IPD 방식으로 재작성 필요)
Rscript R/run_pooled.R ./results
```

---

## TODO

- [ ] `R/pooled_analysis.R`를 IPD pooled analysis로 재작성
  - [ ] result.zip에서 StudyPop/Ps/CmData 추출
  - [ ] 다기관 환자 데이터 합침 + site 변수
  - [ ] PS 재추정 & 재매칭
  - [ ] Site-stratified Cox regression
  - [ ] Kaplan-Meier + Forest plot
- [ ] 로컬에 있는 기존 IPD pooled R 코드 찾아서 반영
- [ ] `R/install_dependencies.R`에 survival, MatchIt 등 추가
- [ ] README.md의 R 섹션을 IPD pooled analysis로 수정
