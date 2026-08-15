"""Reusable single-site Feature Analysis and Characterization workflows."""

import copy
import logging
import time
from dataclasses import dataclass


logger = logging.getLogger(__name__)


class CharacterizationResultCountError(RuntimeError):
    """The result list is shorter than the count the server reported.

    A trimmed list is missing rows, and a missing row reads as a zero
    downstream, which produces a plausible but wrong table. Fail instead.
    """


@dataclass(frozen=True)
class EnsureResult:
    """The resource selected or created by an ensure operation."""

    resource: dict
    reused: bool


@dataclass(frozen=True)
class GenerationResult:
    """A generation and the lifecycle action taken for it."""

    generation: dict
    action: str


class CharacterizationService:
    """Coordinate Characterization assets and generations for one site."""

    def __init__(self, client):
        self.client = client

    @staticmethod
    def _find_latest_exact_name(resources, name, resource_kind="resource"):
        matches = [item for item in resources if item.get("name") == name]
        if not matches:
            return None

        numeric_matches = []
        for item in matches:
            try:
                numeric_matches.append((int(item["id"]), item))
            except (KeyError, TypeError, ValueError):
                continue
        if not numeric_matches:
            raise ValueError(
                f"Exact-name {resource_kind} matches have no numeric id: {name!r}"
            )

        if len(matches) > 1:
            logger.warning(
                "Duplicate exact-name %s assets found for %r; reusing largest numeric id",
                resource_kind,
                name,
            )
        return max(numeric_matches, key=lambda pair: pair[0])[1]

    def ensure_feature_analysis(
        self,
        name,
        template_id,
        prepare_first,
        prepare_second=None,
        reuse_existing=True,
        search_size=2000,
    ):
        """Reuse an exact-name FA or create one through copy and one/two PUTs."""
        if reuse_existing:
            existing = self._find_latest_exact_name(
                self.client.list_feature_analyses(size=search_size),
                name,
                "Feature Analysis",
            )
            if existing is not None:
                return EnsureResult(resource=existing, reused=True)

        copied = self.client.copy_feature_analysis(template_id)
        try:
            new_id = int(copied["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Copied Feature Analysis has no numeric id") from exc

        try:
            first_payload = prepare_first(copy.deepcopy(copied))
            if not isinstance(first_payload, dict):
                raise TypeError("prepare_first must return a dict")
            first_payload["id"] = new_id
            first_payload["name"] = name
            updated = self.client.update_feature_analysis(new_id, first_payload)

            if prepare_second is not None:
                second_payload = prepare_second(copy.deepcopy(updated))
                if not isinstance(second_payload, dict):
                    raise TypeError("prepare_second must return a dict")
                second_payload["id"] = new_id
                second_payload["name"] = name
                updated = self.client.update_feature_analysis(new_id, second_payload)
            return EnsureResult(resource=updated, reused=False)
        except Exception:
            try:
                self.client.delete_feature_analysis(new_id)
            except Exception as cleanup_error:
                logger.warning(
                    "Could not clean up failed Feature Analysis copy id=%s: %s",
                    new_id,
                    cleanup_error,
                )
            raise

    def ensure_created_characterization(
        self, spec, reuse_existing=True, search_size=2000,
    ):
        """Reuse an exact-name Characterization or create it from a design."""
        payload = copy.deepcopy(spec)
        name = payload["name"]
        if reuse_existing:
            existing = self._find_latest_exact_name(
                self.client.list_characterizations(size=search_size),
                name,
                "Characterization",
            )
            if existing is not None:
                return EnsureResult(resource=existing, reused=True)
        return EnsureResult(
            resource=self.client.create_characterization(payload),
            reused=False,
        )

    def ensure_imported_characterization(
        self, export_spec, name, reuse_existing=True, search_size=2000,
    ):
        """Reuse an exact-name Characterization or import a copied export."""
        if reuse_existing:
            existing = self._find_latest_exact_name(
                self.client.list_characterizations(size=search_size),
                name,
                "Characterization",
            )
            if existing is not None:
                return EnsureResult(resource=existing, reused=True)

        payload = copy.deepcopy(export_spec)
        payload.pop("id", None)
        payload["name"] = name
        return EnsureResult(
            resource=self.client.import_characterization(payload),
            reused=False,
        )

    @staticmethod
    def _generation_source_key(generation):
        for key in ("sourceKey", "source_key"):
            value = generation.get(key)
            if value is not None:
                return str(value)
        source = generation.get("source")
        if isinstance(source, str):
            return source
        if isinstance(source, dict):
            for key in ("sourceKey", "source_key", "key"):
                value = source.get(key)
                if value is not None:
                    return str(value)
        return None

    @staticmethod
    def _generation_status(generation):
        status = generation.get("status")
        if isinstance(status, dict):
            status = status.get("name", status.get("value"))
        if status is None:
            return "UNKNOWN"
        return str(status).upper()

    @classmethod
    def _latest_generation_for_source(cls, generations, source_key):
        matches = []
        for generation in generations:
            if cls._generation_source_key(generation) != str(source_key):
                continue
            try:
                generation_id = int(generation["id"])
            except (KeyError, TypeError, ValueError):
                continue
            matches.append((generation_id, generation))
        if not matches:
            return None
        return max(matches, key=lambda pair: pair[0])[1]

    def _start_generation(self, characterization_id, source_key):
        generation = self.client.generate_characterization(
            characterization_id, source_key,
        )
        return GenerationResult(generation=generation, action="STARTED")

    def run_or_reuse(self, characterization_id, source_key, force=False):
        """Reuse, wait for, or start a generation based on its newest state."""
        if force:
            return self._start_generation(characterization_id, source_key)

        generations = self.client.get_characterization_generations(
            characterization_id,
        )
        latest = self._latest_generation_for_source(generations, source_key)
        if latest is None:
            return self._start_generation(characterization_id, source_key)

        status = self._generation_status(latest)
        if status == "COMPLETE":
            return GenerationResult(generation=latest, action="REUSED")
        if status in {"PENDING", "RUNNING"}:
            return GenerationResult(generation=latest, action="WAITING")
        if status in {"ERROR", "FAILED", "CANCELED"}:
            return self._start_generation(characterization_id, source_key)
        raise ValueError(f"Unknown Characterization generation status: {status}")

    def wait_for_generation(
        self,
        characterization_id,
        source_key,
        timeout=3600,
        poll_interval=10,
    ):
        """Wait for the newest same-source generation to complete."""
        deadline = time.monotonic() + timeout
        while True:
            generations = self.client.get_characterization_generations(
                characterization_id,
            )
            latest = self._latest_generation_for_source(generations, source_key)
            if latest is not None:
                status = self._generation_status(latest)
                if status == "COMPLETE":
                    return latest
                if status in {"ERROR", "FAILED", "CANCELED"}:
                    raise RuntimeError(
                        f"Characterization generation ended with {status}"
                    )
                if status not in {"PENDING", "RUNNING"}:
                    raise ValueError(
                        f"Unknown Characterization generation status: {status}"
                    )

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Timed out waiting for Characterization "
                    f"id={characterization_id} source={source_key}"
                )
            time.sleep(max(0, poll_interval))

    def collect_results(self, generation_id):
        """Fetch the count and then the complete WebAPI 2.12 result list."""
        expected_count = self.client.get_characterization_result_count(generation_id)
        results = self.client.get_characterization_results(
            generation_id, threshold_level=0,
        )
        logger.info(
            "Collected %s Characterization results for generation id=%s "
            "(reported count=%s)",
            len(results),
            generation_id,
            expected_count,
        )
        if len(results) != expected_count:
            raise CharacterizationResultCountError(
                f"Characterization result count mismatch for generation "
                f"id={generation_id}: reported={expected_count} "
                f"received={len(results)}"
            )
        return results
