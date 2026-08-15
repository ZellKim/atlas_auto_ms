"""Contract tests for cohort-generation validity.

Every case here is a live failure, not a hypothetical. The anchor is AUMC on
2026-08-15, where two cohorts returned `status: COMPLETE` with `isValid: false`
and a null `personCount` after runs of 2.2 and 1.7 hours.
"""

import pytest

from atlas_auto.generation_safety import (
    GenerationNotValidError,
    assert_generation_valid,
    is_finished_generation,
    is_usable_generation,
    resolve_source_id,
    rows_for_source,
    usable_generation,
)


def row(status="COMPLETE", is_valid=True, source_id=9, person_count=1864):
    return {
        "id": {"cohortDefinitionId": 2684, "sourceId": source_id},
        "status": status,
        "isValid": is_valid,
        "personCount": person_count,
    }


# ── status normalisation ──────────────────────────────────────────────────


def test_complete_and_valid_is_usable():
    assert is_usable_generation(row()) is True


def test_completed_spelling_is_also_success():
    assert is_usable_generation(row(status="COMPLETED")) is True


def test_status_object_form_is_read_by_name():
    """Some deployments return status as {"name": ...} rather than a string."""
    entry = row()
    entry["status"] = {"name": "COMPLETE"}
    assert is_usable_generation(entry) is True


# ── the AUMC trap ─────────────────────────────────────────────────────────


def test_complete_but_invalid_is_not_usable():
    assert is_usable_generation(row(is_valid=False, person_count=None)) is False


def test_missing_is_valid_is_not_usable():
    """Absence is not truth. An unreported flag must not read as valid."""
    entry = row()
    del entry["isValid"]
    assert is_usable_generation(entry) is False


def test_truthy_non_true_is_valid_is_not_usable():
    """`isValid` must be the boolean True, not merely truthy."""
    assert is_usable_generation(row(is_valid="true")) is False


def test_complete_but_invalid_still_counts_as_finished():
    """It is done. It is just not usable, so a poller must stop waiting."""
    entry = row(is_valid=False)
    assert is_finished_generation(entry) is True
    assert is_usable_generation(entry) is False


@pytest.mark.parametrize(
    "status", ["FAILED", "ERROR", "CANCELED", "CANCELLED", "STOPPED"],
)
def test_failure_statuses_are_finished_and_unusable(status):
    entry = row(status=status)
    assert is_finished_generation(entry) is True
    assert is_usable_generation(entry) is False


@pytest.mark.parametrize("status", ["RUNNING", "PENDING", "STARTED"])
def test_in_flight_statuses_are_not_finished(status):
    assert is_finished_generation(row(status=status)) is False


# ── source scoping ────────────────────────────────────────────────────────


def test_rows_are_scoped_to_one_source():
    """A site with several CDM sources returns one row per source."""
    rows = [row(source_id=3, status="FAILED"), row(source_id=9)]

    assert rows_for_source(rows, 9) == [rows[1]]


def test_usable_generation_ignores_another_sources_success():
    rows = [row(source_id=3), row(source_id=9, is_valid=False)]

    assert usable_generation(rows, source_id=9) is None


def test_usable_generation_returns_the_matching_row():
    rows = [row(source_id=3, status="FAILED"), row(source_id=9)]

    assert usable_generation(rows, source_id=9) is rows[1]


def test_unscoped_usable_generation_accepts_any_source():
    assert usable_generation([row(source_id=3)]) is not None


def test_resolve_source_id_maps_a_source_key():
    sources = [
        {"sourceKey": "cdmpv53m", "sourceId": 11},
        {"sourceKey": "cdmpv53_251128", "sourceId": 9},
    ]

    assert resolve_source_id(sources, "cdmpv53_251128") == 9


def test_resolve_source_id_rejects_an_unknown_key():
    sources = [{"sourceKey": "cdmpv53m", "sourceId": 11}]

    with pytest.raises(LookupError) as excinfo:
        resolve_source_id(sources, "cdmpv53_251128")

    assert "cdmpv53_251128" in str(excinfo.value)
    assert "cdmpv53m" in str(excinfo.value)


def test_resolve_source_id_rejects_a_record_without_a_source_id():
    """Guessing here would silently disable the whole source filter."""
    sources = [{"sourceKey": "cdmpv53_251128"}]

    with pytest.raises(LookupError):
        resolve_source_id(sources, "cdmpv53_251128")


# ── the assertion form ────────────────────────────────────────────────────


def test_assert_generation_valid_returns_the_row_when_usable():
    entry = row()
    assert assert_generation_valid(entry) is entry


def test_assert_generation_valid_raises_on_complete_but_invalid():
    with pytest.raises(GenerationNotValidError) as excinfo:
        assert_generation_valid(row(is_valid=False, person_count=None))

    message = str(excinfo.value)
    assert "COMPLETE" in message
    assert "isValid" in message


def test_assert_generation_valid_raises_on_no_row_at_all():
    with pytest.raises(GenerationNotValidError):
        assert_generation_valid(None)
