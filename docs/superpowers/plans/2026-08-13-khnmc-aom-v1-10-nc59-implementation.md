# KHNMC AOM v1.10 NC59 Implementation Plan

> **For Codex:** Execute continuously with test-driven development. Preserve all v1.9 live and repository artifacts. Use `src/atlas_auto/client.py` and `automation/credentials.py` only. Every live mutation must follow a read-only exact-name and contract preflight.

**Goal:** Create one validated 59-outcome KHNMC negative-control concept set, create two new v1.10 Estimations that preserve the v1.9 P1/P2 designs, and trigger two new Feedernet analyses on the exact prior 23-CDM set.

**Architecture:** A pure builder owns the immutable NC59 roster, P1/P2 patching, normalized contracts, and fail-closed validators. A deployment script performs concept-set and Estimation writes without execution. A separate Feedernet script imports the validated Estimations, rechecks the exact 23-CDM manifest, and triggers only when given `--execute`. Durable JSON/Markdown artifacts record every boundary.

**Tech Stack:** Python 3.12, pytest, OHDSI ATLAS WebAPI 2.12, `atlas_auto.client.FedernetClient`, Feedernet portal API, JSON/Markdown evidence artifacts.

---

## Task 1: Add failing NC59 builder and validator tests

**Files:**

- Create: `tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py`
- Read fixtures: `studies/fracture_treatment/cohort_definitions/khnmc_v1_9_estimations_20260812/primary1/estimation_export.json`
- Read fixtures: `studies/fracture_treatment/cohort_definitions/khnmc_v1_9_estimations_20260812/primary2/estimation_export.json`

**Step 1: Write the failing tests**

Cover these exact behaviors:

```python
assert len(builder.NC_CONCEPTS) == 59
assert len({row["concept_id"] for row in builder.NC_CONCEPTS}) == 59
assert builder.CONFIRMED_NC_IDS == EXPECTED_59_IDS
```

Build P1 and P2 from the v1.9 exports plus full ConceptDTO fixtures and assert:

- P1 T/C/O remains `2684/2685/2636`, risk start remains 91.
- P2 T/C/O remains `2687/2688/2636`, risk start remains 366.
- all non-NC normalized fields match v1.9;
- package names are `AOMFxKHNMCv110AllPeriodP1/P2`;
- concept set `#524` is absent;
- one NC concept set contains 59 items;
- one cross-reference uses target index 0;
- P1 and P2 each contain 59 exact mapped triples.

Add negative tests for missing selected IDs, duplicate items, wrong concept metadata, empty NC rows, wrong target/comparator IDs, wrong target index, dangling concept-set references, duplicate triples, and any change to a preserved v1.9 analysis field.

**Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py -q
```

Expected: FAIL because the v1.10 module does not exist.

## Task 2: Implement the pure v1.10 builder and validators

**Files:**

- Create: `studies/fracture_treatment/scripts/build_khnmc_v1_10_estimations.py`
- Test: `tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py`

**Step 1: Add immutable configuration**

Define the exact 59 ID/name pairs, artifact paths, source Estimation IDs `291/292`, output names, package names, T/C/O IDs, and expected cohort counts. Import v1.9 only for stable cohort-readiness utilities; do not delegate the semantic contract to the lossy v1.8/v1.9 contract.

**Step 2: Add pure patching**

Implement:

```python
def build_estimation_export(
    source: Mapping[str, Any],
    concept_set: Mapping[str, Any],
    analysis_key: str,
) -> dict[str, Any]:
    ...
```

Deep-copy the v1.9 source, change only approved identity/description and NC fields, generate 59 NC rows for the analysis-specific T/C pair, and retain all other fields.

**Step 3: Add stage-specific validation**

Implement:

```python
def validate_selected_concepts(concepts: Iterable[Mapping[str, Any]]) -> dict[str, Any]: ...
def validate_design(spec: Mapping[str, Any], analysis_key: str) -> dict[str, Any]: ...
def validate_export(spec: Mapping[str, Any], analysis_key: str) -> dict[str, Any]: ...
def preserved_v19_contract(spec: Mapping[str, Any]) -> dict[str, Any]: ...
def v110_contract(spec: Mapping[str, Any]) -> dict[str, Any]: ...
```

The final export validator must require exact IDs and exact T/C triples even when exported concept-set items are empty.

**Step 4: Run tests to verify GREEN**

Run the Task 1 command and the v1.9 regression test:

```powershell
python -m pytest tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py tests/fracture_treatment/test_build_deploy_khnmc_v1_9_estimations.py -q
```

Expected: PASS.

## Task 3: Implement create-only ATLAS deployment

**Files:**

- Create: `studies/fracture_treatment/scripts/deploy_khnmc_v1_10_estimations.py`
- Modify: `tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py`

**Step 1: Write failing deployer-safety tests**

Use a fake client to assert:

- concept creation is followed by exact 59-item PUT and readback;
- exact-name matching concept sets are reused only after exact item equality;
- exact-name mismatch and duplicates fail without an update call;
- design validation occurs before Estimation copy/PUT;
- new Estimations copy sources `291/292` and do not update mismatching same-name objects;
- final export validation and `/estimation/check` occur before success is recorded;
- generation IDs do not change;
- the deployer contains no execution path.

Run the focused tests and verify the new cases fail.

**Step 2: Implement live concept collection and hierarchy preflight**

Using the canonical client:

- connect to group `7`, site `203`;
- confirm source `cdmpv53_251128`;
- fetch the exact live ConceptDTO for every configured ID;
- fetch descendant closures and outcome `#2636` expression;
- enforce zero selected-pair and primary-outcome overlap;
- save the selection manifest before mutation.

**Step 3: Implement fail-closed concept-set deployment**

Search exact name. Reuse only if the readback item contract is identical; otherwise fail. If absent, POST the concept-set shell, PUT 59 items, and read back exact identity and items. Never update a mismatching existing object.

**Step 4: Implement fail-closed Estimation deployment**

Export sources `#291/#292`, build and validate expected specs, use the verified copy+PUT pattern, export again, enforce the exact final contract, run `/estimation/check`, verify no generation IDs changed, and write all artifacts. The default command creates only and never executes.

**Step 5: Run focused tests**

```powershell
python -m pytest tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py -q
```

Expected: PASS.

## Task 4: Implement Feedernet prepare/execute workflow

**Files:**

- Create: `studies/fracture_treatment/scripts/run_khnmc_v1_10_feedernet_23site.py`
- Create: `tests/fracture_treatment/test_run_khnmc_v1_10_feedernet_23site.py`

**Step 1: Write failing portal-workflow tests**

Test that the script:

- loads validated Estimation deployment artifacts only;
- derives 23 unique CDM IDs from both v1.9 execution groups and requires exact set equality;
- creates two new project analyses without triggering by default;
- imports the exact v1.10 ATLAS Estimation into KHNMC ATLAS site `203`;
- fails on duplicate or mismatching exact names;
- re-reads imported analysis details before execution;
- requires `--execute` and triggers exactly the two new analysis IDs with exactly the 23 validated CDM IDs;
- captures group IDs, execution IDs, and immediate status.

Run the focused test and verify RED.

**Step 2: Implement prepare mode**

Use `get_project_analyses`, the verified project-analysis create endpoint, and the verified KHNMC ATLAS import endpoint. Write `analysis_map.json` and `site_manifest.json`; do not execute.

**Step 3: Implement explicit execution mode**

Revalidate the deployment/export contracts and prepared analysis map, call `run_analysis_execution` once for P1 and once for P2, verify successful API envelopes, then call `get_analysis_executions` and save raw trigger and immediate-status artifacts.

**Step 4: Run tests**

```powershell
python -m pytest tests/fracture_treatment/test_run_khnmc_v1_10_feedernet_23site.py tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py -q
```

Expected: PASS.

## Task 5: Record incident, NC requirement, and limitations

**Files:**

- Modify: `docs/system_knowledge_base.md`
- Modify: `docs/new_study_topic_to_estimation_protocol.md`
- Modify: `studies/fracture_treatment/PROGRESS.md`
- Modify: `studies/fracture_treatment/study_knowledge_base.md`
- Create during deployment: `studies/fracture_treatment/cohort_definitions/khnmc_v1_10_estimations_20260813/VALIDATION.md`

Apply narrow edits only. Record that all Estimations require effective NCs, an empty referenced placeholder is invalid even when `/estimation/check` passes, final `/export` is the hard gate, v1.9 remains historical evidence, v1.10 uses confirmed NC59, and P2 retains landmark-conditioned healthy-adherer/time-varying bias. Record the post-result requirement of at least 50 finite estimable NCs per P1/P2 site before stable calibration claims.

## Task 6: Run local verification and dry-run

Run:

```powershell
python -m pytest tests/fracture_treatment/test_build_deploy_khnmc_v1_10_estimations.py tests/fracture_treatment/test_run_khnmc_v1_10_feedernet_23site.py tests/fracture_treatment/test_build_deploy_khnmc_v1_9_estimations.py -q
python studies/fracture_treatment/scripts/deploy_khnmc_v1_10_estimations.py --dry-run
python studies/fracture_treatment/scripts/run_khnmc_v1_10_feedernet_23site.py --dry-run
```

Expected: all tests pass; dry-runs report NC59, exact T/C mappings, no hierarchy or outcome overlap, exact 23 CDMs, and zero mutations/triggers.

Review the exact diff and confirm no unrelated dirty file was altered.

## Task 7: Create and verify live ATLAS assets

Run the create-only deployer without an execution flag. Record the new concept-set ID and two new Estimation IDs.

Re-read from live API and verify:

- concept-set identity and 59 items;
- both final exports contain exactly 59 effective NCs;
- exact selected ID set and T/C mapping;
- preserved v1.9 non-NC contracts;
- diagnostics have no CRITICAL warnings;
- no local ATLAS Estimation generation was created.

If any check fails, stop before Feedernet import.

## Task 8: Prepare and trigger new Feedernet analyses

Run prepare mode first. Inspect the new analysis IDs and imported ATLAS mapping. Then run the same command with `--execute`.

Verify the returned two execution groups each contain exactly 23 unique CDM IDs equal to the validated manifest. Save immediate raw statuses and update `VALIDATION.md`, `PROGRESS.md`, and `study_knowledge_base.md` with exact IDs and timestamps.

Do not claim completion of the distributed analyses until their live execution statuses actually reach terminal success. The deliverable for this task is verified creation and triggering plus current status evidence.

## Task 9: Final review

Run the focused and adjacent regression suites again, inspect all live artifact IDs from the saved JSON against current GET responses, and perform an independent code/spec review. Fix all Critical or Important findings before reporting completion.
