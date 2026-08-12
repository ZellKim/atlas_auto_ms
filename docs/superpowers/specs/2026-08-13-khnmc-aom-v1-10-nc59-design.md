# KHNMC AOM v1.10 NC59 Estimation Design

## Objective

Create a new, immutable v1.10 revision of the KHNMC AOM fracture Estimations by adding 59 clinically reviewed negative-control outcomes, then deploy and execute new Feedernet analyses across the same 23 CDMs used for v1.9.

The v1.9 ATLAS Estimations `#291/#292`, Feedernet analyses `#11859/#11860`, and execution groups `#147880/#147881` remain historical evidence and must not be modified, reused as the new analysis, cancelled, or deleted.

## Version and naming

- ATLAS concept set: `[ms] AOMFx KHNMC v1.10 negative control outcomes NC59`
- P1 Estimation: `[ms] AOMFx KHNMC v1.10 P1 All-period Initial Anabolic vs Antiresorptive Refracture 91-730 NC59`
- P2 Estimation: `[ms] AOMFx KHNMC v1.10 P2 All-period Maintained LM3 vs Interrupted Refracture 366-730 NC59`
- P1 package: `AOMFxKHNMCv110AllPeriodP1`
- P2 package: `AOMFxKHNMCv110AllPeriodP2`
- Feedernet project: existing stable project `#5413`
- Feedernet analyses: two new analyses whose names include `v1.10`, `P1` or `P2`, and `NC59`
- Artifact root: `studies/fracture_treatment/cohort_definitions/khnmc_v1_10_estimations_20260813/`

Exact-name reuse is allowed only when the full semantic contract is identical. Any exact-name mismatch or duplicate is a hard failure; the automation must not update an existing v1.10 object in place.

## Confirmed negative controls

The confirmed set is the strong tier only. Conditional candidates are excluded. Every item must resolve live as a Standard, Valid, SNOMED, Condition concept and is represented with `includeDescendants=true`, `includeMapped=false`, and `isExcluded=false`.

| # | Concept ID | Concept name |
|---:|---:|---|
| 1 | 378424 | Astigmatism |
| 2 | 381581 | Chalazion |
| 3 | 375552 | Pterygium |
| 4 | 374375 | Impacted cerumen |
| 5 | 377910 | Deviated nasal septum |
| 6 | 374801 | Foreign body in ear |
| 7 | 440129 | Hypertrophy of nasal turbinates |
| 8 | 261599 | Vocal cord paralysis |
| 9 | 4170770 | Epidermoid cyst |
| 10 | 441818 | Hemangioma |
| 11 | 139099 | Ingrowing nail |
| 12 | 4067069 | Callosity |
| 13 | 4288544 | Inguinal hernia |
| 14 | 4112731 | Polyp of intestine |
| 15 | 195562 | Hemorrhoids |
| 16 | 374923 | Bell's palsy |
| 17 | 381270 | Parkinson's disease |
| 18 | 440374 | Obsessive-compulsive disorder |
| 19 | 440690 | Social phobia |
| 20 | 313459 | Sleep apnea |
| 21 | 136368 | Non-toxic multinodular goiter |
| 22 | 75911 | Acquired hallux valgus |
| 23 | 77965 | Acquired trigger finger |
| 24 | 40481632 | Ganglion cyst |
| 25 | 194475 | Hiccoughs |
| 26 | 376132 | Ectropion |
| 27 | 4083487 | Macular drusen |
| 28 | 377572 | Noise effects on inner ear |
| 29 | 374919 | Multiple sclerosis |
| 30 | 433997 | Lymphangioma |
| 31 | 379805 | Myopia |
| 32 | 373478 | Presbyopia |
| 33 | 440083 | Acute stress disorder |
| 34 | 436677 | Adjustment disorder |
| 35 | 436665 | Bipolar disorder |
| 36 | 197032 | Hyperplasia of prostate |
| 37 | 81336 | Rectal prolapse |
| 38 | 201606 | Crohn's disease |
| 39 | 434085 | Obstruction of duodenum |
| 40 | 192953 | Intestinal adhesions with obstruction |
| 41 | 253796 | Pneumothorax |
| 42 | 254443 | Sjogren's syndrome |
| 43 | 438688 | Sarcoidosis |
| 44 | 4094822 | Foreign body in respiratory tract |
| 45 | 435371 | Hypothermia |
| 46 | 72995 | Contracture of joint of hand |
| 47 | 440268 | Toxic effect of carbon monoxide |
| 48 | 4164898 | Diverticulosis of large intestine without diverticulitis |
| 49 | 433450 | Paranoid schizophrenia |
| 50 | 197036 | Vesicoureteric reflux |
| 51 | 4096682 | Bleeding from nose |
| 52 | 4271013 | Melanocytic nevus |
| 53 | 4112852 | Benign lipomatous tumor |
| 54 | 4142875 | Solitary nodule of lung |
| 55 | 36716270 | Cyst of kidney |
| 56 | 257007 | Allergic rhinitis |
| 57 | 195864 | Diverticulum of urinary bladder |
| 58 | 439147 | Amnesia |
| 59 | 261325 | Pulmonary emphysema |

The selection manifest must preserve the exact ID/name pairs, live ConceptDTO payloads, vocabulary checks, hierarchy-overlap checks, primary-outcome overlap check, provenance, review tier, and timestamp. The expected ID set is immutable for v1.10.

## Preserved P1/P2 design

v1.10 changes only Estimation identity/package metadata and negative-control configuration. Cohort definitions, target/comparator/outcome IDs, risk windows, propensity-score settings, outcome-model settings, and all other analysis parameters must remain identical to the corresponding v1.9 export.

| Analysis | Target | Comparator | Primary outcome | Risk window |
|---|---:|---:|---:|---|
| P1 | 2684 | 2685 | 2636 | T0+91 through T0+730 |
| P2 | 2687 | 2688 | 2636 | T0+366 through T0+730 |

Each Estimation contains one TCO. Therefore each has exactly one negative-control cross-reference with `targetName=negativeControlOutcomes`, `targetIndex=0`, and `propertyName=outcomeId`.

For P1, `negativeControls` contains exactly 59 unique `(2684, 2685, outcomeId)` rows. For P2, it contains exactly 59 unique `(2687, 2688, outcomeId)` rows. The empty v1.9 placeholder concept set `#524` must not appear.

`negativeControlOutcomeCohortDefinition` remains:

```json
{
  "occurrenceType": "all",
  "detectOnDescendants": true,
  "domains": ["condition", "procedure"]
}
```

`negativeControlExposureCohortDefinition={}` and `doPositiveControlSynthesis=false` remain unchanged.

## Fail-closed validation

### Before any ATLAS mutation

The pure design validator must establish all of the following:

1. The configured NC ID set equals the 59 confirmed IDs exactly.
2. Every ID is positive and unique, and every live concept has the expected exact name, Condition domain, SNOMED vocabulary, Standard status, and Valid status.
3. The new concept-set expression contains 59 full ConceptDTO items with the required flags.
4. The expanded concept closures have no pairwise intersection and no intersection with the primary-outcome expression `#2636`.
5. The Estimation contains exactly one TCO and one NC cross-reference targeting index 0.
6. The concept-set reference resolves to the newly created or exactly reused v1.10 NC59 concept set.
7. The 59 NC triples use the exact target/comparator pair for that analysis and contain no duplicate.
8. The normalized non-NC portion of the specification is identical to v1.9 except for the approved name, package, description suffix, and NC fields.

### After ATLAS PUT and before Feedernet import

The final `/estimation/{id}/export` is authoritative. It must contain:

- exactly 59 effective `negativeControls`;
- the exact confirmed outcome-ID set;
- the exact P1 or P2 target/comparator pair on every row;
- no duplicate triples;
- valid NC cross-reference coverage of target index 0;
- a non-empty NC cohort definition;
- no reference to concept set `#524`.

The exported concept-set item list may be empty only when the effective exported `negativeControls` still contains the exact 59 rows. `/estimation/check` is an additional diagnostic and never substitutes for this export contract.

### Before Feedernet execution

The automation must:

1. create/import new Feedernet analyses without triggering execution;
2. inspect the imported analysis metadata and exact ATLAS Estimation mapping;
3. verify that the intended CDM-ID set equals the 23-CDM set from both v1.9 groups;
4. trigger only those exact two new analysis IDs and exact 23 CDMs;
5. capture the returned execution group and execution IDs;
6. immediately re-read and preserve raw current status snapshots.

## Idempotency and failure handling

- No existing v1.9 object is mutable in this workflow.
- A same-name v1.10 concept set, Estimation, or Feedernet analysis is reusable only after exact-contract equality.
- A same-name mismatch, duplicate exact name, missing concept, vocabulary mismatch, hierarchy collision, empty effective NC list, wrong T/C mapping, unexpected generation, or wrong CDM set stops the workflow.
- The deployment script never triggers an Estimation.
- The Feedernet execution script requires an explicit execution flag and reads the validated deployment artifacts before triggering.
- Partial success is recorded with exact IDs and timestamps; the automation does not delete or overwrite partially created live assets.

## Limitations and interpretation gate

- Fifty-nine configured controls provide only nine controls of buffer above the 50-control rule of thumb. Configuration does not prove estimability.
- Whole-CDM Achilles visibility is not a P1/P2 matched-risk-window event count. Multiple sclerosis (`374919`) and diverticulum of urinary bladder (`195864`) were particularly sparse at KHNMC in the preflight and may be non-estimable.
- Each site and each P1/P2 result must retain at least 50 finite, valid NC estimates with adequate matched risk-window events before empirical calibration is treated as stable. If fewer than 50 survive, calibration and calibrated inference are marked exploratory or unavailable; conditional candidates are not silently added after observing results.
- Negative controls diagnose systematic error; they do not remove bias by themselves.
- P2 uses a day-365 landmark, so its day-366 outcome window avoids classic immortal-time attribution. It remains conditional on surviving, remaining observable, and having adherence classified through day 365. Healthy-adherer, healthcare-contact, and time-varying illness bias can remain.
- A successful v1.10 run would support that the package is executable with valid NC wiring. It would not prove that every v1.9 failure was caused solely by the empty placeholder because v1.9 failure logs were empty and site/runtime interactions remain possible.

## Durable artifacts

The workflow stores:

- `negative_control_selection.json` and a human-readable review table;
- concept-set deployment payload and live expression;
- P1/P2 design contracts, final exports, diagnostics, and deployment metadata;
- cohort readiness and unchanged-design comparison;
- Feedernet analysis map, 23-CDM manifest, import response, trigger response, execution IDs, and immediate status;
- `VALIDATION.md` containing all pass/fail gates and the limitations above;
- updates to `PROGRESS.md` and `study_knowledge_base.md` that preserve v1.9 as superseded evidence rather than rewriting its history.
