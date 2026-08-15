"""The generic half of a study run: journal, evidence, stage order, gates.

The required sequence is not a style preference. `docs/system_knowledge_base.md`
and the OHDSI guardrails both state it: deploy without executing, inspect the
deployed artifact, trigger the exact intended analysis, capture its execution
identifier, monitor that execution, and preserve raw current status snapshots.

Every study re-implemented that sequence. The one runner that did it properly,
`studies/fracture_treatment/scripts/run_khnmc_v1_11_nonestimation.py`, is 1,472
lines, and its generic half was then unavailable to v1.13 through v1.17 — each
of which was a fresh one-off script that rediscovered the WebAPI contract by
trial and error. This module is that generic half, promoted.

What it owns.

Stage order
    `record(stage, key)` refuses a stage whose predecessors are missing for that
    key, so "trigger" cannot happen before "inspect". Repeating a stage is fine;
    re-running after a fix is normal work, not an ordering violation.

The operation journal
    Append-only JSONL, flushed and fsynced per line, canonically serialised so
    the same event always produces the same bytes. It is the resume state: a new
    `StudyRun` over the same directory reads what the previous one did.

The uncertain create
    A create is journalled in two halves. If `create_started` is the last word
    for a key, the response was lost and the server may or may not hold the
    object. Retrying blind would duplicate it. `assert_no_uncertain_create`
    turns that into a hard stop demanding live reconciliation, and
    `assert_ready_to_trigger` refuses to proceed while one is outstanding.

Evidence files
    `write_evidence` writes with `newline="\\n"` and returns the digest **of the
    bytes it wrote**. `Path.write_text` translates LF to CRLF on Windows, so a
    digest taken over the in-memory string never matches its own file; that is
    how all 34 rows of both published `INDEX.csv` files failed on 2026-08-15.
    Writes are atomic, so an interrupted run never leaves a half file.

The readback gate
    `assert_definition_unchanged` fails closed when the live definition no
    longer equals the prepared one. Fields named in `unordered` compare as
    multisets, because no WebAPI readback preserves member order.

What it deliberately does not own: anything study-specific. It does not decide
what to build, which analyses exist, or how to interpret a result. Those belong
to the study's own thin driver, the same way `R/lib/ipd_pooled.R` leaves the
driver to the study.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

STAGES: tuple[str, ...] = (
    "build",     # produce the definition locally; no server contact
    "deploy",    # import or create it; never execute in the same step
    "inspect",   # read the deployed artifact back and compare
    "trigger",   # start the exact intended analysis
    "capture",   # record the execution identifier it returned
    "monitor",   # poll that identifier
    "snapshot",  # preserve the raw current status
)

JOURNAL_NAME = "operation_journal.jsonl"
CREATE_STARTED = "create_started"
CREATE_PERSISTED = "create_response_persisted"


class StageOrderError(RuntimeError):
    """A stage was reached before one of its prerequisites."""


class UncertainCreateError(RuntimeError):
    """A create was started and its response never recorded."""


def canonical_json(value: Any) -> str:
    """Serialise so that equal values always produce equal bytes."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    """sha256 over the canonical serialisation of a value."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_evidence(path: Path | str, payload: Any) -> str:
    """Atomically write one evidence file; return the digest of its bytes.

    The digest is taken over what landed on disk, not over the in-memory value,
    so a published digest can always be rechecked against the file itself.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unordered_view(value: Any) -> Any:
    """Compare a member list as a multiset, since readback order is arbitrary."""
    if isinstance(value, (list, tuple)):
        return Counter(canonical_json(item) for item in value)
    return value


class StudyRun:
    """One study version's run over one output directory."""

    def __init__(self, output_dir: Path | str, *, run_id: str):
        self.output_dir = Path(output_dir)
        self.run_id = run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── journal ───────────────────────────────────────────────────────────

    @property
    def journal_path(self) -> Path:
        return self.output_dir / JOURNAL_NAME

    def journal_records(self) -> list[dict[str, Any]]:
        """Every event written for this directory, oldest first."""
        if not self.journal_path.exists():
            return []
        records: list[dict[str, Any]] = []
        lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"operation journal is truncated at line {number}; "
                    f"the run state is uncertain and must be reconciled live"
                ) from exc
            if not isinstance(item, dict):
                raise RuntimeError(
                    f"operation journal line {number} is not an object; "
                    f"the run state is uncertain"
                )
            records.append(item)
        return records

    def _append(self, event: str, key: str, **values: Any) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event": event,
            "key": key,
            **copy.deepcopy(values),
        }
        with self.journal_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical_json(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return record

    # ── stage order ───────────────────────────────────────────────────────

    def completed(self, stage: str, key: str) -> bool:
        """Whether this key already reached this stage in this directory."""
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
        return any(
            record.get("event") == stage and record.get("key") == key
            for record in self.journal_records()
        )

    def record(self, stage: str, key: str, **values: Any) -> dict[str, Any]:
        """Journal that `key` reached `stage`, refusing an out-of-order jump."""
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
        done = {
            record["event"]
            for record in self.journal_records()
            if record.get("key") == key
        }
        for earlier in STAGES[: STAGES.index(stage)]:
            if earlier not in done:
                raise StageOrderError(
                    f"{key} cannot reach {stage!r} before {earlier!r}; "
                    f"the required sequence is {' -> '.join(STAGES)}"
                )
        return self._append(stage, key, **values)

    # ── gates ─────────────────────────────────────────────────────────────

    def assert_no_uncertain_create(self, keys: Iterable[str] | None = None) -> None:
        """Stop when any create was started without its response recorded."""
        records = self.journal_records()
        seen = [record.get("key") for record in records]
        candidates = list(keys) if keys is not None else sorted(
            {key for key in seen if key is not None}
        )
        for key in candidates:
            started = persisted = -1
            for index, record in enumerate(records):
                if record.get("key") != key:
                    continue
                if record.get("event") == CREATE_STARTED:
                    started = index
                elif record.get("event") == CREATE_PERSISTED:
                    persisted = index
            if started > persisted:
                raise UncertainCreateError(
                    f"create state for {key!r} is uncertain: the request was "
                    f"journalled but no response was. The server may or may not "
                    f"hold the object; reconcile live state before retrying, "
                    f"because a blind retry would duplicate it"
                )

    def assert_ready_to_trigger(self, key: str) -> None:
        """Refuse to execute anything that was not built, deployed and inspected."""
        self.assert_no_uncertain_create([key])
        for stage in ("build", "deploy", "inspect"):
            if not self.completed(stage, key):
                raise StageOrderError(
                    f"{key} is not ready to trigger: {stage!r} has not been "
                    f"recorded. A deploy acknowledgement is not proof that the "
                    f"deployed artifact is the one you designed"
                )

    def assert_definition_unchanged(
        self,
        key: str,
        *,
        prepared: Mapping[str, Any],
        live: Mapping[str, Any],
        unordered: Iterable[str] = (),
    ) -> None:
        """Fail closed when the live definition no longer equals the prepared one.

        Fields named in `unordered` compare as multisets. No WebAPI readback
        preserves member order: the same six feature analyses came back as
        `[74, 77, 71, 80, 252, 49]` from create and `[49, 71, 74, 77, 80, 252]`
        from export against a requested `[77, 71, 74, 80, 49, 252]`.
        """
        unordered = set(unordered)

        def view(payload: Mapping[str, Any]) -> dict[str, Any]:
            return {
                name: (_unordered_view(value) if name in unordered else value)
                for name, value in payload.items()
            }

        if view(prepared) != view(live):
            raise RuntimeError(
                f"{key} live definition does not equal the prepared design; "
                f"prepared digest={digest(dict(prepared))} "
                f"live digest={digest(dict(live))}"
            )

    # ── create protection ─────────────────────────────────────────────────

    @contextmanager
    def creating(self, key: str, **values: Any):
        """Journal a create in two halves so a lost response is not retried blind.

        Yields a dict; whatever the body puts in it is journalled with the
        response half. If the body raises, only the started half exists, and the
        next run stops at `assert_no_uncertain_create`.
        """
        self._append(CREATE_STARTED, key, **values)
        response: dict[str, Any] = {}
        yield response
        self._append(CREATE_PERSISTED, key, **response)

    # ── snapshots ─────────────────────────────────────────────────────────

    def snapshot(self, key: str, payload: Any, *, label: str | None = None) -> Path:
        """Preserve a raw current status payload and journal its digest.

        A historical state file proves only its recorded run, so each snapshot is
        written once under its own name and never overwritten in place.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        name = f"{key}__{label}__{stamp}.json" if label else f"{key}__{stamp}.json"
        path = self.output_dir / "snapshots" / name
        sha = write_evidence(path, payload)
        self._append(
            "snapshot",
            key,
            path=str(path.relative_to(self.output_dir)),
            sha256=sha,
        )
        return path
