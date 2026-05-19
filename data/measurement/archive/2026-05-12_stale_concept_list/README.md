# Archive — 2026-05-12 stale concept list

**Status**: ⛔ **DO NOT USE for measurement research**. Drilldown responses are valid, but the input concept inventory was stale.

**Archived on**: 2026-05-12 (same day as collection — flagged after discovery)
**Original location**: `data/measurement/khnmc_full_value_survey.csv`, `data/measurement/raw_drilldown/`

## Why archived

These were collected on 2026-05-11 / 2026-05-12 against the current KHNMC ATLAS instance `KHNMC_5.3.1_08 (cdmpv53_251128)` and the responses themselves are **internally valid Achilles drilldown output** for that instance. However:

- The **input concept list** came from `data/concept_frequency/by_site/KHNMC_measurement.csv` (1,494 concepts)
- That CSV is the untraceable Apr-16 snapshot whose source does not match any current KHNMC instance
- Result: 609 of 1,494 concepts (40.8%) returned `NO_DATA` because they do not exist in the current `cdmpv53_251128` OMOP build (or have been re-mapped to other concept_ids by ETL)
- 885 of 1,494 concepts returned valid distribution data, but the inventory was always going to be incomplete because concepts in the current OMOP that are NOT in the stale CSV were never queried at all

## What this means

- Files inside are not "wrong" per se — they accurately reflect KHNMC `cdmpv53_251128` Achilles state for the specific 1,494 concepts queried, with 5 concepts re-validated on 2026-05-12 by retry (originally ERROR placeholder).
- But the **concept selection (inventory) is biased** by the stale CSV, so this file should not be used as a representative survey of KHNMC measurement universe.

## What is valid inside

If you need it: each row's drilldown response (`recordsByUnit`, `measurementValueDistribution`, etc.) is internally consistent with KHNMC `cdmpv53_251128` Achilles state at 2026-05-11/12. The 5 retried concepts (3000330 / 3009542 / 3015884 / 3016244 / 3028026) were re-validated on 2026-05-12 and confirmed to have data in the current OMOP.

## Replacement

Fresh refresh planned with proper inventory step:
1. `client.get_achilles_frequency(sourceKey='cdmpv53_251128', domain='measurement')` → fresh inventory
2. For each inventory concept, `client.get_achilles_drilldown(...)` for value distribution
3. Write CSV with metadata header (sourceName, sourceKey, vocabulary release, total_persons, collected_at)

## Forensics reference

Full forensic in `data/concept_frequency/archive/2026-04-16_untraceable_source/README.md`.
