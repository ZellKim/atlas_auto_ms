# tests/

Two kinds of test live here, and the difference matters.

## `tests/*.py` — contract tests (tracked in git)

These pin the behaviour of `src/atlas_auto/`. Each one exists because a live
failure proved the contract was not obvious. They must keep working when every
study is gone, so they never import anything from `studies/`.

| File | What it pins |
|---|---|
| `test_generation_safety.py` | `COMPLETE` alone is not success; `isValid` and `id.sourceId` both decide |
| `test_cohort_generation_client.py` | the shared wait applies that judgement and scopes to one source |
| `test_characterization_client.py` | endpoint shapes, including `thresholdLevel` defaulting to 0 |
| `test_characterization_service.py` | a short result list raises instead of returning silently |
| `test_characterization_safety.py` | design reads, PRESET names, feature identity, import mapping |
| `test_attrition.py` | the waterfall comes from `treemapData`, never from `countSatisfying` |
| `test_study_runner.py` | stage order, the uncertain-create stop, evidence digests, readback gate |
| `test_estimation_validation.py` | negative controls are required, fail-closed |
| `test_incidence_rate_client.py`, `test_cohort_definition_sql_client.py` | endpoint contracts |
| `test_multisite_characterization.py` | multi-site deployment ledger |
| `test_public_surface.py` | every guard is reachable from `import atlas_auto` |
| `test_vendored_modules.py` | a study's shipped copy of a shared module has not drifted |
| `test_legacy_client_shim.py` | the old import path still resolves |

**A new contract test belongs here, not in a study directory.** A test that
lives beside one version's script dies with that script, and the next study
starts from nothing. That is how the same traps were hit twice each across v1.13
to v1.17; see `docs/knowledge_promotion_protocol.md`.

## `tests/{study}/` — study-version tests (Drive only, gitignored)

These pin one study's own build and deploy scripts, one file per version. They
import `studies.{study}.scripts.*`, and `studies/` is gitignored and lives on
Drive under the three-tier layout in `docs/system_knowledge_base.md` §7.0. They
are therefore not in the repository either, and each directory carries a
`conftest.py` that skips it when its study is absent.

`pytest tests` is correct in both places: everything locally, contract tests
only on a fresh clone.

## Running

    pytest tests                      # everything available here
    pytest tests -q --ignore=tests/fracture_treatment   # contract tests only

As of 2026-08-15: 212 contract tests, 426 fracture_treatment version tests.
