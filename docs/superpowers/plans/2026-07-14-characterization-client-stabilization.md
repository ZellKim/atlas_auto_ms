# Characterization Client Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the proven WebAPI 2.12 Feature Analysis and Cohort Characterization scripts into the canonical `atlas_auto` client and reusable single-site/multisite workflows without changing the validated study payloads.

**Architecture:** `FedernetClient` owns one HTTP operation, `CharacterizationService` owns one-site asset and generation lifecycle, and `MultisiteCharacterizationDeployer` owns site iteration and ledger creation. Existing scripts keep their study-specific payload mutations while switching from direct `session` calls to these package interfaces.

**Tech Stack:** Python 3.9+, requests, pytest, Ruff, setuptools editable install.

## Global Constraints

- Preserve WebAPI 2.12 behavior and the verified FA `copy -> PUT -> optional PUT` sequence.
- Do not implement WebAPI 2.15 Temporal, Demographics, Annotation, CLI, or parallel deployment in this change.
- Do not send POST, PUT, DELETE, copy, generate, or cancel requests to live Feedernet during automated verification.
- Obtain credentials only through `automation/credentials.py`; never log or copy credential values.
- Retry only explicitly safe reads. WebAPI GET endpoints that mutate state are never retried.
- Work in the current checkout because `src/atlas_auto/client.py` contains 550 lines of relevant uncommitted work that a clean worktree would omit.
- Preserve all pre-existing user modifications. Do not stage or commit implementation files whose existing changes cannot be separated safely.
- The approved design is `docs/superpowers/specs/2026-07-14-characterization-client-stabilization-design.md`.
- WebAPI 2.12 `GET /cohort-characterization/generation/{id}/result` returns the complete `List<CcResult>`; it is not paginated.

---

## File Map

- Modify `pyproject.toml`: restrict pytest discovery to `tests/` so ad-hoc `data/scripts/test_*.py` files are never imported by the package test run.
- Modify `src/atlas_auto/client.py`: structured WebAPI request helper and FA/Characterization endpoint methods.
- Create `src/atlas_auto/characterization.py`: single-site lifecycle service and result collection.
- Create `src/atlas_auto/multisite_characterization.py`: site model, source selection, sequential deployer, JSON ledger.
- Modify `src/atlas_auto/__init__.py`: public exports.
- Replace `automation/feedernet_client.py`: compatibility re-export with repository `src` fallback.
- Modify four `data/scripts/*char*.py` files: package imports and removal of direct FA/Characterization HTTP calls.
- Create `tests/__init__.py` and `tests/fakes.py`: deterministic, unambiguous test package and requests session/response test doubles.
- Create four `tests/test_*.py` files: client, service, deployer, compatibility tests.
- Create `docs/characterization_client_workflow.md`: installation, migration, usage, retry/resume policy.
- Modify `README.md`: link the operating guide.

---

### Task 1: Safe Test Discovery and Client Request Contract

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/fakes.py`
- Create: `tests/test_characterization_client.py`
- Modify: `src/atlas_auto/client.py:22-68`

**Interfaces:**
- Produces: `AtlasApiError`, `FedernetClient._request_webapi_json(method, path, ..., retry_safe=False)`.
- Consumes: existing `FedernetClient.session`, `webapi_url`, and module-level `time`.

- [ ] **Step 1: Configure isolated package test discovery**

Add this exact section to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

Run:

```powershell
python -m pip install -e ".[dev]"
python -c "from pathlib import Path; text=Path('pyproject.toml').read_text(encoding='utf-8'); assert 'testpaths = [\"tests\"]' in text"
```

Expected: editable installation exits 0 and the configuration assertion passes. Do not run repository-wide pytest until `tests/` and its first test exist.

- [ ] **Step 2: Create deterministic HTTP test doubles**

Create an empty `tests/__init__.py`, then create `tests/fakes.py` with these concrete interfaces:

```python
from dataclasses import dataclass
from typing import Any


@dataclass
class FakeResponse:
    status_code: int = 200
    json_data: Any = None
    text: str = ""

    def json(self):
        if isinstance(self.json_data, Exception):
            raise self.json_data
        return self.json_data


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
```

- [ ] **Step 3: Write failing tests for retry and redacted errors**

Add tests that express the desired public behavior:

```python
import requests
import pytest

from atlas_auto.client import FedernetClient
from tests.fakes import FakeResponse, FakeSession


def connected_client(outcomes):
    client = FedernetClient("https://feedernet.test")
    client.webapi_url = "https://feedernet.test/api/v1/atlas/7/203"
    client.session = FakeSession(outcomes)
    return client


def test_safe_list_retries_transient_timeout(monkeypatch):
    monkeypatch.setattr("atlas_auto.client.time.sleep", lambda _: None)
    client = connected_client([
        requests.Timeout("temporary"),
        FakeResponse(json_data={"content": [{"id": 74}]})
    ])
    assert client.list_feature_analyses() == [{"id": 74}]
    assert len(client.session.calls) == 2


def test_api_error_does_not_include_payload_secret():
    client = connected_client([FakeResponse(status_code=400, text='{"password":"secret"}')])
    with pytest.raises(requests.RequestException) as caught:
        client.create_feature_analysis({"password": "secret", "name": "x"})
    assert type(caught.value).__name__ == "AtlasApiError"
    assert "secret" not in str(caught.value)
    assert "/feature-analysis/" in str(caught.value)
```

Run:

```powershell
python -m pytest tests/test_characterization_client.py -q
```

Expected: tests are collected and fail because the new client methods do not exist; there is no collection error.

- [ ] **Step 4: Implement the minimal common request policy**

Add `AtlasApiError` at module scope. Add a private `_request_webapi_json` method that:

```python
_TRANSIENT_HTTP_STATUS = {429, 502, 503, 504}
_REDACT_PATTERN = re.compile(
    r'(?i)(password|authorization|cookie|token)(["\s:=]+)([^,}\s]+)'
)


class AtlasApiError(requests.RequestException):
    def __init__(self, method, path, message, status_code=None):
        self.method = method
        self.path = path
        self.status_code = status_code
        status = f" status={status_code}" if status_code is not None else ""
        super().__init__(f"{method.upper()} {path}{status}: {message}")
```

The helper must use `(10, 30)` as its default timeout, make three total attempts only when `retry_safe=True`, retry connection errors/timeouts and the four transient HTTP statuses, redact the response snippet, return `None` for allowed empty success responses, and raise `AtlasApiError` for non-2xx or invalid JSON. It must never infer safety from `method == "GET"`; the caller supplies `retry_safe` explicitly.

- [ ] **Step 5: Add the first list/create methods and verify green**

Implement `list_feature_analyses()` with `retry_safe=True`, Page/list normalization, and `create_feature_analysis()` with `retry_safe=False`.

Run:

```powershell
python -m pytest tests/test_characterization_client.py -q
```

Expected: the two tests pass.

- [ ] **Step 6: Record a checkpoint without committing overlapping user changes**

Run:

```powershell
git diff --check -- pyproject.toml src/atlas_auto/client.py tests/fakes.py tests/test_characterization_client.py
git status --short -- pyproject.toml src/atlas_auto/client.py tests
```

Expected: no whitespace errors; `src/atlas_auto/client.py` remains a modified user-owned file and is not staged.

---

### Task 2: Complete Feature Analysis and Characterization Client Methods

**Files:**
- Modify: `tests/test_characterization_client.py`
- Modify: `src/atlas_auto/client.py` immediately before the Estimation section

**Interfaces:**
- Consumes: `_request_webapi_json` from Task 1.
- Produces: every low-level method listed in design section 4.1.

- [ ] **Step 1: Add parameterized failing endpoint tests**

Use a parameterized test table containing these exact operations:

```python
ENDPOINT_CASES = [
    ("get_feature_analysis", (372,), "GET", "/feature-analysis/372", True),
    ("copy_feature_analysis", (372,), "GET", "/feature-analysis/372/copy", False),
    ("update_feature_analysis", (901, {"id": 901}), "PUT", "/feature-analysis/901", False),
    ("delete_feature_analysis", (901,), "DELETE", "/feature-analysis/901", False),
    ("list_characterizations", (), "GET", "/cohort-characterization/", True),
    ("get_characterization", (121,), "GET", "/cohort-characterization/121", True),
    ("create_characterization", ({"name": "cc"},), "POST", "/cohort-characterization/", False),
    ("update_characterization", (121, {"id": 121}), "PUT", "/cohort-characterization/121", False),
    ("delete_characterization", (121,), "DELETE", "/cohort-characterization/121", False),
    ("export_characterization", (121,), "GET", "/cohort-characterization/121/export", True),
    ("import_characterization", ({"name": "cc"},), "POST", "/cohort-characterization/import", False),
    ("generate_characterization", (121, "cdm"), "POST", "/cohort-characterization/121/generation/cdm", False),
    ("get_characterization_generations", (121,), "GET", "/cohort-characterization/121/generation", True),
    ("get_characterization_result_count", (77,), "GET", "/cohort-characterization/generation/77/result/count", True),
    ("get_characterization_results", (77,), "GET", "/cohort-characterization/generation/77/result", True),
    ("delete_characterization_generation", (77,), "DELETE", "/cohort-characterization/generation/77", False),
]
```

The test must assert method, path, default timeout, JSON body or params, and that only safe rows retry. Add a separate test proving `copy_feature_analysis()` consumes one outcome and raises immediately on timeout.

Run:

```powershell
python -m pytest tests/test_characterization_client.py -q
```

Expected: failures identify each missing method.

- [ ] **Step 2: Implement all Feature Analysis methods**

Use these exact endpoint contracts:

```python
list_feature_analyses(size=200, analysis_type=None)
get_feature_analysis(feature_analysis_id)
create_feature_analysis(spec)
copy_feature_analysis(feature_analysis_id)
update_feature_analysis(feature_analysis_id, spec)
delete_feature_analysis(feature_analysis_id)
```

Pass `params={"size": size}` and optional `type` for list. Normalize Page/list list responses. Set `allow_empty=True` on delete. Mark only list/detail as `retry_safe=True`; copy is a state-changing GET and remains false.

- [ ] **Step 3: Implement all Characterization methods**

Use these exact signatures:

```python
list_characterizations(size=200)
get_characterization(characterization_id)
create_characterization(spec)
update_characterization(characterization_id, spec)
delete_characterization(characterization_id)
export_characterization(characterization_id)
import_characterization(export_spec)
generate_characterization(characterization_id, source_key)
get_characterization_generations(characterization_id)
get_characterization_result_count(generation_id)
get_characterization_results(generation_id, threshold_level=0.01)
delete_characterization_generation(generation_id)
```

`get_characterization_results` sends only `thresholdLevel`, uses `(10, 120)`, and returns a list. `get_characterization_result_count` accepts the WebAPI 2.12 numeric JSON response and returns `int`. List and generation list normalize Page/list responses.

- [ ] **Step 4: Verify all low-level contracts**

Run:

```powershell
python -m pytest tests/test_characterization_client.py -q
```

Expected: all client tests pass, including no retry for copy/generate.

- [ ] **Step 5: Check the focused diff**

Run:

```powershell
git diff --check -- src/atlas_auto/client.py tests/test_characterization_client.py
rg -n "def (list_feature_analyses|copy_feature_analysis|list_characterizations|get_characterization_results)" src/atlas_auto/client.py
```

Expected: each method appears exactly once and no whitespace errors are reported.

---

### Task 3: Single-Site Characterization Lifecycle Service

**Files:**
- Create: `src/atlas_auto/characterization.py`
- Create: `tests/test_characterization_service.py`

**Interfaces:**
- Consumes: Task 2 client methods.
- Produces: `EnsureResult`, `GenerationResult`, `CharacterizationService`.

- [ ] **Step 1: Write failing asset reuse and two-stage update tests**

Create a small recording client in the test and assert:

```python
def test_existing_feature_analysis_is_reused_without_copy():
    client = RecordingClient(feature_analyses=[{"id": 900, "name": "[B17] WBC_Pre365"}])
    service = CharacterizationService(client)
    result = service.ensure_feature_analysis(
        "[B17] WBC_Pre365", 372, lambda payload: payload
    )
    assert result.reused is True
    assert result.resource["id"] == 900
    assert client.calls == [("list_feature_analyses",)]


def test_new_feature_analysis_uses_copy_then_two_updates():
    client = RecordingClient(feature_analyses=[])
    service = CharacterizationService(client)
    result = service.ensure_feature_analysis(
        "[B17] WBC_Pre365",
        372,
        lambda payload: {**payload, "phase": 1},
        lambda payload: {**payload, "phase": 2},
    )
    assert result.reused is False
    assert [call[0] for call in client.calls] == [
        "list_feature_analyses", "copy_feature_analysis",
        "update_feature_analysis", "update_feature_analysis",
    ]
```

Add a test where the second update raises and assert `delete_feature_analysis(new_id)` is called once.

Run:

```powershell
python -m pytest tests/test_characterization_service.py -q
```

Expected: import fails because the service module does not exist.

- [ ] **Step 2: Implement result dataclasses and exact-name resolution**

Create:

```python
@dataclass(frozen=True)
class EnsureResult:
    resource: dict
    reused: bool


@dataclass(frozen=True)
class GenerationResult:
    generation: dict
    action: str
```

`CharacterizationService._find_latest_exact_name()` filters by exact `name`, sorts numeric `id`, returns the largest ID, and logs a warning if more than one match exists.

- [ ] **Step 3: Implement FA and Characterization ensure methods**

Implement:

```python
ensure_feature_analysis(
    name, template_id, prepare_first, prepare_second=None,
    reuse_existing=True, search_size=2000,
) -> EnsureResult

ensure_created_characterization(spec, reuse_existing=True, search_size=2000) -> EnsureResult

ensure_imported_characterization(
    export_spec, name, reuse_existing=True, search_size=2000,
) -> EnsureResult
```

Deep-copy API payloads before invoking callbacks. The service sets the requested name after the first callback. On any update failure, delete only the ID returned by the current copy call and re-raise the original exception after best-effort cleanup.

- [ ] **Step 4: Write failing generation state tests**

Cover WebAPI 2.12 states `PENDING`, `RUNNING`, `COMPLETE`, `ERROR`, plus compatibility states `FAILED` and `CANCELED`. Assert:

- COMPLETE returns `action="REUSED"` and does not generate.
- PENDING/RUNNING returns `action="WAITING"` and does not generate.
- ERROR/FAILED/CANCELED or no generation calls generate and returns `action="STARTED"`.
- unknown state raises `ValueError` and never generates.
- `force=True` always generates.

Run the focused generation tests and confirm they fail because methods are absent.

- [ ] **Step 5: Implement generation decision, wait, and results**

Implement:

```python
run_or_reuse(characterization_id, source_key, force=False) -> GenerationResult
wait_for_generation(characterization_id, source_key, timeout=3600, poll_interval=10) -> dict
collect_results(generation_id) -> list
```

Select the newest same-source generation by numeric `id`. `wait_for_generation` repeatedly reads the generation list, returns COMPLETE, raises `RuntimeError` for ERROR/FAILED/CANCELED, raises `ValueError` for unknown states, and raises `TimeoutError` at the deadline. `collect_results` reads count for logging and then performs the single WebAPI 2.12 full-list result GET; it does not fabricate pagination.

- [ ] **Step 6: Verify service tests**

Run:

```powershell
python -m pytest tests/test_characterization_service.py -q
```

Expected: all asset lifecycle, cleanup, state, wait, and result tests pass.

---

### Task 4: Sequential Multisite Deployer and Ledger

**Files:**
- Create: `src/atlas_auto/multisite_characterization.py`
- Create: `tests/test_multisite_characterization.py`

**Interfaces:**
- Consumes: `CharacterizationService`, caller-provided `client_factory`, `source_selector`, `name_factory`, optional `prepare_site`.
- Produces: `SiteTarget`, `DeploymentRecord`, `select_latest_static_source`, `MultisiteCharacterizationDeployer.deploy`, `write_ledger`.

- [ ] **Step 1: Write failing source selection and failure-isolation tests**

The source selector test supplies monthly, weekly, and dated static sources and asserts the highest numeric suffix static source is selected. The deployer test uses three targets where the second raises; assert records are produced in input order and the third target still runs.

Expected record fields:

```python
from typing import Optional


@dataclass(frozen=True)
class DeploymentRecord:
    code: str
    group_id: int
    site_id: int
    status: str
    characterization_id: Optional[int] = None
    generation_id: Optional[int] = None
    source_key: Optional[str] = None
    source_name: Optional[str] = None
    error: Optional[str] = None
```

Use these Python 3.9-compatible `Optional[...]` annotations exactly.

Run:

```powershell
python -m pytest tests/test_multisite_characterization.py -q
```

Expected: import fails because the module does not exist.

- [ ] **Step 2: Implement immutable site and record models**

Use `@dataclass(frozen=True)` for `SiteTarget` and `DeploymentRecord`. Add `to_dict()` using `dataclasses.asdict` so JSON serialization has no custom encoder dependency.

- [ ] **Step 3: Implement current latest-static-source behavior**

Move the verified regex rule from the scripts without semantic changes:

- exclude source names containing `monthly` or `weekly`, case-insensitive;
- extract trailing `_(\d+)$`;
- choose the largest numeric suffix;
- fall back to the last source only when no dated static source exists;
- return `None` for an empty source list.

- [ ] **Step 4: Implement sequential deployment**

`deploy()` accepts:

```python
deploy(
    export_spec,
    targets,
    client_factory,
    name_factory,
    source_selector=select_latest_static_source,
    prepare_site=None,
    reuse_existing=True,
    wait=False,
) -> list
```

For each target: create/login client through `client_factory`, connect site, select source, deep-copy export, import or reuse with a site-specific name, invoke optional `prepare_site(client, source_key, target)`, call `run_or_reuse`, optionally wait, and append one record. Catch exceptions inside the per-site loop, sanitize to a short message, append FAILED, and continue.

Map actions to records as follows: `REUSED -> REUSED`, `WAITING -> STARTED` unless `wait=True`, `STARTED -> STARTED`, completed wait -> COMPLETE.

For a generation object, set `generation_id` from `id`; for a just-started `JobExecutionResource`, fall back to `executionId`. Do not assume those two identifiers have the same semantics in later status lookups.

- [ ] **Step 5: Implement atomic ledger writing**

`write_ledger(records, output_path)` writes UTF-8 JSON to a sibling `.tmp` file and replaces the target with `Path.replace()`. Tests assert Korean site names are preserved and no partial target file remains.

- [ ] **Step 6: Verify deployer tests**

Run:

```powershell
python -m pytest tests/test_multisite_characterization.py -q
```

Expected: all tests pass and no live network object is constructed.

---

### Task 5: Public Exports, Legacy Shim, and Script Migration

**Files:**
- Modify: `src/atlas_auto/__init__.py`
- Replace: `automation/feedernet_client.py`
- Modify: `data/scripts/create_char_v2.py`
- Modify: `data/scripts/create_biomarker_fas_v2.py`
- Modify: `data/scripts/deploy_char_17bio.py`
- Modify: `data/scripts/deploy_char_multisite.py`
- Create: `tests/test_legacy_client_shim.py`

**Interfaces:**
- Consumes: Tasks 2-4 public classes.
- Produces: stable imports from `atlas_auto` and legacy `feedernet_client`.

- [ ] **Step 1: Write failing import and source-scan tests**

Test that:

```python
from atlas_auto import FedernetClient as CanonicalClient
from automation.feedernet_client import FedernetClient as LegacyClient

assert LegacyClient is CanonicalClient
```

Read the four script sources and assert they contain `from atlas_auto import` and contain no regex match for:

```python
r"(?:client|c|session)\.session\.(?:get|post|put|delete)|session\.(?:get|post|put|delete)"
```

Run the test and confirm it fails against current imports/direct calls.

- [ ] **Step 2: Export new package interfaces**

Update `src/atlas_auto/__init__.py` to export:

```python
AtlasApiError
CharacterizationService
EnsureResult
GenerationResult
MultisiteCharacterizationDeployer
SiteTarget
DeploymentRecord
select_latest_static_source
write_ledger
```

Retain every existing export and version.

- [ ] **Step 3: Replace the duplicate legacy implementation with a shim**

`automation/feedernet_client.py` must first try `from atlas_auto.client import AtlasApiError, FedernetClient`. On `ModuleNotFoundError`, insert `<repo>/src` derived from `Path(__file__).resolve().parents[1]` and retry. Export only those two names. Do not import credentials or perform network activity at import time.

- [ ] **Step 4: Migrate `create_char_v2.py` and `create_biomarker_fas_v2.py`**

- Keep credential loading from `automation/credentials.py`, but replace the hard-coded drive path with a path derived from `Path(__file__).resolve().parents[2] / "automation"`.
- Import `FedernetClient` and `CharacterizationService` from `atlas_auto`.
- Replace template/detail/create/update/delete/Characterization/generate direct calls with client or service methods.
- Preserve all concept, time-window, cohort, and source-key values.
- Use `EnsureResult.resource["id"]` and `run_or_reuse`; do not change output filenames.

- [ ] **Step 5: Migrate `deploy_char_17bio.py` and `deploy_char_multisite.py`**

- Replace duplicate `get_latest_static_source` functions with the package selector.
- Keep the KHNMC FA payload callback code in `deploy_char_17bio.py`, but pass it to `ensure_feature_analysis`.
- Use `ensure_created_characterization`, `export_characterization`, and the sequential deployer.
- Build clients in the script factory with `get_feedernet_credentials()` and one independent client per target.
- Preserve the current site tuples, names, KHNMC IDs, source keys, and external ledger output path.

- [ ] **Step 6: Verify imports and absence of direct calls**

Run:

```powershell
python -m pytest tests/test_legacy_client_shim.py -q
rg -n "session\.(get|post|put|delete)|\.session\.(get|post|put|delete)" data/scripts/create_char_v2.py data/scripts/create_biomarker_fas_v2.py data/scripts/deploy_char_17bio.py data/scripts/deploy_char_multisite.py
python -m compileall -q src/atlas_auto automation/feedernet_client.py data/scripts/create_char_v2.py data/scripts/create_biomarker_fas_v2.py data/scripts/deploy_char_17bio.py data/scripts/deploy_char_multisite.py
```

Expected: pytest passes, `rg` exits 1 with no matches, compileall exits 0.

---

### Task 6: Operating Guide and Migration Record

**Files:**
- Create: `docs/characterization_client_workflow.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: final package APIs from Tasks 2-5.
- Produces: installation and operating instructions without credentials.

- [ ] **Step 1: Write the operating guide**

Document these exact sections:

1. `python -m pip install -e ".[dev]"`
2. architecture responsibilities
3. low-level client examples
4. FA one-stage and two-stage service examples
5. Characterization create/import, run/resume, wait, result collection
6. sequential multisite example with `SiteTarget`
7. credential factory using only `automation.credentials.get_feedernet_credentials`
8. safe retry table, including mutating GET exclusions
9. WebAPI 2.12 full-list result behavior
10. migration table mapping the four old scripts to new APIs
11. rollback note: the scripts' study payloads were not changed

Use synthetic IDs and `example_source`; do not include real credentials, cookie values, or tokens.

- [ ] **Step 2: Link the guide from README**

Add a short `Characterization / Feature Analysis` subsection near existing usage documentation with a relative link to `docs/characterization_client_workflow.md` and state WebAPI 2.12 compatibility.

- [ ] **Step 3: Validate documentation**

Run:

```powershell
rg -n "TBD|TODO|password\s*=|Bearer\s+[A-Za-z0-9]" docs/characterization_client_workflow.md
git diff --check -- docs/characterization_client_workflow.md README.md
```

Expected: no placeholders, credential-like values, or whitespace errors.

---

### Task 7: Full Verification and Change Audit

**Files:**
- Verify all files listed above.
- Do not modify unrelated dirty files.

**Interfaces:**
- Consumes: all previous task deliverables.
- Produces: fresh evidence for the completion report.

- [ ] **Step 1: Run the complete package test suite**

```powershell
python -m pytest -q
```

Expected: all tests under `tests/` pass with zero failures; `data/scripts/test_*.py` are not collected.

- [ ] **Step 2: Run Ruff and compile verification**

```powershell
python -m ruff check src/atlas_auto/characterization.py src/atlas_auto/multisite_characterization.py tests automation/feedernet_client.py data/scripts/create_char_v2.py data/scripts/create_biomarker_fas_v2.py data/scripts/deploy_char_17bio.py data/scripts/deploy_char_multisite.py
python -m ruff check src/atlas_auto/client.py --ignore F401
python -m compileall -q src/atlas_auto tests automation/feedernet_client.py data/scripts/create_char_v2.py data/scripts/create_biomarker_fas_v2.py data/scripts/deploy_char_17bio.py data/scripts/deploy_char_multisite.py
```

Expected: all three commands exit 0. Do not expand Ruff cleanup to pre-existing errors in `src/atlas_auto/cli.py` or `cohort_validator.py`; the pre-change scoped baseline contained 26 unrelated errors.

- [ ] **Step 3: Verify editable installation in a fresh process**

```powershell
python -c "from atlas_auto import FedernetClient, CharacterizationService, MultisiteCharacterizationDeployer; print('imports-ok')"
```

Expected: `imports-ok`.

- [ ] **Step 4: Verify no direct Characterization HTTP calls remain in migrated scripts**

```powershell
rg -n "session\.(get|post|put|delete)|\.session\.(get|post|put|delete)" data/scripts/create_char_v2.py data/scripts/create_biomarker_fas_v2.py data/scripts/deploy_char_17bio.py data/scripts/deploy_char_multisite.py
```

Expected: exit 1 and no output.

- [ ] **Step 5: Audit the final diff against the dirty baseline**

```powershell
git status --short
git diff --check
git diff --stat
git diff -- src/atlas_auto/client.py automation/feedernet_client.py src/atlas_auto/characterization.py src/atlas_auto/multisite_characterization.py tests docs/characterization_client_workflow.md README.md data/scripts/create_char_v2.py data/scripts/create_biomarker_fas_v2.py data/scripts/deploy_char_17bio.py data/scripts/deploy_char_multisite.py
```

Confirm every approved requirement has a corresponding code path and test. Explicitly list pre-existing changes that remain mixed in `src/atlas_auto/client.py` and the two previously modified scripts. Do not stage or commit them without separate user authorization.

- [ ] **Step 6: Report verification evidence**

The final handoff must include test count, Ruff/compile/install results, changed-file links, the fact that no live Feedernet writes were executed, and any remaining limitation. Do not claim success if any command above did not exit with the expected result.
