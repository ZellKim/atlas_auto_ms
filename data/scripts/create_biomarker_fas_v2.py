"""Create biomarker FAs using copy+PUT method (FA 372 as template)."""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"g:\내 드라이브\KHNMC\atlas_auto_with_claude\automation")
from credentials import get_feedernet_credentials
from feedernet_client import FedernetClient

client = FedernetClient()
client.login_portal(*get_feedernet_credentials())
client.connect_site(7, 203)

session = client.session
webapi = client.webapi_url

biomarkers = [
    (3000905, "WBC", "Leukocytes [#/volume] in Blood"),
    (3017732, "Neutro", "Neutrophils [#/volume] in Blood"),
    (3004327, "Lympho", "Lymphocytes [#/volume] in Blood"),
    (3013115, "Eosino", "Eosinophils [#/volume] in Blood"),
    (3002385, "Mono", "Monocytes [#/volume] in Blood"),
    (3037575, "Baso", "Basophils [#/volume] in Blood"),
    (3020460, "CRP", "C reactive protein [Mass/volume]"),
    (3013707, "ESR", "Erythrocyte sedimentation rate"),
    (3004501, "Gluc", "Glucose [Mass/volume] in Serum or Plasma"),
    (3004410, "HbA1c", "Hemoglobin A1c/Hemoglobin.total"),
    (3028437, "LDL", "Cholesterol in LDL [Mass/volume]"),
    (3022192, "TG", "Triglyceride [Mass/volume]"),
    (3007070, "HDL", "Cholesterol in HDL [Mass/volume]"),
    (3030354, "GFR", "Glomerular filtration rate"),
    (3000285, "UA", "Urate [Mass/volume]"),
    (3006923, "ALT", "Alanine aminotransferase [Enzymatic activity/volume]"),
    (3004077, "GGT", "Gamma glutamyl transferase [Enzymatic activity/volume]"),
    (3035995, "ALP", "Alkaline phosphatase [Enzymatic activity/volume]"),
    (3000963, "Hgb", "Hemoglobin [Mass/volume] in Blood"),
]

time_windows = [
    ("Pre365",   365, -1,   1, -1),
    ("Pst1_30",    1,  1,  30,  1),
    ("Pst31_90",  31,  1,  90,  1),
    ("Pst91_365", 91,  1, 365,  1),
    ("Pst1y3y",  366,  1,1095,  1),
]

created = []
failed = []

for concept_id, short, concept_name in biomarkers:
    for wname, sd, sc, ed, ec in time_windows:
        # Step 1: Copy FA 372
        resp = session.get(f"{webapi}/feature-analysis/372/copy", timeout=15)
        if resp.status_code != 200:
            failed.append(f"{short}_{wname}: copy failed")
            continue

        fa = resp.json()
        new_id = fa["id"]

        # Step 2: PUT - name, time window, concept
        fa["name"] = f"[BIO] {short}_{wname}"

        # time window
        fa["design"][0]["expression"]["StartWindow"] = {
            "Start": {"Days": sd, "Coeff": sc},
            "End": {"Days": ed, "Coeff": ec},
            "UseIndexEnd": False, "UseEventEnd": False,
        }

        # concept
        fa["design"][0]["expression"]["Criteria"]["Measurement"]["CodesetId"] = 0
        fa["conceptSets"] = [{
            "id": 0,
            "name": short,
            "expression": {
                "items": [{
                    "concept": {
                        "CONCEPT_ID": concept_id,
                        "CONCEPT_NAME": concept_name,
                        "STANDARD_CONCEPT": "S",
                        "STANDARD_CONCEPT_CAPTION": "Standard",
                        "INVALID_REASON": "V",
                        "INVALID_REASON_CAPTION": "Valid",
                        "DOMAIN_ID": "Measurement",
                        "VOCABULARY_ID": "LOINC",
                        "CONCEPT_CLASS_ID": "Lab Test",
                    },
                    "isExcluded": False,
                    "includeDescendants": True,
                    "includeMapped": False,
                }]
            }
        }]

        resp2 = session.put(f"{webapi}/feature-analysis/{new_id}", json=fa, timeout=15)
        if resp2.status_code == 200:
            created.append((new_id, short, wname))
            sys.stdout.write(".")
            sys.stdout.flush()
        else:
            failed.append(f"{short}_{wname}: PUT [{resp2.status_code}]")
            session.delete(f"{webapi}/feature-analysis/{new_id}", timeout=15)

print(f"\nCreated: {len(created)} / Failed: {len(failed)}")
if failed:
    for f in failed[:10]:
        print(f"  {f}")

# Characterization
if created:
    all_fas = [
        {"id": 71, "type": "PRESET", "domain": "DEMOGRAPHICS"},
        {"id": 74, "type": "PRESET", "domain": "DEMOGRAPHICS"},
    ]
    for fa_id, _, _ in created:
        all_fas.append({"id": fa_id, "type": "CRITERIA_SET", "domain": "MEASUREMENT"})

    char = {
        "name": "BiomarkerFull_PrePost",
        "cohorts": [
            {"id": 1072, "name": "E01_Appendectomy_ms"},
            {"id": 1074, "name": "E02_Cholecystectomy_ms"},
            {"id": 1121, "name": "E03_hernia_repair_ms"},
        ],
        "featureAnalyses": all_fas,
        "parameters": [], "stratas": [], "strataOnly": False, "strataConceptSets": [],
    }

    resp = session.post(f"{webapi}/cohort-characterization", json=char, timeout=15)
    if resp.status_code == 200:
        char_id = resp.json().get("id")
        print(f"\nCharacterization ID={char_id} ({len(all_fas)} FAs)")
        resp2 = session.post(f"{webapi}/cohort-characterization/{char_id}/generation/cdmpv53_251128", timeout=30)
        if resp2.status_code == 200:
            print(f"Execution started: gen={resp2.json().get('executionId', '?')}")
    else:
        print(f"Char failed: [{resp.status_code}]")

with open(r"C:\Users\data1\Desktop\atlas_auto_cmdata\biomarker_fa_ids.json", "w") as f:
    json.dump(created, f, indent=2)
