# Archive — 2026-04-16 to 2026-04-18 derived

**Status**: ⛔ **DO NOT USE for measurement research**. Built on top of an untraceable source.

**Archived on**: 2026-05-12
**Original location**: `data/measurement/`

## Why archived

These files were either built directly from, or derived using as input, the 2026-04-16 untraceable concept_frequency CSVs (see `data/concept_frequency/archive/2026-04-16_untraceable_source/README.md` for the full forensic).

Contents:

| File | mtime | How affected |
|---|---|---|
| `concept_mapping.csv` | 2026-04-17 | Derived from stale concept_frequency CSV |
| `unit_survey_full.csv` | 2026-04-17 | Drilldown collected per concept; **drilldown responses themselves are valid Achilles output**, but the input concept list came from the stale CSV → some concepts collected from KHNMC ATLAS state that no longer exists, others from concepts ETL has since re-mapped |
| `stability_summary.csv` | 2026-04-18 | Derived from concept_frequency |
| `site_concept_matrix.csv` | 2026-04-18 | Derived from concept_frequency |
| `by_site/concept_by_site.csv` | 2026-04-16 | Direct stale collection |
| `by_site/units_by_site.csv` | 2026-04-16 | Direct stale collection |
| `by_site/unit_summary_by_site.csv` | 2026-04-16 | Direct stale collection |
| `v4_surveys/biomarker_unit_survey.csv` | 2026-04-18 | v4 analysis-specific survey, stale concept list dependence |
| `v4_surveys/all_outcomes_value_survey.csv` | 2026-04-17 | Same |
| `v4_surveys/extension11_value_survey.csv` | 2026-04-18 | Same |
| `v4_surveys/tsh_vitd_survey.csv` | 2026-04-18 | Same |

## What this means

- **v9.4 paper (appendectomy) is unaffected** — paper uses ATLAS estimation direct query, not these derived CSVs.
- **char_preset_all.csv** (PRESET FA characterization) is kept in `data/measurement/characterization/` because it was collected via PRESET FA against OMOP directly, independent of these CSVs.
- For ongoing / future measurement research that requires site-level concept availability or unit metadata: collect freshly with metadata header.

## If recovery is needed

The drilldown responses inside `unit_survey_full.csv` are themselves valid Achilles output — if reproducibility is required for a past analysis that used this file, the data inside is internally consistent (it reflects the Achilles state at 2026-04-17 for whatever sourceKey was active then). The unreliable layer is the concept inventory (which concepts were targeted for drilldown).
