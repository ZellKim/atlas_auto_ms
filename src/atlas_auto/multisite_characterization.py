"""Sequential, resumable multisite Characterization deployment helpers."""

import copy
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .characterization import CharacterizationService


_DATED_STATIC_SUFFIX = re.compile(r"_(\d+)$")
_SECRET_VALUE = re.compile(
    r"(?i)\b(password|authorization|cookie|token)\b(\s*[:=]\s*)(\S+)"
)


@dataclass(frozen=True)
class SiteTarget:
    group_id: int
    site_id: int
    code: str
    name: str


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

    def to_dict(self):
        return asdict(self)


def select_latest_static_source(sources):
    """Select the largest dated static source using the established rule."""
    dated = []
    for source in sources:
        source_name = str(source.get("sourceName", ""))
        lowered = source_name.lower()
        if "monthly" in lowered or "weekly" in lowered:
            continue
        match = _DATED_STATIC_SUFFIX.search(source_name)
        if match:
            dated.append((int(match.group(1)), source))
    if dated:
        return max(dated, key=lambda pair: pair[0])[1]
    return sources[-1] if sources else None


def _short_safe_error(error):
    message = " ".join(str(error).split())
    message = _SECRET_VALUE.sub(r"\1\2<redacted>", message)
    return message[:240] or type(error).__name__


def _numeric_identifier(payload):
    if not isinstance(payload, dict):
        return None
    value = payload.get("id")
    if value is None:
        value = payload.get("executionId")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class MultisiteCharacterizationDeployer:
    """Deploy sequentially and isolate failures to one site at a time."""

    def deploy(
        self,
        export_spec,
        targets,
        client_factory,
        name_factory,
        source_selector=select_latest_static_source,
        prepare_site=None,
        reuse_existing=True,
        wait=False,
    ):
        records = []
        for target in targets:
            characterization_id = None
            generation_id = None
            source_key = None
            source_name = None
            try:
                client = client_factory(target)
                if not client.connect_site(target.group_id, target.site_id):
                    raise RuntimeError("Could not connect to target site")

                source = source_selector(client.get_sources())
                if source is None:
                    raise RuntimeError("No data source is available")
                source_key = str(source["sourceKey"])
                source_name = str(source.get("sourceName", source_key))

                service = CharacterizationService(client)
                ensured = service.ensure_imported_characterization(
                    copy.deepcopy(export_spec),
                    name_factory(target),
                    reuse_existing=reuse_existing,
                )
                characterization_id = int(ensured.resource["id"])

                if prepare_site is not None:
                    prepare_site(client, source_key, target)

                generation_result = service.run_or_reuse(
                    characterization_id, source_key,
                )
                generation_id = _numeric_identifier(generation_result.generation)
                status = {
                    "REUSED": "REUSED",
                    "WAITING": "STARTED",
                    "STARTED": "STARTED",
                }[generation_result.action]

                if wait and generation_result.action != "REUSED":
                    completed = service.wait_for_generation(
                        characterization_id, source_key,
                    )
                    generation_id = _numeric_identifier(completed)
                    status = "COMPLETE"

                records.append(
                    DeploymentRecord(
                        code=target.code,
                        group_id=target.group_id,
                        site_id=target.site_id,
                        status=status,
                        characterization_id=characterization_id,
                        generation_id=generation_id,
                        source_key=source_key,
                        source_name=source_name,
                    )
                )
            except Exception as error:
                records.append(
                    DeploymentRecord(
                        code=target.code,
                        group_id=target.group_id,
                        site_id=target.site_id,
                        status="FAILED",
                        characterization_id=characterization_id,
                        generation_id=generation_id,
                        source_key=source_key,
                        source_name=source_name,
                        error=_short_safe_error(error),
                    )
                )
        return records


def write_ledger(records, output_path):
    """Atomically write deployment records as UTF-8 JSON."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(f"{output}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                [record.to_dict() for record in records],
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output
