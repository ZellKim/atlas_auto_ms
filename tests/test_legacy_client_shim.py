"""Compatibility and migration checks for Characterization scripts."""

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATED_SCRIPTS = [
    REPOSITORY_ROOT / "data" / "scripts" / "create_char_v2.py",
    REPOSITORY_ROOT / "data" / "scripts" / "create_biomarker_fas_v2.py",
    REPOSITORY_ROOT / "data" / "scripts" / "deploy_char_17bio.py",
    REPOSITORY_ROOT / "data" / "scripts" / "deploy_char_multisite.py",
]
DIRECT_SESSION_CALL = re.compile(
    r"(?:client|c|session)\.session\.(?:get|post|put|delete)"
    r"|session\.(?:get|post|put|delete)"
)


def test_legacy_client_is_the_canonical_package_class():
    from atlas_auto import FedernetClient as CanonicalClient
    from automation.feedernet_client import FedernetClient as LegacyClient

    assert LegacyClient is CanonicalClient


def test_characterization_interfaces_are_publicly_exported():
    from atlas_auto import (
        AtlasApiError,
        CharacterizationService,
        DeploymentRecord,
        EnsureResult,
        GenerationResult,
        MultisiteCharacterizationDeployer,
        SiteTarget,
        select_latest_static_source,
        write_ledger,
    )

    assert all(
        item is not None
        for item in (
            AtlasApiError,
            CharacterizationService,
            DeploymentRecord,
            EnsureResult,
            GenerationResult,
            MultisiteCharacterizationDeployer,
            SiteTarget,
            select_latest_static_source,
            write_ledger,
        )
    )


def test_characterization_scripts_use_package_api_without_direct_http_calls():
    for script in MIGRATED_SCRIPTS:
        source = script.read_text(encoding="utf-8")
        assert "from atlas_auto import" in source, script
        assert DIRECT_SESSION_CALL.search(source) is None, script
