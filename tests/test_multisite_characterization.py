"""Tests for sequential multisite Characterization deployment."""

import json
from pathlib import Path

from atlas_auto.multisite_characterization import (
    DeploymentRecord,
    MultisiteCharacterizationDeployer,
    SiteTarget,
    select_latest_static_source,
    write_ledger,
)


def test_select_latest_static_source_excludes_periodic_and_uses_highest_suffix():
    sources = [
        {"sourceName": "CDM monthly_999999", "sourceKey": "monthly"},
        {"sourceName": "CDM_static_250101", "sourceKey": "old"},
        {"sourceName": "CDM weekly_999998", "sourceKey": "weekly"},
        {"sourceName": "CDM_static_251128", "sourceKey": "new"},
    ]

    assert select_latest_static_source(sources)["sourceKey"] == "new"


def test_select_latest_static_source_falls_back_to_last_and_handles_empty():
    sources = [
        {"sourceName": "CDM alpha", "sourceKey": "a"},
        {"sourceName": "CDM beta", "sourceKey": "b"},
    ]

    assert select_latest_static_source(sources) == sources[-1]
    assert select_latest_static_source([]) is None


class FakeSiteClient:
    def __init__(self, target, fail=False, existing=False, wait=False):
        self.target = target
        self.fail = fail
        self.existing = existing
        self.wait = wait
        self.calls = []
        self.generation_reads = 0

    def connect_site(self, group_id, site_id):
        self.calls.append(("connect_site", group_id, site_id))
        return True

    def get_sources(self):
        self.calls.append(("get_sources",))
        if self.fail:
            raise RuntimeError("password=do-not-leak token: hidden")
        return [
            {
                "sourceName": f"{self.target.name}_static_251128",
                "sourceKey": f"cdm_{self.target.code.lower()}",
            }
        ]

    def list_characterizations(self, size=200):
        self.calls.append(("list_characterizations", size))
        if self.existing:
            return [{"id": self.target.site_id, "name": f"Bio17_{self.target.code}"}]
        return []

    def import_characterization(self, spec):
        self.calls.append(("import_characterization", spec))
        return {"id": self.target.site_id, "name": spec["name"]}

    def get_characterization_generations(self, characterization_id):
        self.calls.append(("get_characterization_generations", characterization_id))
        self.generation_reads += 1
        source_key = f"cdm_{self.target.code.lower()}"
        if self.existing:
            return [
                {
                    "id": 5000 + self.target.site_id,
                    "sourceKey": source_key,
                    "status": "COMPLETE",
                }
            ]
        if self.wait and self.generation_reads > 1:
            return [
                {
                    "id": 6000 + self.target.site_id,
                    "sourceKey": source_key,
                    "status": "COMPLETE",
                }
            ]
        return []

    def generate_characterization(self, characterization_id, source_key):
        self.calls.append(
            ("generate_characterization", characterization_id, source_key)
        )
        return {"executionId": 7000 + self.target.site_id}


def test_deploy_isolates_site_failure_and_continues_in_input_order():
    targets = [
        SiteTarget(1, 101, "ONE", "첫 번째"),
        SiteTarget(2, 102, "BAD", "실패 기관"),
        SiteTarget(3, 103, "THREE", "세 번째"),
    ]
    factory_calls = []

    def client_factory(target):
        factory_calls.append(target.code)
        return FakeSiteClient(target, fail=target.code == "BAD")

    deployer = MultisiteCharacterizationDeployer()
    records = deployer.deploy(
        {"id": 121, "name": "source"},
        targets,
        client_factory,
        lambda target: f"Bio17_{target.code}",
    )

    assert [record.code for record in records] == ["ONE", "BAD", "THREE"]
    assert [record.status for record in records] == ["STARTED", "FAILED", "STARTED"]
    assert factory_calls == ["ONE", "BAD", "THREE"]
    assert "do-not-leak" not in records[1].error
    assert "hidden" not in records[1].error


def test_deploy_reuses_completed_generation_without_importing():
    target = SiteTarget(7, 203, "KHNMC", "강동경희대병원")
    client = FakeSiteClient(target, existing=True)
    deployer = MultisiteCharacterizationDeployer()

    records = deployer.deploy(
        {"id": 121, "name": "source"},
        [target],
        lambda _target: client,
        lambda item: f"Bio17_{item.code}",
    )

    assert records[0].status == "REUSED"
    assert records[0].characterization_id == 203
    assert records[0].generation_id == 5203
    assert not any(call[0] == "import_characterization" for call in client.calls)


def test_deploy_waits_and_records_completed_generation(monkeypatch):
    target = SiteTarget(9, 191, "AUMC", "아주대병원")
    client = FakeSiteClient(target, wait=True)
    prepared = []
    deployer = MultisiteCharacterizationDeployer()
    monkeypatch.setattr("atlas_auto.characterization.time.sleep", lambda _seconds: None)

    records = deployer.deploy(
        {"id": 121, "name": "source"},
        [target],
        lambda _target: client,
        lambda item: f"Bio17_{item.code}",
        prepare_site=lambda used_client, source_key, used_target: prepared.append(
            (used_client, source_key, used_target)
        ),
        wait=True,
    )

    assert records[0].status == "COMPLETE"
    assert records[0].generation_id == 6191
    assert prepared == [(client, "cdm_aumc", target)]


def test_write_ledger_is_utf8_atomic_and_preserves_korean(tmp_path):
    output = tmp_path / "deployment.json"
    records = [
        DeploymentRecord(
            code="KHNMC",
            group_id=7,
            site_id=203,
            status="COMPLETE",
            source_name="강동경희대병원_static_251128",
        )
    ]

    written = write_ledger(records, output)

    assert written == output
    assert json.loads(output.read_text(encoding="utf-8"))[0]["source_name"].startswith(
        "강동경희"
    )
    assert not Path(f"{output}.tmp").exists()
