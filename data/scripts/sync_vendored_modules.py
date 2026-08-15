"""Refresh every study's shipped copy of a shared module from `src/`.

`studies/*/portable_assets/` is handed to another institution as a self-contained
package, so it carries copies of the shared helpers. Those copies go stale: the
fracture-treatment copy of `characterization_safety.py` was taken before the
source gained `design_key`, `feature_identity` and
`import_characterization_mapped`, and the shipped package then taught a contract
the origin study had already outgrown.

Each `portable_assets/scripts/VENDORED.json` maps a shipped file name to the
shared module it copies. This script rewrites each shipped file from its source.
`tests/test_vendored_modules.py` fails when they diverge.

Files are written with `newline="\\n"`. The portable package publishes sha256
digests taken over LF bytes, and `Path.write_text` would translate to CRLF on
Windows and make every digest fail.

    python data/scripts/sync_vendored_modules.py           # write
    python data/scripts/sync_vendored_modules.py --check   # report only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _body(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def sync(check_only: bool = False) -> int:
    manifests = sorted(REPO.glob("studies/*/portable_assets/scripts/VENDORED.json"))
    if not manifests:
        print("no VENDORED.json manifests found")
        return 0

    drifted = 0
    for manifest in manifests:
        mapping = json.loads(manifest.read_text(encoding="utf-8"))
        for shipped_name, source_rel in sorted(mapping.items()):
            source = REPO / source_rel
            shipped = manifest.parent / shipped_name
            if not source.is_file():
                raise SystemExit(f"missing source module: {source_rel}")

            wanted = _body(source)
            current = _body(shipped) if shipped.is_file() else None
            label = shipped.relative_to(REPO)

            if current == wanted:
                print(f"ok       {label}")
                continue

            drifted += 1
            if check_only:
                print(f"DRIFTED  {label}  <- {source_rel}")
                continue
            with open(shipped, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(wanted)
            print(f"written  {label}  <- {source_rel}")

    if check_only and drifted:
        print(f"\n{drifted} file(s) drifted; re-run without --check to sync")
    return 1 if (check_only and drifted) else 0


if __name__ == "__main__":
    raise SystemExit(sync(check_only="--check" in sys.argv[1:]))
