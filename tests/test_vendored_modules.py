"""A study's shipped copy of a shared module must not drift from the original.

`studies/*/portable_assets/` is a self-contained package handed to another
institution, so a copy of a shared helper inside it is legitimate: the receiving
site has no package install. What is not legitimate is that copy silently going
stale.

It already happened. `portable_assets/scripts/characterization_safety.py` was a
copy of `src/atlas_auto/characterization_safety.py` taken before the source
gained `design_key`, `feature_identity` and `import_characterization_mapped` —
the three helpers that close the "a design does not identify a feature" trap. The
shipped package therefore taught the receiving site a contract the origin study
had already outgrown.

Each `portable_assets/scripts/` declares its provenance in `VENDORED.json`,
mapping the shipped file name to the shared module it copies. This test fails
when they diverge. Re-sync with::

    python data/scripts/sync_vendored_modules.py

Comparison is on text with newlines normalised: the portable package ships LF
and a Windows checkout may hold CRLF, which is not drift.
"""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MANIFESTS = sorted(REPO.glob("studies/*/portable_assets/scripts/VENDORED.json"))


def _body(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _pairs():
    for manifest in MANIFESTS:
        mapping = json.loads(manifest.read_text(encoding="utf-8"))
        for shipped_name, source_rel in mapping.items():
            yield manifest, shipped_name, source_rel


def test_at_least_one_vendoring_manifest_exists():
    """A silently absent manifest would make every case below vacuous."""
    assert MANIFESTS, "no portable_assets/scripts/VENDORED.json found"


@pytest.mark.parametrize(
    "manifest,shipped_name,source_rel",
    list(_pairs()),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_shipped_copy_matches_its_shared_module(manifest, shipped_name, source_rel):
    shipped = manifest.parent / shipped_name
    source = REPO / source_rel

    assert source.is_file(), f"{source_rel} does not exist"
    assert shipped.is_file(), f"{shipped} does not exist"
    assert _body(shipped) == _body(source), (
        f"{shipped.relative_to(REPO)} has drifted from {source_rel}; "
        f"re-run data/scripts/sync_vendored_modules.py"
    )


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: p.parent.parent.parent.name)
def test_every_shipped_script_is_declared_or_study_local(manifest):
    """A shipped .py is either a declared copy or genuinely study-specific.

    Nothing enforces the second case; the point is that an undeclared file is a
    deliberate choice recorded here, not an unnoticed fork.
    """
    declared = set(json.loads(manifest.read_text(encoding="utf-8")))
    present = {path.name for path in manifest.parent.glob("*.py")}

    assert declared <= present, f"declared but missing: {sorted(declared - present)}"
