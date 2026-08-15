"""Contract tests for the shared cohort-generation wait.

`wait_for_cohort_generation` accepted a `source_key` and never used it, and
returned True on `status == "COMPLETE"` without reading `isValid`. That is the
AUMC 2026-08-15 failure. Eighteen fracture-treatment scripts hand-rolled the
guard instead of calling this, and a new study calling it would inherit the bug.
"""

import pytest

from atlas_auto.client import FedernetClient


class StubClient(FedernetClient):
    """A client whose two network reads are canned."""

    def __init__(self, snapshots, sources=None):
        # Deliberately skips FedernetClient.__init__: no session is needed.
        self.snapshots = list(snapshots)
        self.sources = list(sources or [])
        self.info_calls = 0

    def get_cohort_generation_info(self, cohort_id):
        self.info_calls += 1
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]

    def get_sources(self):
        return self.sources


SOURCES = [
    {"sourceKey": "cdmpv53m", "sourceId": 11},
    {"sourceKey": "cdmpv53_251128", "sourceId": 9},
]


def row(status="COMPLETE", is_valid=True, source_id=9, person_count=1864):
    return {
        "id": {"cohortDefinitionId": 2684, "sourceId": source_id},
        "status": status,
        "isValid": is_valid,
        "personCount": person_count,
    }


def test_complete_and_valid_returns_true():
    client = StubClient([[row()]], SOURCES)

    assert client.wait_for_cohort_generation(
        2684, "cdmpv53_251128", timeout=1, poll_interval=0,
    ) is True


def test_complete_but_invalid_returns_false():
    """AUMC: COMPLETE, isValid false, null personCount, after 2.2 hours."""
    client = StubClient([[row(is_valid=False, person_count=None)]], SOURCES)

    assert client.wait_for_cohort_generation(
        2684, "cdmpv53_251128", timeout=1, poll_interval=0,
    ) is False


def test_another_sources_success_is_not_reported_as_ours():
    """A multi-source site returns one row per source."""
    client = StubClient(
        [[row(source_id=11), row(source_id=9, status="FAILED")]], SOURCES,
    )

    assert client.wait_for_cohort_generation(
        2684, "cdmpv53_251128", timeout=1, poll_interval=0,
    ) is False


def test_it_waits_through_a_running_row_then_succeeds():
    client = StubClient([[row(status="RUNNING")], [row()]], SOURCES)

    assert client.wait_for_cohort_generation(
        2684, "cdmpv53_251128", timeout=5, poll_interval=0,
    ) is True
    assert client.info_calls == 2


def test_an_unknown_source_key_raises_rather_than_scanning_every_row():
    client = StubClient([[row()]], SOURCES)

    with pytest.raises(LookupError):
        client.wait_for_cohort_generation(
            2684, "not-a-source", timeout=1, poll_interval=0,
        )


def test_without_a_source_key_validity_is_still_required():
    client = StubClient([[row(is_valid=False)]], SOURCES)

    assert client.wait_for_cohort_generation(
        2684, timeout=1, poll_interval=0,
    ) is False


def test_timeout_returns_false_while_still_running():
    client = StubClient([[row(status="RUNNING")]], SOURCES)

    assert client.wait_for_cohort_generation(
        2684, "cdmpv53_251128", timeout=0, poll_interval=0,
    ) is False
