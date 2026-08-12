# Estimation Negative Control 필수 검증 설계

- 작성일: 2026-08-12
- 상태: 사용자 승인 완료
- 적용 범위: 이 저장소에서 설계·생성·수정·반입·실행하는 모든 Estimation
- 정책: Negative Control(NC)이 없는 Estimation은 허용하지 않는다.

## 1. 목적

모든 Estimation에서 NC를 선택 사항이 아닌 필수 설계 요소로 강제한다. NC concept set을 실제로 정하지 않았거나, 최종 ATLAS export에서 유효 NC가 0개인 Estimation은 Feedernet에 반입하거나 실행하지 못하게 한다.

2026-08-12 `fracture_treatment` v1.9 실패에서는 빈 NC placeholder concept set과 형식상 유효한 cross-reference가 있었지만 최종 `negativeControls`가 비어 있었다. WebAPI `/estimation/check`는 경고를 내지 않았고, 생성된 연구 패키지는 빈 `outcome_ids`를 SQL `IN ()`으로 렌더링했다. 따라서 concept set ID나 cross-reference의 존재만으로 NC 준비 완료를 판정하면 안 된다.

## 2. 확정 정책

1. 모든 Estimation은 NC outcome cohort definition을 가진다.
2. 모든 Estimation은 실제 NC concept set을 명시적으로 선택한다.
3. NC concept set은 `negativeControlOutcomes` cross-reference와 일관되어야 한다.
4. 아직 해석되지 않은 빈 placeholder는 유효한 NC로 간주하지 않는다.
5. Feedernet 반입 직전의 ATLAS `/estimation/{id}/export`에는 유효한 `negativeControls`가 1개 이상 있어야 한다.
6. `/estimation/check` 경고 0건은 위 검증을 대체하지 않는다.
7. 의도적인 no-NC 모드는 두지 않는다.
8. 하나라도 충족하지 않으면 fail-closed로 생성·수정·반입·실행을 중단한다.

## 3. 실패가 누락된 이유

기존 구현과 테스트는 다음 세 상태를 잘못 같은 것으로 취급했다.

- ATLAS가 나중에 해석할 수 있는 concept set 표현
- ID와 cross-reference만 있고 실제 내용은 없는 placeholder
- 최종 연구 패키지에 포함된 실제 NC outcome 목록

`fracture_treatment` v1.4.1에서 빈 placeholder 패턴을 도입했고, v1.6.1과 v1.8이 이를 반복했으며, v1.9은 v1.8 Estimation을 복사하면서 그대로 상속했다. 기존 semantic contract는 `negative_controls == 0`을 정상 기대값으로 기록했고 concept set 내용과 cross-reference의 참조 무결성을 검사하지 않았다. 배포 후 실행한 `/estimation/check`도 이 오류를 탐지하지 못했다.

## 4. 선택한 구조

문서 경고나 연구별 검사만으로 끝내지 않고 공통 검증기와 배포 직전 검증을 함께 둔다.

### 4.1 공통 검증 모듈

새 canonical 모듈 `src/atlas_auto/estimation_validation.py`를 둔다.

- `EstimationValidationError`: 위반 항목과 수정 방향을 함께 제공하는 예외
- `validate_estimation_design(spec)`: 작성·생성·수정 전에 수행하는 설계 검증
- `validate_estimation_export(spec)`: Feedernet 반입 전에 수행하는 최종 export 검증

검증 함수는 네트워크나 파일 쓰기를 하지 않는 순수 함수로 만든다. 호출자가 가진 JSON만 검사하며, 성공하면 검증 결과를 반환하고 실패하면 `EstimationValidationError`를 발생시킨다. 검증 결과에는 참조된 NC concept set ID, effective NC 수, TCO별 NC 수와 검증한 export의 식별 정보를 포함해 배포 기록과 다음 단계의 검증 증명으로 사용할 수 있게 한다.

### 4.2 설계 단계 검증

`validate_estimation_design()`은 다음을 모두 요구한다.

- `negativeControlOutcomeCohortDefinition`이 존재하고 비어 있지 않다.
- `targetName == "negativeControlOutcomes"`인 cross-reference가 1개 이상 있다.
- 각 cross-reference의 `propertyName`은 `outcomeId`이다.
- 각 `conceptSetId`가 같은 spec의 `conceptSets`에 존재한다.
- 각 `targetIndex`가 target-comparator-outcome 분석 목록 범위 안에 있다.
- 참조된 NC concept set의 실제 expression item이 1개 이상이거나, 이미 해석된 `negativeControls`가 1개 이상이다.
- 중복되거나 식별자가 없는 NC 참조는 허용하지 않는다.

concept set ID만 있고 expression이 빈 상태는 “해석 대기”가 아니라 검증 실패로 처리한다. live ATLAS concept set을 사용한다면 호출자가 먼저 expression을 조회해 spec에 반영하거나, 이미 해석된 export를 입력해야 한다. 추측으로 통과시키지 않는다.

### 4.3 최종 export 검증

`validate_estimation_export()`은 설계 참조 무결성을 검사한 뒤 다음을 추가로 요구한다.

- `negativeControls`가 1개 이상이다.
- 모든 TCO index가 NC cross-reference로 포함된다.
- 각 NC 항목의 `targetId`, `comparatorId`가 실제 TCO 한 쌍과 일치한다.
- 각 TCO 쌍마다 일치하는 NC 항목이 1개 이상이다.
- 각 NC 항목의 `outcomeId`가 양의 정수이다.
- 같은 `(targetId, comparatorId, outcomeId)` 조합은 중복되지 않는다. 같은 NC outcome을 서로 다른 TCO 쌍에 사용하는 것은 허용한다.
- NC cross-reference와 concept set 참조가 끊어지지 않았다.

ATLAS export의 `conceptSets[].expression.items`가 비어 있어도 `negativeControls`가 실제로 해석되어 1개 이상이면 허용한다. 반대로 concept set ID와 cross-reference가 있어도 `negativeControls == []`이면 최종 export 검증은 반드시 실패한다.

## 5. 적용 지점과 데이터 흐름

```text
NC concept set 선택
  -> Estimation JSON 작성
  -> validate_estimation_design
  -> ATLAS create/copy+PUT
  -> GET /estimation/{id}/export
  -> validate_estimation_export
  -> Feedernet import/create analysis
  -> execution
```

적용 지점은 다음과 같다.

1. `EstimationBuilder.build()`와 `save()`에서 설계 검증을 수행한다.
2. `FedernetClient.create_estimation()`은 ATLAS HTTP POST 전에 설계 검증을 수행한다.
3. canonical `update_estimation()`을 추가해 ATLAS HTTP PUT 전에 설계 검증을 수행한다.
4. `FedernetClient.import_estimation()`은 **ATLAS `/estimation/import`** 경로이므로 HTTP POST 전에 최종 export 검증을 수행한다. 이를 Feedernet portal import와 혼동하지 않는다.
5. 검증까지 한 번에 수행하는 `get_validated_estimation_export(estimation_id)`를 제공하고, 이후 배포 단계에는 이 함수가 반환한 검증 결과와 export를 함께 전달한다.
6. 현재 direct copy+PUT을 사용하는 활성 배포 스크립트는 canonical update 경로 또는 공통 검증기를 사용하도록 바꾼다.
7. Feedernet portal의 analysis 생성 및 ATLAS research import orchestration은 먼저 위 검증된 export를 받아야 한다. 검증 전에는 portal analysis도 생성하지 않는다.
8. `run_analysis_execution(..., execution_type="ESTIMATION")`은 같은 Estimation에 대한 최종 export 검증 결과를 필수로 받고, 검증된 Estimation 식별 정보와 실행 대상이 일치하지 않으면 POST 전에 실패한다. 다른 execution type에는 이 조건을 적용하지 않는다.

검증 실패 뒤에는 POST, PUT, Feedernet import, analysis 생성 또는 execution 요청이 한 번도 발생하지 않아야 한다. 단순 조회와 오류 기록만 허용한다.

## 6. 오류 처리

오류 메시지는 최소한 다음 정보를 포함한다.

- 실패 단계: `design` 또는 `export`
- Estimation 이름 또는 ID(있을 때)
- 누락·오류 필드
- 참조된 concept set ID
- 확인된 effective NC 수
- 다음 조치: NC concept set 선택/해석 후 다시 export

비밀번호, cookie, Authorization header, 전체 임상 concept payload는 오류나 로그에 남기지 않는다.

## 7. 테스트 전략

구현 전에 실패하는 테스트를 먼저 추가한다.

### 공통 검증 단위 테스트

- 기본 `EstimationBuilder`처럼 NC definition만 있고 NC 참조가 없는 spec은 실패한다.
- NC 설정 자체가 없는 spec도 실패한다.
- 빈 concept set과 cross-reference만 있는 기존 placeholder 패턴은 실패한다.
- 존재하지 않는 `conceptSetId`를 가리키면 실패한다.
- 범위를 벗어난 `targetIndex`이면 실패한다.
- 최종 export의 `negativeControls == []`이면 실패한다.
- 일부 TCO에 NC cross-reference나 일치하는 effective NC가 없으면 실패한다.
- NC의 target/comparator가 TCO와 다르거나 `outcomeId`가 유효한 양의 정수가 아니면 실패한다.
- 같은 TCO 안에서 같은 NC outcome이 중복되면 실패한다.
- 실제 NC concept items가 있는 설계 spec은 통과한다.
- concept items가 비어 있어도 최종 export에 유효한 `negativeControls`가 있으면 통과한다.

### 변경 차단 테스트

- 잘못된 spec을 `create_estimation()`, `update_estimation()`, `import_estimation()`에 전달하면 fake session의 POST/PUT 호출 수가 0인지 확인한다.
- `EstimationBuilder.build()`와 `save()`가 잘못된 spec을 반환하거나 저장하지 않는지 확인한다.
- 검증되지 않은 Estimation으로 Feedernet portal analysis 생성·import 또는 ESTIMATION execution을 요청하면 portal POST 호출 수가 0인지 확인한다.
- 검증 결과와 실행 대상 Estimation의 식별 정보가 다르면 portal POST 호출 수가 0인지 확인한다.

### 연구 회귀 테스트

- `fracture_treatment` v1.9의 #524 빈 placeholder 구조를 fixture로 사용해 반드시 실패하는지 확인한다.
- 기존 테스트의 `negative_controls == 0` 정상 기대값을 제거한다.
- 실제로 NC가 채워진 기존 성공 export fixture는 통과하는지 확인한다.

## 8. 기록 위치

중복 문서를 새로 만들지 않고 기존 정본을 갱신한다.

- `docs/system_knowledge_base.md`: 2026-08-12 empty-NC 사고, `/estimation/check`의 한계, 최종 export NC 필수 규칙
- `docs/new_study_topic_to_estimation_protocol.md`: Phase 9와 Gate C의 mandatory effective-NC preflight
- `studies/fracture_treatment/PROGRESS.md`: #291/#292, analyses #11859/#11860, groups #147880/#147881의 실패와 현재 remediation 상태
- `studies/fracture_treatment/study_knowledge_base.md`: #524 placeholder 재사용 금지와 replacement Estimation의 필수 검증 규칙

`docs/estimation_output_template.md`는 결과 작성용 문서이므로 Estimation 생성 차단 규칙을 중복 기록하지 않는다. 기존 `CLAUDE.md`가 신규 연구 프로토콜과 시스템 KB를 이미 필수 라우팅하므로 새 trigger도 추가하지 않는다.

## 9. 기존 자산 처리

- 과거 빈 NC JSON과 실행 기록은 사고 증거이므로 삭제하거나 사후 수정하지 않는다.
- #291/#292와 그 export는 유효한 분석 설계로 재사용하지 않는다.
- 현재 v1.9 분석은 결과 해석이나 재실행 대상으로 간주하지 않는다.
- 임상적으로 적절한 NC concept set을 별도로 확정한 뒤 새 Estimation을 만들고 두 단계 검증을 모두 통과시킨다.
- 이 guardrail 구현 과정에서는 live ATLAS/Feedernet 자산을 생성·수정·삭제하거나 분석을 재실행하지 않는다.

## 10. 완료 기준

1. 모든 canonical Estimation 생성·수정·ATLAS 반입 및 Feedernet portal 배포·실행 경로가 공통 검증기를 호출한다.
2. 빈 NC placeholder spec이 첫 HTTP 쓰기 전에 차단된다.
3. 최종 export의 effective NC가 0이면 Feedernet 반입 전에 차단된다.
4. 유효 NC가 있는 알려진 성공 export는 통과한다.
5. `fracture_treatment` 회귀 테스트가 이번 v1.9 구조를 재현하고 차단한다.
6. 시스템·워크플로·연구 기록이 같은 정책과 사실을 가리킨다.
7. targeted pytest와 관련 전체 테스트가 통과한다.

## 11. 범위 제외

- 실제 NC concept set의 임상 개념 선정
- #291/#292의 현장 수정 또는 삭제
- replacement Estimation 배포와 Feedernet 재실행
- 과거 실행 산출물의 일괄 재작성

위 작업은 guardrail이 검증된 뒤 별도 설계·승인을 거쳐 수행한다.
