"""Contract tests for the inclusion-rule attrition waterfall.

`inclusionRuleStats[i].countSatisfying` counts patients satisfying rule *i* on
its own against the base population. It is not "remaining after step i", and
chaining it produces a waterfall that looks right and is wrong at every row
after the first. The fracture-treatment study made that error once and recorded
it. The correct source is `treemapData`.
"""

import json

import pytest

from atlas_auto.attrition import cumulative_attrition, format_attrition, main

# base 100; after R1 70, after R2 50, after R3 40.
LEAVES = {
    "111": 40,  # == finalCount
    "110": 10,
    "101": 5,
    "100": 15,
    "011": 8,
    "010": 7,
    "001": 6,
    "000": 9,
}


def treemap(leaves=None):
    leaves = LEAVES if leaves is None else leaves
    return {
        "name": "root",
        "children": [
            {"name": bits, "size": size} for bits, size in leaves.items()
        ],
    }


def report(leaves=None, base=100, final=40, treemap_as_string=False):
    data = treemap(leaves)
    return {
        "summary": {"baseCount": base, "finalCount": final},
        # Deliberately non-chainable: these are independent counts.
        "inclusionRuleStats": [
            {"name": "age >= 50", "countSatisfying": 70},
            {"name": "no prior AOM", "countSatisfying": 58},
            {"name": "no cancer", "countSatisfying": 59},
        ],
        "treemapData": json.dumps(data) if treemap_as_string else data,
    }


def test_waterfall_chains_from_the_treemap_bit_strings():
    rows = cumulative_attrition(report())

    assert [row["remaining"] for row in rows] == [100, 70, 50, 40]
    assert [row["excluded_here"] for row in rows] == [None, 30, 20, 10]


def test_the_waterfall_ignores_count_satisfying():
    """Chaining countSatisfying would give 70/58/59, not 70/50/40."""
    rows = cumulative_attrition(report())

    assert [row["remaining"] for row in rows][1:] != [70, 58, 59]


def test_step_names_come_from_the_rules_in_rule_order():
    rows = cumulative_attrition(report())

    assert [row["step"] for row in rows][1:] == [
        "age >= 50", "no prior AOM", "no cancer",
    ]


def test_the_first_row_is_the_base_population():
    rows = cumulative_attrition(report())

    assert rows[0]["remaining"] == 100
    assert rows[0]["excluded_here"] is None


def test_a_treemap_delivered_as_a_json_string_is_parsed():
    rows = cumulative_attrition(report(treemap_as_string=True))

    assert [row["remaining"] for row in rows] == [100, 70, 50, 40]


def test_an_archived_wrapper_holding_the_report_is_unwrapped():
    rows = cumulative_attrition({"report": report(), "capturedAt": "2026-08-14"})

    assert [row["remaining"] for row in rows] == [100, 70, 50, 40]


def test_leaves_that_do_not_sum_to_base_count_raise():
    """A parsing mistake must fail loudly, not produce a plausible table."""
    with pytest.raises(RuntimeError) as excinfo:
        cumulative_attrition(report(base=999))

    assert "baseCount" in str(excinfo.value)


def test_an_all_ones_leaf_that_is_not_final_count_raises():
    """That mismatch means the bit order does not match the rule order."""
    with pytest.raises(RuntimeError) as excinfo:
        cumulative_attrition(report(final=41))

    assert "finalCount" in str(excinfo.value)


def test_format_attrition_renders_one_line_per_step():
    text = format_attrition(cumulative_attrition(report()))

    lines = text.splitlines()
    assert len(lines) == 4
    assert lines[0].startswith("qualifying events")
    assert "100" in lines[0]
    assert "-30" in lines[1]


def test_main_reads_a_report_file_and_returns_the_rows(tmp_path, capsys):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report()), encoding="utf-8")

    rows = main([str(path)])

    assert [row["remaining"] for row in rows] == [100, 70, 50, 40]
    assert "-30" in capsys.readouterr().out


def test_main_rejects_a_wrong_argument_count():
    with pytest.raises(SystemExit):
        main([])


def test_nested_treemap_children_are_walked():
    nested = {
        "name": "root",
        "children": [
            {
                "name": "group",
                "children": [
                    {"name": bits, "size": size}
                    for bits, size in list(LEAVES.items())[:4]
                ],
            },
            *[
                {"name": bits, "size": size}
                for bits, size in list(LEAVES.items())[4:]
            ],
        ],
    }
    body = report()
    body["treemapData"] = nested

    rows = cumulative_attrition(body)

    assert [row["remaining"] for row in rows] == [100, 70, 50, 40]
