"""ATLAS study driver template — copy to `studies/{연구}/scripts/run_{버전}.py`.

The Python counterpart of `R/lib/driver_template.R`. Same rule: the shared
package owns the sequence and the gates, the driver owns only what this study
is actually asking.

Why this exists
---------------
`studies/fracture_treatment/scripts/` holds 64 scripts, 48 of them `v1_N`
variants. Of those, 0 called `client.wait_for_cohort_generation` and 17
hand-rolled their own polling loop; 18 files hand-typed the `isValid` check.
Each new version re-derived the WebAPI contract by trial and error, and hit the
same traps twice. Write the driver, not the plumbing.

The sequence is not optional
----------------------------
`StudyRun` refuses a stage whose predecessors are missing, so this order is
enforced rather than remembered:

    build     produce the definition locally; no server contact
    deploy    import or create it; never execute in the same step
    inspect   read the deployed artifact back and compare it to what you built
    trigger   start the exact intended analysis
    capture   record the execution identifier it returned
    monitor   poll that identifier
    snapshot  preserve the raw current status

Run it
------
    python run_v1_18.py --build
    python run_v1_18.py --deploy      # then read the inspect output yourself
    python run_v1_18.py --execute

Splitting deploy from execute is the point. A deploy acknowledgement is not
proof that the deployed artifact is the one you designed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The credentials wrapper resolves env -> GCP Secret Manager -> local file.
# Never hard-code an email or password; see CLAUDE.md.
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "automation"))

from atlas_auto import (  # noqa: E402
    FedernetClient,
    StudyRun,
    assert_generation_valid,
    fetch_results,
    resolve_source_id,
    usable_generation,
    write_evidence,
)
from credentials import get_feedernet_credentials  # noqa: E402

# ── study configuration ───────────────────────────────────────────────────

STUDY = "{연구}"
VERSION = "v1.18"

# Site identifiers are four different things. Look them up, never guess:
#   data/site_mapping/site_id_mapping_full.csv  (group_id, site_id, orgId, cdmId)
#   data/site_mapping/source_key_mapping.csv    (sourceKey vs cdmName)
GROUP_ID = 7
SITE_ID = 203
SOURCE_KEY = "cdmpv53_251128"

OUTPUT_DIR = (
    REPO / "studies" / STUDY / "cohort_definitions" / f"{VERSION.replace('.', '_')}"
)

# One entry per artifact this version owns. The key is what the journal and the
# stage gates track, so keep it stable across runs of the same version.
ARTIFACTS = {
    "p1_characterization": {
        "kind": "characterization",
        "definition_path": OUTPUT_DIR / "p1_characterization.json",
    },
}


# ── stages ────────────────────────────────────────────────────────────────


def build(run: StudyRun) -> None:
    """Produce every definition locally. No server contact happens here."""
    for key, spec in ARTIFACTS.items():
        definition = {}  # TODO: build this study's definition
        sha = write_evidence(spec["definition_path"], definition)
        run.record(
            "build", key,
            path=str(spec["definition_path"].relative_to(REPO)),
            sha256=sha,
        )


def deploy(client: FedernetClient, run: StudyRun) -> dict[str, int]:
    """Import each definition. Does not execute anything.

    `run.creating` journals the request before it is sent and the response after
    it lands. If the response is lost, the next run stops at
    `assert_no_uncertain_create` instead of retrying blind and creating a
    duplicate server-side object.
    """
    ids: dict[str, int] = {}
    for key, spec in ARTIFACTS.items():
        with run.creating(key) as created:
            # TODO: the import call for this artifact kind.
            # An analysis import also creates the cohort definitions inside it,
            # resolved by expression. Import cohorts first and bodies second to
            # avoid duplicates, and make local edits only after everything is in.
            response = {}
            created.update({"id": response.get("id")})
        ids[key] = created["id"]
        run.record("deploy", key, id=created["id"])
    return ids


def inspect(client: FedernetClient, run: StudyRun, ids: dict[str, int]) -> None:
    """Read each deployed artifact back and compare it to what was built.

    Use the `/export` endpoint, not the plain read: for every ATLAS artifact the
    export is the portable form and the read DTO is not. A pathway read DTO is
    2 KB of id references; its export is 162 KB with every cohort expression
    inline.

    Name every field whose order the server does not preserve in `unordered`.
    """
    for key, spec in ARTIFACTS.items():
        prepared = {}   # TODO: load spec["definition_path"]
        live = {}       # TODO: client.export_...(ids[key])
        run.assert_definition_unchanged(
            key,
            prepared=prepared,
            live=live,
            unordered=("featureAnalyses", "cohorts"),
        )
        run.record("inspect", key, id=ids[key])


def trigger(client: FedernetClient, run: StudyRun, ids: dict[str, int]) -> None:
    """Start each analysis and capture the identifier it returns."""
    for key in ARTIFACTS:
        run.assert_ready_to_trigger(key)
        response = {}  # TODO: client.generate_...(ids[key], SOURCE_KEY)
        run.record("trigger", key, id=ids[key])
        run.record("capture", key, generation_id=response.get("id"))


def monitor(client: FedernetClient, run: StudyRun, ids: dict[str, int]) -> None:
    """Poll the captured identifier, then preserve the raw status.

    `status == "COMPLETE"` alone is not success. A generation can finish after
    hours and still return `isValid: false` with a null `personCount`. And a
    site with several CDM sources returns one row per source, so scope the read
    to the source in use.
    """
    source_id = resolve_source_id(client.get_sources(), SOURCE_KEY)
    for key in ARTIFACTS:
        rows = client.get_cohort_generation_info(ids[key])
        row = usable_generation(rows, source_id=source_id)
        assert_generation_valid(row, cohort_id=ids[key], source_id=source_id)
        run.record("monitor", key, generation_id=row.get("id"))
        run.snapshot(key, row, label="generation")


def collect(client: FedernetClient, run: StudyRun, generation_id: int) -> list:
    """Fetch results with the count checked.

    `fetch_results` forces `threshold_level=0`, compares against the count
    endpoint, and refuses to return when a requested analysis id has no row.
    The WebAPI default of 0.01 drops sub-1% covariates silently, and a missing
    row read as zero produces a plausible, wrong table.
    """
    return fetch_results(client, generation_id, analysis_ids=[])  # TODO


# ── entry point ───────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=f"{STUDY} {VERSION}")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--deploy", action="store_true", help="import only")
    parser.add_argument("--execute", action="store_true", help="trigger + monitor")
    args = parser.parse_args(argv)

    run = StudyRun(OUTPUT_DIR, run_id=VERSION)
    run.assert_no_uncertain_create()

    if args.build:
        build(run)
        return

    client = FedernetClient()
    client.login_portal(*get_feedernet_credentials())
    client.connect_site(group_id=GROUP_ID, site_id=SITE_ID)

    if args.deploy:
        ids = deploy(client, run)
        inspect(client, run, ids)
        return

    if args.execute:
        ids = {
            key: record["id"]
            for record in run.journal_records()
            if record.get("event") == "deploy"
            for key in [record["key"]]
        }
        trigger(client, run, ids)
        monitor(client, run, ids)
        return

    parser.error("choose one of --build, --deploy, --execute")


if __name__ == "__main__":
    main()
