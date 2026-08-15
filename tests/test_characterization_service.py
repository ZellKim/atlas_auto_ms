"""Tests for the single-site Characterization lifecycle service."""

import pytest

from atlas_auto.characterization import (
    CharacterizationResultCountError,
    CharacterizationService,
)


class RecordingClient:
    def __init__(self, feature_analyses=None, characterizations=None):
        self.feature_analyses = list(feature_analyses or [])
        self.characterizations = list(characterizations or [])
        self.calls = []
        self.update_count = 0
        self.fail_update_call = None

    def list_feature_analyses(self, size=200):
        self.calls.append(("list_feature_analyses", size))
        return self.feature_analyses

    def copy_feature_analysis(self, feature_analysis_id):
        self.calls.append(("copy_feature_analysis", feature_analysis_id))
        return {"id": 901, "name": "copy", "nested": {"value": "original"}}

    def update_feature_analysis(self, feature_analysis_id, payload):
        self.calls.append(("update_feature_analysis", feature_analysis_id, payload))
        self.update_count += 1
        if self.update_count == self.fail_update_call:
            raise RuntimeError("update failed")
        return dict(payload)

    def delete_feature_analysis(self, feature_analysis_id):
        self.calls.append(("delete_feature_analysis", feature_analysis_id))

    def list_characterizations(self, size=200):
        self.calls.append(("list_characterizations", size))
        return self.characterizations

    def create_characterization(self, spec):
        self.calls.append(("create_characterization", spec))
        return {**spec, "id": 121}

    def import_characterization(self, spec):
        self.calls.append(("import_characterization", spec))
        return {**spec, "id": 122}


def test_existing_feature_analysis_is_reused_without_copy():
    client = RecordingClient(
        feature_analyses=[{"id": 900, "name": "[B17] WBC_Pre365"}]
    )
    service = CharacterizationService(client)

    result = service.ensure_feature_analysis(
        "[B17] WBC_Pre365", 372, lambda payload: payload
    )

    assert result.reused is True
    assert result.resource["id"] == 900
    assert client.calls == [("list_feature_analyses", 2000)]


def test_duplicate_exact_names_reuse_largest_numeric_id(caplog):
    client = RecordingClient(
        feature_analyses=[
            {"id": "899", "name": "same"},
            {"id": 901, "name": "same"},
            {"id": 999, "name": "same prefix"},
        ]
    )
    service = CharacterizationService(client)

    result = service.ensure_feature_analysis("same", 372, lambda payload: payload)

    assert result.resource["id"] == 901
    assert "duplicate" in caplog.text.lower()


def test_new_feature_analysis_uses_copy_then_two_updates():
    client = RecordingClient(feature_analyses=[])
    service = CharacterizationService(client)
    copied_nested = None

    def prepare_first(payload):
        nonlocal copied_nested
        copied_nested = payload["nested"]
        payload["nested"]["value"] = "phase-1"
        payload["phase"] = 1
        return payload

    result = service.ensure_feature_analysis(
        "[B17] WBC_Pre365",
        372,
        prepare_first,
        lambda payload: {**payload, "phase": 2},
    )

    assert result.reused is False
    assert result.resource["phase"] == 2
    assert [call[0] for call in client.calls] == [
        "list_feature_analyses",
        "copy_feature_analysis",
        "update_feature_analysis",
        "update_feature_analysis",
    ]
    first_payload = client.calls[2][2]
    assert first_payload["name"] == "[B17] WBC_Pre365"
    assert copied_nested == {"value": "phase-1"}


def test_feature_analysis_callbacks_cannot_drop_or_replace_copied_id():
    client = RecordingClient(feature_analyses=[])
    service = CharacterizationService(client)

    result = service.ensure_feature_analysis(
        "stable id",
        372,
        lambda _payload: {"id": 123, "phase": 1},
        lambda _payload: {"phase": 2},
    )

    assert client.calls[2][2]["id"] == 901
    assert client.calls[3][2]["id"] == 901
    assert result.resource["id"] == 901


def test_failed_second_feature_analysis_update_cleans_up_new_copy():
    client = RecordingClient(feature_analyses=[])
    client.fail_update_call = 2
    service = CharacterizationService(client)

    with pytest.raises(RuntimeError, match="update failed"):
        service.ensure_feature_analysis(
            "new FA",
            372,
            lambda payload: payload,
            lambda payload: payload,
        )

    assert client.calls[-1] == ("delete_feature_analysis", 901)
    assert sum(call[0] == "delete_feature_analysis" for call in client.calls) == 1


def test_ensure_created_characterization_reuses_exact_name():
    client = RecordingClient(characterizations=[{"id": 120, "name": "existing"}])
    service = CharacterizationService(client)

    result = service.ensure_created_characterization({"name": "existing"})

    assert result.reused is True
    assert result.resource["id"] == 120
    assert [call[0] for call in client.calls] == ["list_characterizations"]


def test_ensure_imported_characterization_deep_copies_and_sets_name():
    export_spec = {"name": "source", "design": {"cohorts": [1]}}
    client = RecordingClient()
    service = CharacterizationService(client)

    result = service.ensure_imported_characterization(export_spec, "target")

    assert result.reused is False
    assert result.resource["name"] == "target"
    assert export_spec["name"] == "source"
    assert client.calls[-1][0] == "import_characterization"


class GenerationClient:
    def __init__(self, generation_snapshots=None, generated=None):
        self.generation_snapshots = list(generation_snapshots or [[]])
        self.generated = generated or {"executionId": 808}
        self.calls = []
        self.result_count = 0
        self.results = []

    def get_characterization_generations(self, characterization_id):
        self.calls.append(("get_characterization_generations", characterization_id))
        if len(self.generation_snapshots) > 1:
            return self.generation_snapshots.pop(0)
        return self.generation_snapshots[0]

    def generate_characterization(self, characterization_id, source_key):
        self.calls.append(("generate_characterization", characterization_id, source_key))
        return self.generated

    def get_characterization_result_count(self, generation_id):
        self.calls.append(("get_characterization_result_count", generation_id))
        return self.result_count

    def get_characterization_results(self, generation_id, threshold_level=0.01):
        self.calls.append(("get_characterization_results", generation_id))
        self.requested_threshold = threshold_level
        return self.results


def generation(status, generation_id=77, source_key="cdm"):
    return {"id": generation_id, "sourceKey": source_key, "status": status}


@pytest.mark.parametrize(
    "status,expected_action,should_generate",
    [
        ("COMPLETE", "REUSED", False),
        ("PENDING", "WAITING", False),
        ("RUNNING", "WAITING", False),
        ("ERROR", "STARTED", True),
        ("FAILED", "STARTED", True),
        ("CANCELED", "STARTED", True),
    ],
)
def test_run_or_reuse_follows_generation_state(
    status, expected_action, should_generate
):
    client = GenerationClient(
        [[generation("COMPLETE", 999, "other"), generation(status)]]
    )
    service = CharacterizationService(client)

    result = service.run_or_reuse(121, "cdm")

    assert result.action == expected_action
    assert result.generation == (client.generated if should_generate else generation(status))
    assert any(call[0] == "generate_characterization" for call in client.calls) is should_generate


def test_run_or_reuse_accepts_status_object_and_uses_newest_numeric_id():
    client = GenerationClient(
        [[
            generation("COMPLETE", 76),
            generation({"name": "RUNNING"}, 78),
        ]]
    )
    service = CharacterizationService(client)

    result = service.run_or_reuse(121, "cdm")

    assert result.action == "WAITING"
    assert result.generation["id"] == 78


def test_run_or_reuse_starts_when_no_generation_exists():
    client = GenerationClient([[]])
    service = CharacterizationService(client)

    result = service.run_or_reuse(121, "cdm")

    assert result.action == "STARTED"
    assert client.calls[-1] == ("generate_characterization", 121, "cdm")


def test_run_or_reuse_unknown_state_never_generates():
    client = GenerationClient([[generation("MYSTERY")]])
    service = CharacterizationService(client)

    with pytest.raises(ValueError, match="MYSTERY"):
        service.run_or_reuse(121, "cdm")

    assert not any(call[0] == "generate_characterization" for call in client.calls)


def test_run_or_reuse_force_always_starts_new_generation():
    client = GenerationClient([[generation("COMPLETE")]])
    service = CharacterizationService(client)

    result = service.run_or_reuse(121, "cdm", force=True)

    assert result.action == "STARTED"
    assert client.calls[-1] == ("generate_characterization", 121, "cdm")


def test_wait_for_generation_polls_until_complete(monkeypatch):
    client = GenerationClient(
        [
            [generation("PENDING")],
            [generation("RUNNING")],
            [generation("COMPLETE")],
        ]
    )
    service = CharacterizationService(client)
    monkeypatch.setattr("atlas_auto.characterization.time.sleep", lambda _seconds: None)

    result = service.wait_for_generation(121, "cdm", timeout=30, poll_interval=0)

    assert result["status"] == "COMPLETE"
    assert sum(call[0] == "get_characterization_generations" for call in client.calls) == 3


@pytest.mark.parametrize("status", ["ERROR", "FAILED", "CANCELED"])
def test_wait_for_generation_raises_for_terminal_failure(status):
    client = GenerationClient([[generation(status)]])
    service = CharacterizationService(client)

    with pytest.raises(RuntimeError, match=status):
        service.wait_for_generation(121, "cdm", timeout=30, poll_interval=0)


def test_wait_for_generation_rejects_unknown_state():
    client = GenerationClient([[generation("MYSTERY")]])
    service = CharacterizationService(client)

    with pytest.raises(ValueError, match="MYSTERY"):
        service.wait_for_generation(121, "cdm", timeout=30, poll_interval=0)


def test_wait_for_generation_times_out_after_observing_running():
    client = GenerationClient([[generation("RUNNING")]])
    service = CharacterizationService(client)

    with pytest.raises(TimeoutError):
        service.wait_for_generation(121, "cdm", timeout=0, poll_interval=0)

    assert client.calls == [("get_characterization_generations", 121)]


def test_collect_results_reads_count_then_single_full_result_list():
    client = GenerationClient()
    client.result_count = 2
    client.results = [{"featureId": 1}, {"featureId": 2}]
    service = CharacterizationService(client)

    results = service.collect_results(77)

    assert results == client.results
    assert client.calls == [
        ("get_characterization_result_count", 77),
        ("get_characterization_results", 77),
    ]


def test_collect_results_requests_the_unthresholded_list():
    """thresholdLevel 0.01 silently drops sub-1% covariates (KHNMC 2026-08-14)."""
    client = GenerationClient()
    client.result_count = 2
    client.results = [{"featureId": 1}, {"featureId": 2}]
    service = CharacterizationService(client)

    service.collect_results(77)

    assert client.requested_threshold == 0


def test_collect_results_raises_when_the_server_count_is_not_met():
    """A short list is missing rows, and missing rows read as zero downstream."""
    client = GenerationClient()
    client.result_count = 57
    client.results = [{"featureId": 1}]
    service = CharacterizationService(client)

    with pytest.raises(CharacterizationResultCountError) as excinfo:
        service.collect_results(77)

    assert "57" in str(excinfo.value)
    assert "1" in str(excinfo.value)
