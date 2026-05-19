# Archive — 2026-04-16 untraceable_source

**Status**: ⛔ **DO NOT USE for measurement / observation / condition research**. Source unverifiable.

**Archived on**: 2026-05-12
**Original location**: `data/concept_frequency/by_site/`, `data/concept_frequency/kcd_vocab/`, `data/concept_frequency/extras/`

## Why archived

These CSVs were imported on 2026-04-24 (commit `aeb2dca chore: consolidate data/concept_frequency/...`) with file mtime 2026-04-16, but the **collection source cannot be traced**:

- The collection script is not in the repo
- No metadata header in the CSVs (no sourceKey, no collection timestamp, no API endpoint)
- The numPersons values do not match **any** of the 6 KHNMC ATLAS OMOP build instances available on the current ATLAS server:

  | sourceKey | sourceName | Total persons (live) | Hemoglobin numPersons |
  |---|---|---|---|
  | cdmpv535_230522 | KHNMC_5.3.0_04 | 887,370 | (no data) |
  | cdmpv53m_240229 | KHNMC_5.3.0_05 | 931,884 | (no data) |
  | cdmpv53_240913 | KHNMC_5.3.1_06 | 931,884 | (no data) |
  | cdmpv53_250317 | KHNMC_5.3.1_07 | 1,133,875 | 561,909 (49.6%) |
  | cdmpv53_251128 | KHNMC_5.3.1_08 (current default) | 1,155,514 | 584,529 (50.6%) |
  | cdmpv53m | KHNMC_5.3.1_monthly | 1,169,751 | 598,289 (51.1%) |
  | **archived CSV** | **unknown** | **~2,140,015** (back-calculated) | **1,281,737 (59.9%)** |

  The archived CSV's KHNMC entry reports ~2.14 M persons, which exceeds every current instance by ~2× and uses a coverage percentage (59.9%) that no current instance matches (~50%). The source is therefore not any of the 6 instances currently visible via `/source/sources`.

- SNOMED hierarchy parent concepts (e.g., `4146380 Alanine aminotransferase measurement`) show numPersons ≈ 1.24 M in the CSV — but SNOMED hierarchy parents normally do not directly receive OMOP MEASUREMENT records under standard ETL, suggesting either a hierarchical (descendants-aggregated) collection method or an external mapping pipeline that does not match current KHNMC ATLAS.

## What this means

- **v9.4 paper (appendectomy) is unaffected** — the v9.4 analysis used ATLAS estimation which queries OMOP MEASUREMENT directly, never reads these CSVs.
- **Site coverage / biomarker selection decisions** based on these CSVs should be **re-validated against fresh live Achilles** (`/cdmresults/{sourceKey}/{domain}`) with explicit metadata header (sourceKey, sourceName, vocabulary release, total_persons, collected_at).
- **Derived files** (`data/measurement/concept_mapping.csv`, `stability_summary.csv`, `site_concept_matrix.csv`, `by_site/*.csv`, `v4_surveys/*.csv`) are likewise unreliable for the same reason and are archived alongside.

## Replacement

Fresh refresh planned in `data/scripts/refresh_achilles_frequency.py` (TBD) — to be executed with mandatory metadata header per CSV.

## If recovery is needed

Contact KHNMC site admin for ETL log / vocabulary release log of the period 2026-04 to identify what ATLAS instance (or external pipeline) produced this snapshot. The 6 instances visible today are not sufficient to explain the 2.14 M person count.
