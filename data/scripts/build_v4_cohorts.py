"""
v4 cohort JSON 일괄 생성기 (43 cohort)

Template 기반 (v3 B07_CRP, B_Neutro 구조 참조):
- Single-concept, single unit
- Multi-concept OR
- Dual-unit (2 cohort per biomarker)
- Bidirectional (low/high 분리)
- Sex-specific (gender filter)
- Inclusion rules: Prior normal (365d) + No prior abnormal

Output: cohort_definitions/v4/*.json
"""
import json
import os
from copy import deepcopy

OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..',
    'studies', 'appendectomy', 'cohort_definitions', 'v4b')
os.makedirs(OUT_DIR, exist_ok=True)
# v4b = simplified (no inclusion rules; IPD handles prior filter with 30d washout)

# Unit concept IDs (OMOP)
UNIT = {
    'mg/dL':        {'id': 8840, 'name': 'milligram per deciliter'},
    'mg/L':         {'id': 8751, 'name': 'milligram per liter'},
    'g/dL':         {'id': 8713, 'name': 'gram per deciliter'},
    'U/L':          {'id': 8645, 'name': 'unit per liter'},
    'IU/L':         {'id': 8859, 'name': 'international unit per liter'},
    '%':            {'id': 8554, 'name': 'percent'},
    'thou/uL':      {'id': 8848, 'name': 'thousand per microliter'},
    '/uL':          {'id': 8647, 'name': 'per microliter'},
    'fL':           {'id': 9156, 'name': 'femtoliter'},
    'mm/hr':        {'id': 8555, 'name': 'millimeter per hour'},
    'mIU/L':        {'id': 8859, 'name': 'international unit per liter'},  # check — mIU/L vs IU/L
    'uIU/mL':       {'id': 8795, 'name': 'microunit per milliliter'},
    'ng/mL':        {'id': 8842, 'name': 'nanogram per milliliter'},
}

GENDER = {'MALE': 8507, 'FEMALE': 8532}

# Concept metadata for cohort JSON (need full fields per ATLAS CIRCE)
def make_concept(cid, name):
    return {
        'CONCEPT_ID': cid,
        'CONCEPT_NAME': name,
        'STANDARD_CONCEPT': 'S',
        'STANDARD_CONCEPT_CAPTION': 'Standard',
        'INVALID_REASON': 'V',
        'INVALID_REASON_CAPTION': 'Valid',
        'DOMAIN_ID': 'Measurement',
        'VOCABULARY_ID': 'LOINC',
        'CONCEPT_CLASS_ID': 'Lab Test',
    }

def make_unit(unit_key):
    u = UNIT[unit_key]
    return [{'CONCEPT_ID': u['id'], 'CONCEPT_NAME': u['name']}]

def make_gender(gender_key):
    return [{'CONCEPT_ID': GENDER[gender_key], 'CONCEPT_NAME': gender_key}]

def value_op(op, value, extent=None):
    """op: 'gt', 'gte', 'lt', 'lte', 'bt' (between). extent used for 'bt'."""
    v = {'Value': value, 'Op': op}
    if op == 'bt' and extent is not None:
        v['Extent'] = extent
    return v

# =========================================================
# Cohort JSON builder
# =========================================================
def build_cohort(name, concept_sets, entry_criteria,
                  prior_normal_criteria, no_prior_abnormal_criteria):
    """
    concept_sets: list of {id, name, concepts: [(cid, cname)]}
    entry_criteria: list of measurement criteria dicts
    prior_normal: list of measurement criteria for InclusionRule 1
    no_prior_abnormal: list of measurement criteria for InclusionRule 2
    """
    cs_list = []
    for cs in concept_sets:
        items = []
        for cid, cname in cs['concepts']:
            items.append({
                'concept': make_concept(cid, cname),
                'isExcluded': False,
                'includeDescendants': True,
                'includeMapped': False,
            })
        cs_list.append({
            'id': cs['id'],
            'name': cs['name'],
            'expression': {'items': items},
        })

    def build_meas_criteria(cr):
        meas = {'CodesetId': cr['codeset_id']}
        if 'value' in cr:
            meas['ValueAsNumber'] = value_op(cr['op'], cr['value'], cr.get('extent'))
        if 'unit' in cr and cr['unit']:
            meas['Unit'] = make_unit(cr['unit'])
        if 'gender' in cr and cr['gender']:
            meas['Gender'] = make_gender(cr['gender'])
        return {'Measurement': meas}

    primary_criteria_list = [build_meas_criteria(cr) for cr in entry_criteria]

    # v4b: inclusion rules 제거 — IPD에서 30일 washout + Full Union filter 처리
    inclusion_rules = []

    def build_inclusion(criteria_list, occ_type, window_start_days=365):
        crits = []
        for cr in criteria_list:
            crits.append({
                'Criteria': build_meas_criteria(cr),
                'StartWindow': {
                    'Start': {'Days': window_start_days, 'Coeff': -1},
                    'End': {'Days': 1, 'Coeff': -1},
                    'UseEventEnd': False,
                },
                'Occurrence': {'Type': occ_type, 'Count': 1},
            })
        return crits

    # "Prior normal" = at least 1 occurrence (Type=2 is "at least")
    prior_normal_rule = {
        'name': 'Prior normal (365d)',
        'expression': {
            'Type': 'ANY',  # any of the criteria (dual-unit, multi-concept)
            'CriteriaList': build_inclusion(prior_normal_criteria, occ_type=2, window_start_days=365),
            'DemographicCriteriaList': [],
            'Groups': [],
        },
    }
    # "No prior abnormal" = 0 occurrences (Type=0 is "exactly"), any time prior
    def build_no_prior(criteria_list):
        crits = []
        for cr in criteria_list:
            crits.append({
                'Criteria': build_meas_criteria(cr),
                'StartWindow': {
                    'Start': {'Coeff': -1},  # any time prior (no Days means all prior)
                    'End': {'Days': 1, 'Coeff': -1},
                    'UseEventEnd': False,
                },
                'Occurrence': {'Type': 0, 'Count': 0},
            })
        return crits

    no_prior_rule = {
        'name': 'No prior abnormal',
        'expression': {
            'Type': 'ALL',  # must satisfy all (none of abnormal criteria triggered)
            'CriteriaList': build_no_prior(no_prior_abnormal_criteria),
            'DemographicCriteriaList': [],
            'Groups': [],
        },
    }

    cohort = {
        'cdmVersionRange': '>=5.0.0',
        'ConceptSets': cs_list,
        'PrimaryCriteria': {
            'CriteriaList': primary_criteria_list,
            'ObservationWindow': {'PriorDays': 0, 'PostDays': 0},
            'PrimaryCriteriaLimit': {'Type': 'First'},
        },
        'QualifiedLimit': {'Type': 'First'},
        'ExpressionLimit': {'Type': 'First'},
        'InclusionRules': inclusion_rules,  # v4b: empty
        'EndStrategy': {
            'DateOffset': {'DateField': 'StartDate', 'Offset': 1},
        },
        'CensoringCriteria': [],
        'CollapseSettings': {'CollapseType': 'ERA', 'EraPad': 0},
        'CensorWindow': {},
    }
    return cohort


def save(name, cohort):
    path = os.path.join(OUT_DIR, f'{name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cohort, f, indent=2, ensure_ascii=False)
    print(f'  saved: {name}.json')


# =========================================================
# Concept definitions
# =========================================================
WBC_CONCEPTS = [(3000905, 'Leukocytes [#/volume] in Blood by Automated count'),
                (3010813, 'Leukocytes [#/volume] in Blood')]
NEUTRO_ABS = [(3017732, 'Neutrophils [#/volume] in Blood')]
NEUTRO_PCT = [(3017354, 'Segmented neutrophils/100 leukocytes in Blood'),
              (3018010, 'Neutrophils/100 leukocytes in Blood')]
LYMPHO_PCT = [(3002030, 'Lymphocytes/100 leukocytes in Blood')]
EOSINO_ABS = [(3013115, 'Eosinophils [#/volume] in Blood')]
EOSINO_PCT = [(3006504, 'Eosinophils/100 leukocytes in Blood')]
MONO_CONCEPTS = [(3001604, 'Monocytes [#/volume] in Blood'),
                  (3019069, 'Monocytes/100 leukocytes in Blood')]
BASO_PCT = [(3022096, 'Basophils/100 leukocytes in Blood')]
HGB_CONCEPTS = [(3000963, 'Hemoglobin [Mass/volume] in Blood'),
                 (3027484, 'Hemoglobin [Mass/volume] in Blood (alt)')]
HCT_CONCEPTS = [(3009542, 'Hematocrit [Volume Fraction] of Blood'),
                 (3023314, 'Hematocrit [Volume Fraction] of Blood by Automated count')]
MCV_CONCEPTS = [(3024731, 'MCV [Entitic volume]')]
RDW_CONCEPTS = [(3002385, 'Erythrocyte distribution width [Ratio]')]
PLT_CONCEPTS = [(3007461, 'Platelets [#/volume] in Blood')]
CRP_CONCEPTS = [(3020460, 'C reactive protein [Mass/volume] in Serum or Plasma')]
ESR_CONCEPTS = [(3013707, 'Erythrocyte sedimentation rate'),
                 (3015183, 'Erythrocyte sedimentation rate (alt)')]
FERRITIN_CONCEPTS = [(3015242, 'Ferritin [Mass/volume] in Serum or Plasma')]
ALT_CONCEPTS = [(3006923, 'Alanine aminotransferase [Enzymatic activity/volume]')]
AST_CONCEPTS = [(3013721, 'Aspartate aminotransferase [Enzymatic activity/volume]')]
GGT_CONCEPTS = [(3026910, 'Gamma glutamyl transferase [Enzymatic activity/volume]')]
ALP_CONCEPTS = [(3035995, 'Alkaline phosphatase [Enzymatic activity/volume]')]
TOTBILI_CONCEPTS = [(3024128, 'Bilirubin.total [Mass/volume] in Serum or Plasma')]
ALB_CONCEPTS = [(3024561, 'Albumin [Mass/volume] in Serum or Plasma')]
TOTPROT_CONCEPTS = [(3020630, 'Protein [Mass/volume] in Serum or Plasma')]
GLUC_CONCEPTS = [(3004501, 'Glucose [Mass/volume] in Serum or Plasma'),
                   (3037110, 'Fasting glucose [Mass/volume] in Serum or Plasma')]
GLUC_FAST_ONLY = [(3037110, 'Fasting glucose [Mass/volume] in Serum or Plasma')]
HBA1C_CONCEPTS = [(3004410, 'Hemoglobin A1c/Hemoglobin.total in Blood')]
LDL_CONCEPTS = [(3028437, 'Cholesterol in LDL [Mass/volume] in Serum or Plasma')]
HDL_CONCEPTS = [(3007070, 'Cholesterol in HDL [Mass/volume] in Serum or Plasma')]
TG_CONCEPTS = [(3022192, 'Triglyceride [Mass/volume] in Serum or Plasma')]
TC_CONCEPTS = [(3027114, 'Cholesterol [Mass/volume] in Serum or Plasma')]
CR_CONCEPTS = [(3016723, 'Creatinine [Mass/volume] in Serum or Plasma')]
BUN_CONCEPTS = [(3013682, 'Urea nitrogen [Mass/volume] in Serum or Plasma')]
UA_CONCEPTS = [(3037556, 'Urate [Mass/volume] in Serum or Plasma')]
TSH_CONCEPTS = [(3009201, 'Thyrotropin [Units/volume] in Serum or Plasma')]
VITD_CONCEPTS = [(3020149, '25-Hydroxyvitamin D3 [Mass/volume] in Serum or Plasma'),
                   (40765040, '25-Hydroxyvitamin D3+D2 [Mass/volume]'),
                   (42529187, '25-Hydroxyvitamin D3+D2 by Immunoassay')]


def single_concept_cohort(name, concepts, op, value, unit_key, fallback_range=None):
    """단일 concept + unit filter + fallback (value range for No matching).
    Fallback은 entry/prior normal/no prior abnormal 모두에 일관되게 적용.
    """
    cs = [{'id': 0, 'name': name, 'concepts': concepts}]
    opposite = {'gt': 'lte', 'gte': 'lt', 'lt': 'gte', 'lte': 'gt'}.get(op, 'lte')

    # Entry: unit 매칭 OR "No matching" fallback value range
    entry = [{'codeset_id': 0, 'op': op, 'value': value, 'unit': unit_key}]
    prior_normal = [{'codeset_id': 0, 'op': opposite, 'value': value, 'unit': unit_key}]
    no_prior_abnormal = [{'codeset_id': 0, 'op': op, 'value': value, 'unit': unit_key}]

    if fallback_range:
        low, high = fallback_range
        # Entry fallback: abnormal-side value range
        entry.append({'codeset_id': 0, 'op': 'bt', 'value': low, 'extent': high})
        # Prior normal fallback: normal-side value range (opposite direction)
        if op in ('gt', 'gte'):
            # normal = value <= threshold, fallback range for normal side
            prior_normal.append({'codeset_id': 0, 'op': 'bt', 'value': 0, 'extent': value})
        else:
            # normal = value >= threshold, fallback range upper side
            prior_normal.append({'codeset_id': 0, 'op': 'bt', 'value': value, 'extent': high})
        # No prior abnormal fallback: same abnormal range as entry
        no_prior_abnormal.append({'codeset_id': 0, 'op': 'bt', 'value': low, 'extent': high})

    return build_cohort(name, cs, entry, prior_normal, no_prior_abnormal)


# ============== Build all cohorts ==============
def build_all():
    print('\n== v4_1a cbc_wbc ==')
    # 1. WBC > 11 thou/uL
    save('v4_WBC_high', single_concept_cohort(
        'WBC_high', WBC_CONCEPTS, 'gt', 11, 'thou/uL', fallback_range=(11, 50)))
    # 2. Neutro# thou > 7.7
    save('v4_Neutro_abs_thou_high', single_concept_cohort(
        'Neutro_abs_thou_high', NEUTRO_ABS, 'gt', 7.7, 'thou/uL', fallback_range=(7.7, 50)))
    # 3. Neutro# uL > 7700
    save('v4_Neutro_abs_uL_high', single_concept_cohort(
        'Neutro_abs_uL_high', NEUTRO_ABS, 'gt', 7700, '/uL', fallback_range=(7700, 50000)))
    # 4. Neutro% > 70
    save('v4_Neutro_pct_high', single_concept_cohort(
        'Neutro_pct_high', NEUTRO_PCT, 'gt', 70, '%', fallback_range=(70, 100)))
    # 5-6. Lympho% low <20 / high >50
    save('v4_Lympho_pct_low', single_concept_cohort(
        'Lympho_pct_low', LYMPHO_PCT, 'lt', 20, '%', fallback_range=(0, 20)))
    save('v4_Lympho_pct_high', single_concept_cohort(
        'Lympho_pct_high', LYMPHO_PCT, 'gt', 50, '%', fallback_range=(50, 100)))
    # 7. Eosino# thou > 0.5
    save('v4_Eosino_abs_thou_high', single_concept_cohort(
        'Eosino_abs_thou_high', EOSINO_ABS, 'gt', 0.5, 'thou/uL', fallback_range=(0.5, 20)))
    # 8. Eosino# uL > 500
    save('v4_Eosino_abs_uL_high', single_concept_cohort(
        'Eosino_abs_uL_high', EOSINO_ABS, 'gt', 500, '/uL', fallback_range=(500, 20000)))

    print('\n== v4_1b cbc_rbc ==')
    # 9. Eosino% > 6
    save('v4_Eosino_pct_high', single_concept_cohort(
        'Eosino_pct_high', EOSINO_PCT, 'gt', 6, '%', fallback_range=(6, 100)))
    # 10. Mono > 1 thou/uL OR > 10%: multi-concept with per-concept cutoffs + fallback
    mono_entry = [
        {'codeset_id': 0, 'op': 'gt', 'value': 1, 'unit': 'thou/uL'},
        {'codeset_id': 0, 'op': 'bt', 'value': 1, 'extent': 50},   # fallback for abs count
        {'codeset_id': 1, 'op': 'gt', 'value': 10, 'unit': '%'},
        {'codeset_id': 1, 'op': 'bt', 'value': 10, 'extent': 100}, # fallback for %
    ]
    mono_prior = mono_entry  # placeholder (v4b에서 inclusion rules 사용 안 함)
    mono_abn = mono_entry
    save('v4_Mono_high', build_cohort(
        'Mono_high',
        [{'id': 0, 'name': 'Mono_abs', 'concepts': [(3001604, 'Monocytes [#/volume] in Blood')]},
         {'id': 1, 'name': 'Mono_pct', 'concepts': [(3019069, 'Monocytes/100 leukocytes in Blood')]}],
        mono_entry, mono_prior, mono_abn))
    # 11. Baso% > 1
    save('v4_Baso_pct_high', single_concept_cohort(
        'Baso_pct_high', BASO_PCT, 'gt', 1, '%', fallback_range=(1, 100)))
    # 12-13. MCV low <80 / high >100
    save('v4_MCV_low', single_concept_cohort(
        'MCV_low', MCV_CONCEPTS, 'lt', 80, 'fL', fallback_range=(0, 80)))
    save('v4_MCV_high', single_concept_cohort(
        'MCV_high', MCV_CONCEPTS, 'gt', 100, 'fL', fallback_range=(100, 200)))
    # 14. RDW > 14.5
    save('v4_RDW_high', single_concept_cohort(
        'RDW_high', RDW_CONCEPTS, 'gt', 14.5, '%', fallback_range=(14.5, 100)))
    # 15-16. Platelet low <150 / high >450
    save('v4_Platelet_low', single_concept_cohort(
        'Platelet_low', PLT_CONCEPTS, 'lt', 150, 'thou/uL', fallback_range=(0, 150)))
    save('v4_Platelet_high', single_concept_cohort(
        'Platelet_high', PLT_CONCEPTS, 'gt', 450, 'thou/uL', fallback_range=(450, 2000)))

    print('\n== v4_2 chem_hepa ==')
    # 17. CRP mg/dL > 0.5
    save('v4_CRP_mgdL_high', single_concept_cohort(
        'CRP_mgdL_high', CRP_CONCEPTS, 'gt', 0.5, 'mg/dL', fallback_range=(0.5, 30)))
    # 18. CRP mg/L > 5
    save('v4_CRP_mgL_high', single_concept_cohort(
        'CRP_mgL_high', CRP_CONCEPTS, 'gt', 5, 'mg/L', fallback_range=(5, 500)))
    # 19. ALT > 40
    save('v4_ALT_high', single_concept_cohort(
        'ALT_high', ALT_CONCEPTS, 'gt', 40, 'U/L', fallback_range=(40, 50000)))
    # 20. AST > 35
    save('v4_AST_high', single_concept_cohort(
        'AST_high', AST_CONCEPTS, 'gt', 35, 'U/L', fallback_range=(35, 50000)))
    # 21. ALP > 120
    save('v4_ALP_high', single_concept_cohort(
        'ALP_high', ALP_CONCEPTS, 'gt', 120, 'U/L', fallback_range=(120, 50000)))
    # 22. TotBili > 1.2
    save('v4_TotBili_high', single_concept_cohort(
        'TotBili_high', TOTBILI_CONCEPTS, 'gt', 1.2, 'mg/dL', fallback_range=(1.2, 100)))
    # 23. Albumin < 3.5
    save('v4_Albumin_low', single_concept_cohort(
        'Albumin_low', ALB_CONCEPTS, 'lt', 3.5, 'g/dL', fallback_range=(0, 3.5)))
    # 24. HbA1c >= 6.5
    save('v4_HbA1c_high', single_concept_cohort(
        'HbA1c_high', HBA1C_CONCEPTS, 'gte', 6.5, '%', fallback_range=(6.5, 30)))
    # 25. LDL >= 160
    save('v4_LDL_high', single_concept_cohort(
        'LDL_high', LDL_CONCEPTS, 'gte', 160, 'mg/dL', fallback_range=(160, 1000)))
    # 26. TG >= 200
    save('v4_TG_high', single_concept_cohort(
        'TG_high', TG_CONCEPTS, 'gte', 200, 'mg/dL', fallback_range=(200, 10000)))
    # 27. TC >= 240
    save('v4_TC_high', single_concept_cohort(
        'TC_high', TC_CONCEPTS, 'gte', 240, 'mg/dL', fallback_range=(240, 1000)))

    print('\n== v4_3 meta_endo ==')
    # 28. GlucDM >=126: multi-concept (Glucose + Fasting Glucose) + unit fallback
    gluc_dm_entry = [
        {'codeset_id': 0, 'op': 'gte', 'value': 126, 'unit': 'mg/dL'},
        {'codeset_id': 0, 'op': 'bt', 'value': 126, 'extent': 1000},  # fallback for "No matching"
    ]
    save('v4_GlucDM', build_cohort(
        'GlucDM',
        [{'id': 0, 'name': 'Glucose', 'concepts': GLUC_CONCEPTS}],
        gluc_dm_entry, gluc_dm_entry, gluc_dm_entry))
    # 29. GlucPreDM 100-125 fasting only + fallback
    gluc_pre_entry = [
        {'codeset_id': 0, 'op': 'bt', 'value': 100, 'extent': 125, 'unit': 'mg/dL'},
        {'codeset_id': 0, 'op': 'bt', 'value': 100, 'extent': 125},  # fallback
    ]
    save('v4_GlucPreDM', build_cohort(
        'GlucPreDM',
        [{'id': 0, 'name': 'FastingGlucose', 'concepts': GLUC_FAST_ONLY}],
        gluc_pre_entry, gluc_pre_entry, gluc_pre_entry))
    # 30-31. TotProtein low / high
    save('v4_TotProtein_low', single_concept_cohort(
        'TotProtein_low', TOTPROT_CONCEPTS, 'lt', 6, 'g/dL', fallback_range=(0, 6)))
    save('v4_TotProtein_high', single_concept_cohort(
        'TotProtein_high', TOTPROT_CONCEPTS, 'gt', 8, 'g/dL', fallback_range=(8, 20)))
    # 32. BUN > 21
    save('v4_BUN_high', single_concept_cohort(
        'BUN_high', BUN_CONCEPTS, 'gt', 21, 'mg/dL', fallback_range=(21, 500)))
    # 33-34. TSH low / high
    save('v4_TSH_low', single_concept_cohort(
        'TSH_low', TSH_CONCEPTS, 'lt', 0.4, 'mIU/L', fallback_range=(0, 0.4)))
    save('v4_TSH_high', single_concept_cohort(
        'TSH_high', TSH_CONCEPTS, 'gt', 4.5, 'mIU/L', fallback_range=(4.5, 200)))
    # 35. VitD < 20
    save('v4_VitD_low', single_concept_cohort(
        'VitD_low', VITD_CONCEPTS, 'lt', 20, 'ng/mL', fallback_range=(0, 20)))

    print('\n== v4_4 sex_specific ==')

    def sex_specific_cohort(name, concepts, op, m_val, f_val, unit_key, fallback_range):
        """Sex-specific with unit filter + 'No matching' fallback.
        Entry/prior/abnormal each has 4 criteria:
          - MALE + unit + value (explicit)
          - MALE + no unit + value range (fallback for No matching)
          - FEMALE + unit + value (explicit)
          - FEMALE + no unit + value range (fallback)
        """
        low, high = fallback_range
        opposite = {'gt': 'lte', 'gte': 'lt', 'lt': 'gte', 'lte': 'gt'}.get(op, 'lte')

        entry = [
            {'codeset_id': 0, 'op': op, 'value': m_val, 'unit': unit_key, 'gender': 'MALE'},
            {'codeset_id': 0, 'op': 'bt', 'value': low if op in ('gt','gte') else 0,
             'extent': high if op in ('gt','gte') else m_val, 'gender': 'MALE'},
            {'codeset_id': 0, 'op': op, 'value': f_val, 'unit': unit_key, 'gender': 'FEMALE'},
            {'codeset_id': 0, 'op': 'bt', 'value': low if op in ('gt','gte') else 0,
             'extent': high if op in ('gt','gte') else f_val, 'gender': 'FEMALE'},
        ]
        # Prior normal: opposite direction
        prior = [
            {'codeset_id': 0, 'op': opposite, 'value': m_val, 'unit': unit_key, 'gender': 'MALE'},
            {'codeset_id': 0, 'op': 'bt', 'value': 0 if op in ('gt','gte') else m_val,
             'extent': m_val if op in ('gt','gte') else high, 'gender': 'MALE'},
            {'codeset_id': 0, 'op': opposite, 'value': f_val, 'unit': unit_key, 'gender': 'FEMALE'},
            {'codeset_id': 0, 'op': 'bt', 'value': 0 if op in ('gt','gte') else f_val,
             'extent': f_val if op in ('gt','gte') else high, 'gender': 'FEMALE'},
        ]
        # No prior abnormal: same direction as entry
        abn = list(entry)
        return build_cohort(name,
                             [{'id': 0, 'name': name, 'concepts': concepts}],
                             entry, prior, abn)

    # 36. Hgb (M <13, F <12)
    save('v4_Hgb_low_sex', sex_specific_cohort(
        'Hgb_low_sex', HGB_CONCEPTS, 'lt', 13, 12, 'g/dL', fallback_range=(0, 13)))

    save('v4_Hct_low_sex', sex_specific_cohort(
        'Hct_low_sex', HCT_CONCEPTS, 'lt', 40, 36, '%', fallback_range=(0, 40)))
    save('v4_Ferritin_high_sex', sex_specific_cohort(
        'Ferritin_high_sex', FERRITIN_CONCEPTS, 'gt', 300, 200, 'ng/mL', fallback_range=(200, 5000)))
    save('v4_GGT_high_sex', sex_specific_cohort(
        'GGT_high_sex', GGT_CONCEPTS, 'gt', 55, 38, 'U/L', fallback_range=(38, 50000)))
    save('v4_ESR_high_sex', sex_specific_cohort(
        'ESR_high_sex', ESR_CONCEPTS, 'gt', 15, 20, 'mm/hr', fallback_range=(15, 500)))
    save('v4_UA_high_sex', sex_specific_cohort(
        'UA_high_sex', UA_CONCEPTS, 'gte', 7, 6, 'mg/dL', fallback_range=(6, 30)))
    save('v4_HDL_low_sex', sex_specific_cohort(
        'HDL_low_sex', HDL_CONCEPTS, 'lt', 40, 50, 'mg/dL', fallback_range=(0, 50)))
    save('v4_Creatinine_high_sex', sex_specific_cohort(
        'Creatinine_high_sex', CR_CONCEPTS, 'gt', 1.3, 1.1, 'mg/dL', fallback_range=(1.1, 20)))


if __name__ == '__main__':
    build_all()
    print(f"\n== Done. Output: {OUT_DIR} ==")
