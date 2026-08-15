"""Derive a flow-chart attrition waterfall from an ATLAS inclusion-rule report.

ATLAS already computes per-inclusion-rule attrition during a normal cohort
generation, so never build one cohort per flow-chart step. The numbers live in
`GET /cohortdefinition/{id}/report/{sourceKey}`, which returns `summary`,
`inclusionRuleStats` and `treemapData`.

The obvious way to read them off is wrong.

`inclusionRuleStats[i].countSatisfying` is the count of patients satisfying rule
*i* **considered on its own** against the base population. It is not "how many
remain after step i". Chaining those numbers produces a waterfall that looks
plausible and is wrong at every row after the first. The fracture-treatment
study made exactly that mistake once and recorded it.

The correct source is `treemapData`. Each leaf is labelled with a bit string,
one bit per inclusion rule in the rules' own order, and `size` is the number of
patients matching that exact pattern. Patients remaining after step *k* are the
leaves whose first *k* bits are all `1`.

Two invariants make a parsing mistake fail loudly instead of producing a wrong
table: the leaves must sum to `baseCount`, and the all-ones leaf must equal
`finalCount`.

Rule order is part of the definition. ATLAS attrition is order-dependent, so
reordering the rules redistributes counts between steps and answers a different
question, even though base and final stay fixed.

Promoted to the shared package from
`studies/fracture_treatment/portable_assets/scripts/cumulative_attrition.py`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASE_LABEL = "qualifying events (before inclusion rules)"


def _leaves(treemap: Any) -> list[tuple[str, int]]:
    if isinstance(treemap, str):
        treemap = json.loads(treemap)

    found: list[tuple[str, int]] = []

    def walk(node: dict) -> None:
        if "children" in node:
            for child in node["children"]:
                walk(child)
        else:
            found.append((node["name"], node["size"]))

    walk(treemap)
    return found


def cumulative_attrition(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Chain the steps from the treemap bit strings, never from countSatisfying.

    Accepts either the report body itself or a wrapper holding it under
    `report`, which is how archived runs are stored.

    Returns one row per step, starting with the base population. Each row is
    ``{"step", "remaining", "excluded_here"}``; the base row's `excluded_here`
    is None.
    """
    if "inclusionRuleStats" not in report and isinstance(report.get("report"), dict):
        report = report["report"]

    rules = report["inclusionRuleStats"]
    leaves = _leaves(report["treemapData"])

    base = report["summary"]["baseCount"]
    final = report["summary"]["finalCount"]

    leaf_sum = sum(size for _, size in leaves)
    if leaf_sum != base:
        raise RuntimeError(
            f"treemap leaves sum to {leaf_sum}, not baseCount {base}; the leaves "
            "were parsed wrongly and every row below would be wrong"
        )

    all_ones = [
        size for bits, size in leaves
        if len(bits) == len(rules) and set(bits) == {"1"}
    ]
    if all_ones != [final]:
        raise RuntimeError(
            f"all-ones treemap leaf {all_ones} does not equal finalCount {final}; "
            "the bit order does not match the rule order"
        )

    rows = [{"step": BASE_LABEL, "remaining": base, "excluded_here": None}]
    previous = base
    for index, rule in enumerate(rules, start=1):
        remaining = sum(
            size for bits, size in leaves
            if all(bit == "1" for bit in bits[:index])
        )
        rows.append({
            "step": rule["name"],
            "remaining": remaining,
            "excluded_here": previous - remaining,
        })
        previous = remaining
    return rows


def format_attrition(rows: list[dict[str, Any]]) -> str:
    """Render the waterfall as fixed-width text."""
    width = max(len(row["step"]) for row in rows)
    lines = []
    for row in rows:
        removed = (
            "" if row["excluded_here"] is None else f"-{row['excluded_here']:,}"
        )
        lines.append(f"{row['step']:<{width}}  {row['remaining']:>8,}  {removed:>8}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> list[dict[str, Any]]:
    """CLI: ``python -m atlas_auto.attrition <report.json>``.

    `report.json` is the body of `GET /cohortdefinition/{id}/report/{sourceKey}`.
    This entry point is kept so the module works unchanged when it ships inside a
    study's `portable_assets/scripts/` for a site that has no package install.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit("usage: attrition.py <report.json>")
    report = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    rows = cumulative_attrition(report)
    print(format_attrition(rows))
    return rows


if __name__ == "__main__":
    main()
