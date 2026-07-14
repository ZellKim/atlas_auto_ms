# Characterization Client 안정화 설계

- 작성일: 2026-07-14
- 상태: 사용자 승인 완료
- 대상: WebAPI 2.12 기반 Cohort Characterization / Feature Analysis 자동화
- 기준 구현: `data/scripts/create_char_v2.py`, `create_biomarker_fas_v2.py`, `deploy_char_17bio.py`, `deploy_char_multisite.py`

## 1. 목적

이미 WebAPI 2.12에서 사용한 Feature Analysis와 Cohort Characterization 자동화를 다시 구현하지 않는다. 검증된 API 호출 순서와 기관별 실패 격리를 보존하면서 다음 문제를 해결한다.

1. `data/scripts`에 흩어진 직접 `client.session` 호출을 canonical client로 이동한다.
2. 중복된 `automation/feedernet_client.py`와 `src/atlas_auto/client.py`의 구현 차이를 제거한다.
3. 단일기관 분석 lifecycle과 다기관 배포 orchestration을 HTTP client에서 분리한다.
4. 재실행 시 불필요한 FA, Characterization, generation 중복 생성을 줄인다.
5. 완료 대기와 결과 수집을 재현 가능한 코드로 남긴다.
6. API 동작을 실제 서버 쓰기 없이 자동 테스트할 수 있게 한다.

원시 HTTP 속도 개선은 목표가 아니다. 동일한 `requests.Session`을 사용하므로 단순 메서드 호출 전환만으로 네트워크 왕복 횟수는 줄지 않는다. 속도 개선은 중복 작업 방지와 중단 지점 재개에서 얻는다.

## 2. 확인된 현재 상태

- `deploy_char_17bio.py`는 17개 바이오마커와 5개 시간창에 대해 FA 85개를 `copy -> PUT -> PUT` 순서로 생성한다.
- KHNMC Characterization을 생성·실행·export한 뒤 13개 기관에 import·실행한다.
- `data/measurement/characterization/char_preset_all.csv`에 13기관, 5개 시간창의 결과 47,140개 데이터 행이 존재한다.
- 네 스크립트에는 총 23개의 직접 `session.get/post/put/delete` 호출이 있다.
- `automation/feedernet_client.py`와 `src/atlas_auto/client.py`는 별도 구현이며 canonical client에만 concept 검증 메서드 6개가 더 있다.
- canonical client에는 사용자의 미커밋 변경이 있으므로 기존 내용을 덮어쓰거나 되돌리지 않고 필요한 코드를 추가한다.
- 패키지 단위 테스트 디렉터리는 없고 `data/scripts/test_*.py` 두 개만 존재한다.

## 3. 범위

### 포함

- canonical client의 Feature Analysis / Characterization 저수준 API 메서드
- 새 메서드에 적용할 공통 WebAPI 요청 정책과 구조화된 오류
- Feature Analysis 생성·재사용·정리와 Characterization 실행·수집 서비스
- 다기관 배포·resume·기관별 ledger
- legacy client 호환 shim
- 기존 네 Characterization 스크립트의 `atlas_auto` 패키지 import 전환
- editable 설치 방법, 운영 사용법, 마이그레이션 기록
- pytest 기반 단위·계약 테스트

### 제외

- WebAPI 또는 ATLAS 서버 업그레이드
- WebAPI 2.15의 Temporal/Annual Characterization, Cohort Demographics, Concept Set Annotation
- CLI 명령 추가
- 기관 병렬 실행
- 실제 Feedernet에 대한 자동 테스트 쓰기
- 기존 Characterization 연구 설계, concept, 시간창, 기관 목록 변경

## 4. 선택한 구조

### 4.1 `FedernetClient`: HTTP 한 번의 호출

`src/atlas_auto/client.py`는 URL 구성, timeout, 응답 확인, JSON 변환만 담당한다. 연구별 FA payload 수정, 기관 반복, resume 판단은 담당하지 않는다.

추가할 Feature Analysis 메서드:

- `list_feature_analyses(size=200, analysis_type=None)`
- `get_feature_analysis(feature_analysis_id)`
- `create_feature_analysis(spec)`
- `copy_feature_analysis(feature_analysis_id)`
- `update_feature_analysis(feature_analysis_id, spec)`
- `delete_feature_analysis(feature_analysis_id)`

추가할 Characterization 메서드:

- `list_characterizations(size=200)`
- `get_characterization(characterization_id)`
- `create_characterization(spec)`
- `update_characterization(characterization_id, spec)`
- `delete_characterization(characterization_id)`
- `export_characterization(characterization_id)`
- `import_characterization(export_spec)`
- `generate_characterization(characterization_id, source_key)`
- `get_characterization_generations(characterization_id)`
- `get_characterization_result_count(generation_id)`
- `get_characterization_results(generation_id, threshold_level=0.01)`
- `delete_characterization_generation(generation_id)`

목록 응답은 WebAPI가 list를 반환하든 `{"content": [...]}` Page를 반환하든 list로 정규화한다. WebAPI 2.12의 결과 GET은 pagination을 받지 않고 전체 `List<CcResult>`를 반환하므로 `size`나 `page`를 보내지 않는다.

### 4.2 `CharacterizationService`: 단일기관 lifecycle

새 파일 `src/atlas_auto/characterization.py`에 다음 책임을 둔다.

- 정확히 같은 이름의 FA 또는 Characterization 검색
- 기존 자산 재사용 여부 결정
- FA template copy 후 1차·선택적 2차 payload 변환과 PUT
- 새 FA 처리 중 실패하면 그 실행에서 생성한 FA만 best-effort 삭제
- Characterization create 또는 import
- source별 기존 generation의 상태를 보고 재사용·대기·재실행 결정
- 완료 대기와 전체 결과 수집

FA payload 변환은 연구별 규칙을 서비스에 하드코딩하지 않는다. 서비스는 `prepare_first(copy_payload)`와 선택적 `prepare_second(first_update_response)` callable을 받아 기존 스크립트의 검증된 payload 조립 코드를 그대로 사용할 수 있게 한다.

서비스의 ensure 결과는 `EnsureResult(resource, reused)`로, generation 결정은 `GenerationResult(generation, action)`으로 표현한다. `action`은 `STARTED`, `WAITING`, `REUSED` 중 하나다.

### 4.3 `MultisiteCharacterizationDeployer`: 기관 반복과 ledger

새 파일 `src/atlas_auto/multisite_characterization.py`에 다음 책임을 둔다.

- `SiteTarget(group_id, site_id, code, name)` 입력
- 기관마다 독립적인 `FedernetClient` 생성
- 기존 규칙과 동일한 최신 static source 선택
- 기관별 Characterization 이름 지정, import, 선택적 site 준비 callback, generation 실행
- 한 기관 실패 후 다음 기관 계속 진행
- `DeploymentRecord` 목록과 JSON ledger 저장

credential 취득은 기존 원칙대로 `automation/credentials.py`를 사용하는 스크립트가 담당한다. 패키지 모듈은 credential을 import하거나 저장하지 않고 이미 로그인된 client를 만드는 `client_factory`만 받는다.

### 4.4 호환성

- 네 Characterization 스크립트는 `from atlas_auto import FedernetClient`와 새 service/deployer를 사용한다.
- 개발 환경은 `python -m pip install -e ".[dev]"`를 기준으로 한다.
- `automation/feedernet_client.py`는 canonical class를 다시 export하는 shim으로 바꾼다.
- 패키지가 아직 설치되지 않은 저장소 직접 실행도 지원하도록 shim은 저장소의 `src` 경로 fallback을 제공한다.
- 기존 `from feedernet_client import FedernetClient` 소비자는 같은 canonical class를 받는다.

## 5. 요청 및 오류 정책

새 저수준 메서드는 private 공통 요청 함수를 사용한다.

- 기본 timeout: connect 10초, read 30초
- 결과 조회: connect 10초, read 120초
- 오류에는 HTTP method, credential이 제거된 endpoint path, status, 응답 본문 앞부분만 포함
- cookie, Authorization header, 비밀번호, 전체 연구 payload는 오류와 로그에 기록하지 않음
- JSON이 필요한 성공 응답이 비어 있거나 JSON이 아니면 구조화된 client 오류 발생

재시도는 HTTP verb만 보고 판단하지 않는다. OHDSI WebAPI에는 GET이지만 상태를 변경하는 endpoint가 있기 때문이다.

안전한 조회에만 최대 2회 재시도:

- 연결 오류와 read timeout
- HTTP 429, 502, 503, 504
- 목록, 상세, export, generation 조회, result 조회

자동 재시도 금지:

- FA copy
- FA/Characterization create, update, delete, import
- Characterization generate
- cohort generate/cancel 등 기존 상태 변경 GET

POST 또는 상태 변경 GET이 timeout이면 같은 요청을 다시 보내지 않는다. service가 이름 또는 generation 목록을 다시 조회해 생성·실행 여부를 판정한다.

## 6. 재사용과 generation 상태 규칙

### 자산 이름

- 기본은 대소문자를 포함한 정확한 이름 일치다.
- 같은 이름이 여러 개면 가장 큰 numeric `id`를 선택하고 warning을 기록한다.
- `reuse_existing=False`이면 새 자산을 만든다.

### Generation

source key가 같은 최신 generation을 기준으로 판단한다.

- `COMPLETE`: 결과를 재사용하고 새 generation을 만들지 않음
- 실행 중 상태: 기존 generation을 기다림
- WebAPI 2.12의 `ERROR` 또는 호환 응답의 `FAILED`, `CANCELED`: 새 generation 시작
- generation 없음: 새 generation 시작
- `force=True`: 상태와 관계없이 새 generation 시작

상태가 문자열 또는 `{"name": "COMPLETE"}` 형태여도 동일하게 처리한다. 알 수 없는 상태는 임의로 재실행하지 않고 오류로 보고한다.

## 7. 기존 스크립트 보존 원칙

- FA 372 기반 스크립트의 `copy -> 1차 PUT -> 2차 PUT` 순서를 보존한다.
- `create_biomarker_fas_v2.py`의 단일 PUT 흐름도 그대로 지원한다.
- concept, includeDescendants, time window, cohort ID, source 선택 결과를 바꾸지 않는다.
- 기존 기관별 `try/except`와 계속 진행 의미를 deployer의 기관별 record로 보존한다.
- 현재 외부 Desktop 출력 경로는 명시적 `Path` 인자로 전달하게 하고 임의의 새 기본 위치로 옮기지 않는다.

## 8. 테스트 설계

실제 Feedernet에는 쓰지 않는다. `FakeSession`과 `FakeResponse`로 canonical client의 실제 코드를 호출한다.

`tests/test_characterization_client.py`:

- 각 메서드의 verb, path, params, timeout
- list/Page 응답 정규화
- 안전한 조회의 일시 오류 재시도
- FA copy와 Characterization generate의 재시도 금지
- 오류 메시지의 credential·payload 비노출
- 결과 count와 전체 list 처리

`tests/test_characterization_service.py`:

- 정확한 이름 자산 재사용
- FA 2단계 PUT 순서
- 1차 또는 2차 PUT 실패 시 신규 FA 정리
- COMPLETE/RUNNING/FAILED/CANCELED/unknown generation 처리
- 결과 전체 수집

`tests/test_multisite_characterization.py`:

- 최신 static source 선택
- 한 기관 실패 후 다음 기관 계속 실행
- 기관별 status와 오류 요약
- JSON ledger 직렬화

`tests/test_legacy_client_shim.py`:

- legacy와 package import가 동일한 `FedernetClient` 객체를 노출
- 네 Characterization 스크립트가 package import를 사용

## 9. 기록과 운영 문서

- 본 설계 문서
- `docs/superpowers/plans/2026-07-14-characterization-client-stabilization.md` 구현 계획
- `docs/characterization_client_workflow.md` 설치, API 사용, resume, ledger, 2.12 호환성, 기존 스크립트 마이그레이션 기록
- README에 운영 문서 링크 추가

## 10. 완료 기준

1. 네 Characterization 스크립트에 Feature Analysis / Characterization 직접 session 호출이 없다.
2. legacy와 package import가 동일한 canonical class를 사용한다.
3. 기존 FA 1단계·2단계 update 흐름과 기관별 계속 진행이 테스트로 고정된다.
4. Characterization generation 완료 대기와 결과 수집을 package API로 수행할 수 있다.
5. `python -m pip install -e ".[dev]"`, 전체 package pytest, 변경 대상 Ruff, 대상 파일 compile 검증을 통과한다. 기존 범위 밖 Ruff 오류는 별도로 기록한다.
6. 실제 Feedernet 쓰기 없이 모든 자동 검증이 완료된다.
7. 사용자 미커밋 변경과 관련 없는 파일을 되돌리거나 포함하지 않는다.
