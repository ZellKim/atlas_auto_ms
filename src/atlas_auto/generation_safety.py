"""Guarded reads of cohort-generation status.

Established by a live failure at AUMC on 2026-08-15. Two cohorts returned::

    {"status": "COMPLETE", "personCount": null, "recordCount": null,
     "isValid": false, "executionDuration": 7949138}

after runs of 2.2 and 1.7 hours. A generation can finish and still be unusable,
so checking `status` alone reports it as done and publishes a cohort that
produced nothing.

Two conditions are required and both matter.

Validity
    `status in {"COMPLETE", "COMPLETED"}` **and** `isValid is True`. Absence of
    the flag is not truth, and a truthy string is not the flag.

Source scope
    A site with several CDM sources returns one row per source from
    `GET /cohortdefinition/{id}/info`. An unfiltered read can pick up a
    different source's result, so the row's `id.sourceId` must be the source
    being used. `resolve_source_id` refuses to guess: a source catalog entry
    with no `sourceId` raises rather than silently disabling the filter.

This lived in eighteen separate fracture-treatment scripts, hand-typed each
time, while the shared client had no check at all. Keeping it here is the point.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

SUCCESS_STATUSES = frozenset({"COMPLETE", "COMPLETED"})
FAILURE_STATUSES = frozenset(
    {"FAILED", "ERROR", "CANCELED", "CANCELLED", "STOPPED"}
)


class GenerationNotValidError(RuntimeError):
    """A generation is absent, unfinished, or finished without being usable."""


def generation_status(row: Optional[dict]) -> str:
    """Return the status name, tolerating the `{"name": ...}` object form."""
    if not row:
        return "UNKNOWN"
    raw = row.get("status", "UNKNOWN")
    if isinstance(raw, dict):
        raw = raw.get("name", "UNKNOWN")
    return str(raw).upper()


def is_usable_generation(row: Optional[dict]) -> bool:
    """True only for a finished generation whose result can be used."""
    if not row:
        return False
    return generation_status(row) in SUCCESS_STATUSES and row.get("isValid") is True


def is_finished_generation(row: Optional[dict]) -> bool:
    """True when the engine has stopped, whether or not the result is usable.

    A poller must stop on this, and then decide usability separately.
    """
    if not row:
        return False
    return generation_status(row) in SUCCESS_STATUSES | FAILURE_STATUSES


def source_id_of(row: Optional[dict]) -> Any:
    """Return the row's owning `id.sourceId`, or None when absent."""
    if not row:
        return None
    return (row.get("id") or {}).get("sourceId")


def rows_for_source(rows: Iterable[dict], source_id: Any) -> list:
    """Keep only the rows belonging to one CDM source."""
    return [row for row in rows or [] if source_id_of(row) == source_id]


def resolve_source_id(sources: Iterable[dict], source_key: str) -> Any:
    """Map a `sourceKey` to its numeric `sourceId`.

    Raises rather than returning None, because a missing id would disable the
    source filter and reintroduce the cross-source read this module exists to
    prevent.
    """
    catalog = list(sources or [])
    for source in catalog:
        if source.get("sourceKey") == source_key:
            source_id = source.get("sourceId")
            if source_id is None:
                raise LookupError(
                    f"source {source_key!r} has no sourceId; cannot scope "
                    f"generation rows to it"
                )
            return source_id
    available = [source.get("sourceKey") for source in catalog]
    raise LookupError(f"no source {source_key!r}; found {available}")


def usable_generation(
    rows: Iterable[dict], source_id: Any = None,
) -> Optional[dict]:
    """Return the first usable generation, scoped to one source when given."""
    candidates = list(rows or [])
    if source_id is not None:
        candidates = rows_for_source(candidates, source_id)
    for row in candidates:
        if is_usable_generation(row):
            return row
    return None


def finished_generation(
    rows: Iterable[dict], source_id: Any = None,
) -> Optional[dict]:
    """Return the first finished generation, usable or not."""
    candidates = list(rows or [])
    if source_id is not None:
        candidates = rows_for_source(candidates, source_id)
    for row in candidates:
        if is_finished_generation(row):
            return row
    return None


def assert_generation_valid(
    row: Optional[dict],
    *,
    cohort_id: Any = None,
    source_id: Any = None,
) -> dict:
    """Return the row, or raise explaining exactly which condition failed."""
    where = []
    if cohort_id is not None:
        where.append(f"cohort={cohort_id}")
    if source_id is not None:
        where.append(f"source={source_id}")
    context = f" ({', '.join(where)})" if where else ""

    if not row:
        raise GenerationNotValidError(
            f"no generation row{context}; an absent row is not a zero result"
        )
    status = generation_status(row)
    if status not in SUCCESS_STATUSES:
        raise GenerationNotValidError(
            f"generation{context} has status {status}, not a success status"
        )
    if row.get("isValid") is not True:
        raise GenerationNotValidError(
            f"generation{context} reported status {status} but isValid="
            f"{row.get('isValid')!r} with personCount="
            f"{row.get('personCount')!r}; COMPLETE alone is not success"
        )
    return row
