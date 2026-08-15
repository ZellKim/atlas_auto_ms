"""Contract tests for the shared study-run skeleton.

`docs/system_knowledge_base.md` and the OHDSI guardrails both require the same
sequence: deploy without executing, inspect what was deployed, trigger the exact
intended analysis, capture its execution identifier, monitor that execution,
and preserve raw status snapshots. Every study re-implemented that sequence by
hand, and the one runner that did it properly (fracture_treatment v1.11) was
1,472 lines whose generic half was then not available to the next analysis.

What is generic is here: the append-only operation journal, the uncertain-create
stop, evidence files whose digest matches their own bytes, the fail-closed
readback gate, and the stage ordering itself.
"""

import json

import pytest

from atlas_auto.study_runner import (
    STAGES,
    StageOrderError,
    StudyRun,
    UncertainCreateError,
    canonical_json,
    digest,
    write_evidence,
)


# ── evidence files ────────────────────────────────────────────────────────


def test_write_evidence_returns_the_digest_of_the_bytes_it_wrote(tmp_path):
    """`Path.write_text` translates LF to CRLF on Windows, so a digest taken
    over the in-memory string never matches the file. All 34 rows of both
    published INDEX.csv files failed exactly this way on 2026-08-15."""
    path = tmp_path / "evidence.json"

    reported = write_evidence(path, {"personCount": 1864})

    import hashlib
    assert reported == hashlib.sha256(path.read_bytes()).hexdigest()


def test_write_evidence_uses_lf_regardless_of_platform(tmp_path):
    path = tmp_path / "evidence.json"

    write_evidence(path, {"a": 1, "b": 2})

    assert b"\r\n" not in path.read_bytes()


def test_write_evidence_creates_parent_directories(tmp_path):
    path = tmp_path / "deep" / "nested" / "evidence.json"

    write_evidence(path, {"a": 1})

    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}


def test_write_evidence_replaces_atomically_leaving_no_temp_files(tmp_path):
    path = tmp_path / "evidence.json"

    write_evidence(path, {"first": True})
    write_evidence(path, {"second": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"second": True}
    assert [p.name for p in tmp_path.iterdir()] == ["evidence.json"]


def test_canonical_json_is_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_digest_is_order_independent():
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})


# ── the operation journal ─────────────────────────────────────────────────


def test_a_run_journals_each_recorded_stage(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")

    run.record("build", "p1_characterization", localPath="x.json")

    records = run.journal_records()
    assert [r["event"] for r in records] == ["build"]
    assert records[0]["key"] == "p1_characterization"
    assert records[0]["run_id"] == "v1.18"
    assert records[0]["localPath"] == "x.json"
    assert "timestamp" in records[0]


def test_the_journal_survives_a_new_run_object_over_the_same_directory(tmp_path):
    StudyRun(tmp_path, run_id="v1.18").record("build", "p1")

    resumed = StudyRun(tmp_path, run_id="v1.18")

    assert resumed.completed("build", "p1") is True


def test_a_truncated_journal_line_is_a_hard_stop(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")
    (tmp_path / "operation_journal.jsonl").open("a", encoding="utf-8").write(
        "{not json\n"
    )

    with pytest.raises(RuntimeError) as excinfo:
        StudyRun(tmp_path, run_id="v1.18").journal_records()

    assert "uncertain" in str(excinfo.value).lower()


# ── stage ordering ────────────────────────────────────────────────────────


def test_the_stage_order_is_the_guardrail_sequence():
    assert STAGES == (
        "build", "deploy", "inspect", "trigger", "capture", "monitor", "snapshot",
    )


def test_recording_a_stage_out_of_order_is_refused(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")

    with pytest.raises(StageOrderError) as excinfo:
        run.record("trigger", "p1")

    assert "deploy" in str(excinfo.value)


def test_the_full_sequence_is_accepted(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")

    for stage in STAGES:
        run.record(stage, "p1")

    assert all(run.completed(stage, "p1") for stage in STAGES)


def test_stages_are_tracked_per_key_not_globally(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")
    run.record("deploy", "p1")

    with pytest.raises(StageOrderError):
        run.record("deploy", "p2")


def test_an_unknown_stage_name_is_refused(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")

    with pytest.raises(ValueError):
        run.record("execute", "p1")


def test_repeating_a_stage_is_allowed_and_does_not_break_order(tmp_path):
    """Re-running a stage after a fix is normal; it is not an ordering error."""
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")
    run.record("build", "p1")
    run.record("deploy", "p1")

    assert run.completed("build", "p1") is True


# ── deploy without executing ──────────────────────────────────────────────


def test_triggering_before_inspecting_is_refused(tmp_path):
    """A deploy acknowledgement does not prove the deployed artifact is right."""
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")
    run.record("deploy", "p1")

    with pytest.raises(StageOrderError):
        run.assert_ready_to_trigger("p1")


def test_ready_to_trigger_after_build_deploy_inspect(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    for stage in ("build", "deploy", "inspect"):
        run.record(stage, "p1")

    run.assert_ready_to_trigger("p1")


# ── uncertain create ──────────────────────────────────────────────────────


def test_a_completed_create_records_both_halves(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")

    with run.creating("p1") as created:
        created["id"] = 2684

    events = [r["event"] for r in run.journal_records()]
    assert events == ["build", "create_started", "create_response_persisted"]
    assert run.journal_records()[-1]["id"] == 2684


def test_a_create_whose_response_was_lost_blocks_the_next_run(tmp_path):
    """Retrying blind would duplicate the server-side object."""
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")
    with pytest.raises(ZeroDivisionError):
        with run.creating("p1"):
            raise ZeroDivisionError("connection dropped after POST")

    with pytest.raises(UncertainCreateError) as excinfo:
        StudyRun(tmp_path, run_id="v1.18").assert_no_uncertain_create()

    assert "p1" in str(excinfo.value)


def test_a_clean_journal_passes_the_uncertain_create_check(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    run.record("build", "p1")
    with run.creating("p1") as created:
        created["id"] = 2684

    run.assert_no_uncertain_create()


def test_triggering_is_refused_while_a_create_is_uncertain(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    for stage in ("build", "deploy", "inspect"):
        run.record(stage, "p1")
    with pytest.raises(ZeroDivisionError):
        with run.creating("p1"):
            raise ZeroDivisionError("dropped")

    with pytest.raises(UncertainCreateError):
        run.assert_ready_to_trigger("p1")


# ── the readback gate ─────────────────────────────────────────────────────


def test_readback_matching_the_prepared_design_passes(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")

    run.assert_definition_unchanged(
        "p1", prepared={"a": 1, "b": [2, 3]}, live={"b": [2, 3], "a": 1},
    )


def test_a_changed_live_definition_is_a_hard_stop(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")

    with pytest.raises(RuntimeError) as excinfo:
        run.assert_definition_unchanged(
            "p1", prepared={"a": 1}, live={"a": 2},
        )

    assert "p1" in str(excinfo.value)


def test_membership_order_is_not_a_difference(tmp_path):
    """No readback preserves member order; comparing lists would fail here."""
    run = StudyRun(tmp_path, run_id="v1.18")

    run.assert_definition_unchanged(
        "p1",
        prepared={"featureAnalyses": [77, 71, 74, 80, 49, 252]},
        live={"featureAnalyses": [49, 71, 74, 77, 80, 252]},
        unordered=("featureAnalyses",),
    )


def test_an_unordered_field_with_different_members_still_fails(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")

    with pytest.raises(RuntimeError):
        run.assert_definition_unchanged(
            "p1",
            prepared={"featureAnalyses": [77, 71]},
            live={"featureAnalyses": [77, 99]},
            unordered=("featureAnalyses",),
        )


# ── snapshots ─────────────────────────────────────────────────────────────


def test_a_snapshot_is_written_under_the_run_directory_and_journalled(tmp_path):
    run = StudyRun(tmp_path, run_id="v1.18")
    for stage in ("build", "deploy", "inspect", "trigger", "capture", "monitor"):
        run.record(stage, "p1")

    path = run.snapshot("p1", {"status": "COMPLETE", "isValid": True})

    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["isValid"] is True
    last = run.journal_records()[-1]
    assert last["event"] == "snapshot"

    # The journalled digest is over the file's own bytes, so it can be
    # rechecked against the file later. That is deliberately NOT
    # digest(payload), which hashes the canonical serialisation instead.
    import hashlib
    assert last["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert last["sha256"] != digest({"status": "COMPLETE", "isValid": True})


def test_two_snapshots_of_the_same_key_do_not_overwrite_each_other(tmp_path):
    """A historical file proves only its recorded run; keep both."""
    run = StudyRun(tmp_path, run_id="v1.18")
    for stage in ("build", "deploy", "inspect", "trigger", "capture", "monitor"):
        run.record(stage, "p1")

    first = run.snapshot("p1", {"status": "RUNNING"}, label="poll")
    second = run.snapshot("p1", {"status": "COMPLETE"}, label="poll")

    assert first != second
    assert first.is_file() and second.is_file()
