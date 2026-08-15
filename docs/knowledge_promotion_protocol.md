# 지식 승격 프로토콜 (Knowledge Promotion)

수립 2026-08-15. 트리거·적용은 `CLAUDE.md` 프로토콜 표 참조.

## 이 문서가 생긴 이유

2026-08-15 감사에서 측정된 사실:

- `studies/fracture_treatment/study_knowledge_base.md`는 1,017줄이고, 그 중
  8/13-8/15에 확립된 WebAPI 계약 발견이 재사용 가치가 가장 높았다.
- 그 중 `isValid` / `thresholdLevel` / `countSatisfying` / `treemapData` /
  `analysisName` / member order / 2026-08-14 / 2026-08-15 — **8개 검색어 전부**가
  `docs/system_knowledge_base.md`에 없었다.
- 동시에 `isValid`는 `src/` 전체에 **0회**, fracture_treatment 스크립트에는
  **18개 파일**에 손으로 타이핑돼 있었다. 공유 `wait_for_cohort_generation`은
  `status == "COMPLETE"`만 보고 `source_key` 인자를 받아놓고 쓰지 않았다.
- appendectomy가 2026-05에 확인한 "import는 site마다 cohort id를 새로 배정한다"를
  fracture_treatment가 2026-08에 다시 발견해 자기 KB에 적었다.

즉 **지식은 산문에 있고 게이트는 코드에 없었다.** 산문은 연구 폴더에 갇히고,
코드는 가드가 없어서, 신규 연구는 매번 처음부터 다시 밟았다.

## 원칙

> 연구 중립적 사실은 **코드로 강제**하고, 그 다음 시스템 문서에 등재한다.
> 연구별 임상 판단만 study KB에 남긴다.

문서를 먼저 늘리지 말 것. 표만 길어지고 다음 세션이 또 안 읽는다.

## 분류 기준

| 성격 | 판별 질문 | 귀속 |
|---|---|---|
| 계약 (contract) | 다른 연구·다른 기관에서도 참인가? | `src/atlas_auto/` 함수 + 테스트 → `system_knowledge_base.md` |
| 운영 (operational) | 도구 사용 순서·경로 문제인가? | `system_knowledge_base.md` §2/§7 |
| 임상 (clinical) | 이 연구의 설계 판단인가? | `studies/{연구}/study_knowledge_base.md` |
| 사건 (incident) | 특정 실행의 증거인가? | `studies/{연구}/PROGRESS.md` + 버전 폴더 |

경계 사례는 계약으로 취급한다. 잘못 승격한 비용(문서 한 줄)이 승격 누락 비용
(다음 연구가 며칠 날림)보다 훨씬 싸다.

## 승격 절차

1. **테스트 먼저.** 함정을 재현하는 실패 테스트를 `tests/`에 쓴다. 버전 스크립트
   테스트(`tests/{연구}/test_*_v1_N.py`)가 아니라 계약 테스트여야 한다.
   버전 스크립트가 죽으면 그 테스트도 같이 죽고 다음 연구에 아무것도 안 남는다.
2. **가드를 `src/atlas_auto/`에 넣는다.** 기존 모듈에 맞으면 거기에,
   새 관심사면 새 모듈로. fail-closed가 기본이다. `logger.warning` 후 잘못된 값을
   반환하는 코드는 가드가 아니다.
3. **`__init__.py`에 export.** 공개 표면에 없는 헬퍼는 소스를 이미 읽은 사람만
   찾는다. `tests/test_public_surface.py`가 이를 강제한다.
4. **`system_knowledge_base.md` §1.4 함정표에 한 줄** — 함정 + **강제 함수명**.
   함수명 없는 행은 "기억해라"이고, 그게 실패한 방식이다.
5. **study KB 항목을 축약**하고 시스템 문서·함수를 가리키게 한다. 임상적 맥락과
   실측값(날짜, N, 기관)은 남긴다. 계약 서술만 옮긴다.
6. **배포 사본 동기화.** `studies/*/portable_assets/scripts/`에 공유 모듈 사본이
   있으면 `python data/scripts/sync_vendored_modules.py`를 돌린다.
   `tests/test_vendored_modules.py`가 drift를 잡는다.

## 승격하면 안 되는 것

- 아직 한 번만 관측된 것. "재현 가능"이 조건이다. 관측 1회는 study KB에 사건으로.
- 서버 측 로그 없이 귀속한 실패 원인. 근거 없는 인과는 승격 대상이 아니다.
- 특정 기관에서만 참인 사실 — 예: `condition_occurrence.visit_occurrence_id`가
  KHNMC에서 비어 있다. 이건 "기관마다 확인하라"는 형태로만 승격한다.
- 임상 판단 (grace period 일수, 아웃컴 정의, 제외 기준).

## 승격 시점

- 연구 버전을 닫을 때 (v1.N 완료 보고 직후)
- 같은 함정을 두 번째 밟았을 때 — 즉시. 두 번은 우연이 아니다.
- 다른 연구 KB에서 이미 본 적 있는 사실을 재발견했을 때 — 즉시.

## 등재 이력

| 날짜 | 승격 항목 | 강제 위치 |
|---|---|---|
| 2026-08-15 | `COMPLETE` 단독은 성공 아님 (`isValid` + `id.sourceId`) | `generation_safety.assert_generation_valid`, `client.wait_for_cohort_generation` |
| 2026-08-15 | Characterization 결과 `thresholdLevel` 무음 절단 | `client.get_characterization_results` 기본 0, `CharacterizationService.collect_results` raise, `characterization_safety.fetch_results` |
| 2026-08-15 | `countSatisfying` 체이닝 금지, `treemapData` 비트열 | `attrition.cumulative_attrition` |
| 2026-08-15 | 배포 사본 drift | `data/scripts/sync_vendored_modules.py`, `tests/test_vendored_modules.py` |
| 2026-08-15 | export DTO = portable, read DTO ≠ portable | `system_knowledge_base.md` §1.4 (문서만; 호출부 선택 문제) |
| 2026-08-15 | import는 expression으로 resolve, id/name 아님 | `system_knowledge_base.md` §1.4 (문서만) |
| 2026-08-15 | readback member order 불보장 | `characterization_safety.assert_membership` |
| 2026-08-15 | PRESET `design`은 이름, 결과 행은 `analysisName`으로 매칭 | `characterization_safety.preset_name`, `counts_by_analysis` |
| 2026-08-15 | empty `design` read는 손상 아님 | `characterization_safety.design_of` |
| 2026-08-15 | `Path.write_text` CRLF → digest 불일치 | `study_runner.write_evidence` (파일 바이트 digest 반환), `system_knowledge_base.md` §1.4 |
| 2026-08-15 | deploy→inspect→trigger→monitor 필수 순서 | `study_runner.StudyRun.record` / `assert_ready_to_trigger` |
| 2026-08-15 | create 응답 유실 시 blind retry = 서버 객체 중복 | `study_runner.StudyRun.creating` / `assert_no_uncertain_create` |
| 2026-08-15 | live 정의가 prepared와 달라진 채 실행 | `study_runner.StudyRun.assert_definition_unchanged` |
| 2026-08-16 | feature 행은 코호트 분할이 아님 (중복 membership) | `characterization_safety.membership_overlap` |

**2026-08-16 승격 사례 — 이 프로토콜이 작동한 첫 건.**
"feature 행은 분할이 아니다"는 이미 알려져 있었고 `build_khnmc_v1_15_persistence_by_drug.py`에
`sum >= denominator` 가드까지 있었다. 그런데 그 가드가 **한 버전 스크립트에만** 살아서,
다기관 배포 경로(AUMC)가 타지 않았고 중복이 2건에서 24건으로 12배 커진 것을 아무도
못 봤다. 산문(v1.15 VALIDATION.md)과 코드(한 스크립트)에 둘 다 있었는데도 재발했다 —
**공유 표면에 없으면 없는 것과 같다.** 절차 §2 "같은 함정 2회 = 즉시 승격"이
정확히 이 경우다.
