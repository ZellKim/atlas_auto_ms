"""4개 바이오마커 multi-concept 코호트 생성 (KHNMC)"""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"g:\내 드라이브\KHNMC\atlas_auto_with_claude\automation")
from feedernet_client import FedernetClient

c = FedernetClient()
c.login_portal("20230172@khnmc.or.kr", "rlaaudtjr1!")
c.connect_site(7, 203)

def concept(cid, name, loinc):
    return {"concept": {
        "CONCEPT_ID": cid, "CONCEPT_NAME": name,
        "STANDARD_CONCEPT": "S", "STANDARD_CONCEPT_CAPTION": "Standard",
        "INVALID_REASON": "V", "INVALID_REASON_CAPTION": "Valid",
        "DOMAIN_ID": "Measurement", "VOCABULARY_ID": "LOINC",
        "CONCEPT_CLASS_ID": "Lab Test", "CONCEPT_CODE": loinc
    }, "isExcluded": False, "includeDescendants": True, "includeMapped": False}

def primary(csid, cutoff, op="gt"):
    return {"Measurement": {"CodesetId": csid, "ValueAsNumber": {"Value": cutoff, "Op": op}}}

def inc_normal(csid, cutoff, op="lte"):
    return {"Criteria": {"Measurement": {"CodesetId": csid, "ValueAsNumber": {"Value": cutoff, "Op": op}}},
            "StartWindow": {"Start": {"Days": 365, "Coeff": -1}, "End": {"Days": 1, "Coeff": -1}, "UseEventEnd": False},
            "Occurrence": {"Type": 2, "Count": 1}}

def inc_no_prior(csid, cutoff, op="gt"):
    return {"Criteria": {"Measurement": {"CodesetId": csid, "ValueAsNumber": {"Value": cutoff, "Op": op}}},
            "StartWindow": {"Start": {"Coeff": -1}, "End": {"Days": 1, "Coeff": -1}, "UseEventEnd": False},
            "Occurrence": {"Type": 0, "Count": 0}}

def make_cohort(concept_sets, primaries, normals, no_priors):
    return {
        "cdmVersionRange": ">=5.0.0",
        "ConceptSets": concept_sets,
        "PrimaryCriteria": {
            "CriteriaList": primaries,
            "ObservationWindow": {"PriorDays": 0, "PostDays": 0},
            "PrimaryCriteriaLimit": {"Type": "First"}
        },
        "QualifiedLimit": {"Type": "First"}, "ExpressionLimit": {"Type": "First"},
        "InclusionRules": [
            {"name": "Prior normal (365d)", "expression": {
                "Type": "ALL", "CriteriaList": normals,
                "DemographicCriteriaList": [], "Groups": []}},
            {"name": "No prior abnormal", "expression": {
                "Type": "ALL", "CriteriaList": no_priors,
                "DemographicCriteriaList": [], "Groups": []}}
        ],
        "EndStrategy": {"DateOffset": {"DateField": "StartDate", "Offset": 1}},
        "CensoringCriteria": [], "CollapseSettings": {"CollapseType": "ERA", "EraPad": 0}, "CensorWindow": {}
    }

# ===== 1. WBC: 3000905 + 3010813 (둘 다 #/vol, cutoff >11) =====
wbc = make_cohort(
    concept_sets=[
        {"id": 0, "name": "WBC_3000905", "expression": {"items": [concept(3000905, "Leukocytes [#/volume] in Blood", "6690-2")]}},
        {"id": 1, "name": "WBC_3010813", "expression": {"items": [concept(3010813, "Leukocytes [#/volume] in Blood", "26464-8")]}},
    ],
    primaries=[primary(0, 11), primary(1, 11)],
    normals=[inc_normal(0, 11), inc_normal(1, 11)],
    no_priors=[inc_no_prior(0, 11), inc_no_prior(1, 11)],
)

# ===== 2. Neutro: 3017354(seg%, >70) + 3018010(%, >70) + 3017732(#/vol, >7.7) =====
neutro = make_cohort(
    concept_sets=[
        {"id": 0, "name": "SegNeutro_pct", "expression": {"items": [concept(3017354, "Segmented neutrophils/100 leukocytes in Blood", "770-8")]}},
        {"id": 1, "name": "Neutro_pct", "expression": {"items": [concept(3018010, "Neutrophils/100 leukocytes in Blood", "26511-6")]}},
        {"id": 2, "name": "Neutro_abs", "expression": {"items": [concept(3017732, "Neutrophils [#/volume] in Blood", "26499-4")]}},
    ],
    primaries=[primary(0, 70), primary(1, 70), primary(2, 7.7)],
    normals=[inc_normal(0, 70), inc_normal(1, 70), inc_normal(2, 7.7)],
    no_priors=[inc_no_prior(0, 70), inc_no_prior(1, 70), inc_no_prior(2, 7.7)],
)

# ===== 3. Mono: 3019069(%, >12) + 3002385(#/vol, >0.8) =====
mono = make_cohort(
    concept_sets=[
        {"id": 0, "name": "Mono_pct", "expression": {"items": [concept(3019069, "Monocytes/100 leukocytes in Blood", "26485-3")]}},
        {"id": 1, "name": "Mono_abs", "expression": {"items": [concept(3002385, "Monocytes [#/volume] in Blood", "26484-6")]}},
    ],
    primaries=[primary(0, 12), primary(1, 0.8)],
    normals=[inc_normal(0, 12), inc_normal(1, 0.8)],
    no_priors=[inc_no_prior(0, 12), inc_no_prior(1, 0.8)],
)

# ===== 4. Glucose DM: 3004501(>=126) + 3037110(fasting, >=126) =====
glucose_dm = make_cohort(
    concept_sets=[
        {"id": 0, "name": "Glucose", "expression": {"items": [concept(3004501, "Glucose [Mass/volume] in Serum or Plasma", "2345-7")]}},
        {"id": 1, "name": "Fasting_glucose", "expression": {"items": [concept(3037110, "Fasting glucose [Mass/volume] in Serum or Plasma", "1558-6")]}},
    ],
    primaries=[primary(0, 126, "gte"), primary(1, 126, "gte")],
    normals=[inc_normal(0, 126, "lt"), inc_normal(1, 126, "lt")],
    no_priors=[inc_no_prior(0, 126, "gte"), inc_no_prior(1, 126, "gte")],
)

# KHNMC에 생성
cohorts = [
    ("B_WBC_v2_multiConcept", wbc),
    ("B_Neutro_v2_multiConcept", neutro),
    ("B_Mono_v2_multiConcept", mono),
    ("B_GlucDM_v2_multiConcept", glucose_dm),
]

for name, expr in cohorts:
    result = c.create_cohort_definition(name, expr)
    cid = result.get("id", "?")
    print(f"{name}: cohort id={cid}")
    # JSON도 저장
    with open(f"C:/Users/data1/Desktop/atlas_auto_cmdata/{name}.json", "w", encoding="utf-8") as f:
        json.dump(expr, f, indent=2, ensure_ascii=False)
