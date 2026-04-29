"""Create custom feature analyses for post-surgery measurement values."""
import sys, json, copy
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"g:\내 드라이브\KHNMC\atlas_auto_with_claude\automation")
from credentials import get_feedernet_credentials
from feedernet_client import FedernetClient

client = FedernetClient()
client.login_portal(*get_feedernet_credentials())
client.connect_site(7, 203)

session = client.session
webapi = client.webapi_url

# 기존 FA 227 (LDL-C) 구조를 템플릿으로
resp = session.get(f"{webapi}/feature-analysis/227", timeout=15)
template = resp.json()

time_windows = [
    ("Pre_365d",    365, -1,   1, -1),   # Start: 365일 전(-1), End: 1일 전(-1)
    ("Post_1_30d",    1,  1,  30,  1),   # Start: 1일 후(+1), End: 30일 후(+1)
    ("Post_31_90d",  31,  1,  90,  1),
    ("Post_91_365d", 91,  1, 365,  1),
    ("Post_1y_3y",  366,  1,1095,  1),
]

created_fas = []

for name, start_days, start_coeff, end_days, end_coeff in time_windows:
    fa = copy.deepcopy(template)

    # ID 제거 (새로 생성)
    fa.pop("id", None)
    fa.pop("createdDate", None)
    fa.pop("modifiedDate", None)
    fa.pop("hasWriteAccess", None)

    fa["name"] = f"[APP] MeasAll {name}"
    fa["descr"] = f"All measurement values, day {start_days*start_coeff} to {end_days*end_coeff}"
    fa["description"] = fa["descr"]

    # design 수정
    design = fa["design"][0]
    design.pop("id", None)
    design["name"] = name

    # ValueAsNumber 조건 제거 (모든 값 포함)
    criteria = design["expression"]["CriteriaList"][0]
    meas = criteria["Criteria"]["Measurement"]
    meas.pop("ValueAsNumber", None)

    # 시간 구간 설정
    criteria["StartWindow"] = {
        "Start": {"Days": start_days, "Coeff": start_coeff},
        "End": {"Days": end_days, "Coeff": end_coeff},
        "UseIndexEnd": False,
        "UseEventEnd": False,
    }

    # conceptSets 제거 (모든 measurement)
    fa["conceptSets"] = []
    meas["CodesetId"] = None

    resp = session.post(f"{webapi}/feature-analysis", json=fa, timeout=15)
    if resp.status_code == 200:
        result = resp.json()
        fa_id = result.get("id")
        created_fas.append((fa_id, name))
        print(f"  OK: ID={fa_id}, {name}")
    else:
        print(f"  FAIL: {name}: [{resp.status_code}] {resp.text[:300]}")

print(f"\nCreated: {len(created_fas)} feature analyses")

if created_fas:
    # Characterization 설계
    all_fas = [
        {"id": 71, "name": "Demographics Age Group", "type": "PRESET", "domain": "DEMOGRAPHICS"},
        {"id": 74, "name": "Demographics Gender", "type": "PRESET", "domain": "DEMOGRAPHICS"},
    ]
    for fa_id, name in created_fas:
        all_fas.append({"id": fa_id, "name": f"[APP] MeasAll {name}", "type": "CRITERIA_SET", "domain": "MEASUREMENT"})

    char_design = {
        "name": "Biomarker_PrePost_v3_custom",
        "cohorts": [
            {"id": 1072, "name": "E01_Appendectomy_ms"},
            {"id": 1074, "name": "E02_Cholecystectomy_ms"},
            {"id": 1121, "name": "E03_hernia_repair_ms"},
        ],
        "featureAnalyses": all_fas,
        "parameters": [],
        "stratas": [],
        "strataOnly": False,
        "strataConceptSets": [],
    }

    resp = session.post(f"{webapi}/cohort-characterization", json=char_design, timeout=15)
    if resp.status_code == 200:
        result = resp.json()
        char_id = result.get("id")
        print(f"\nCharacterization ID={char_id}")
        print(f"  cohorts: {len(result.get('cohorts', []))}, FAs: {len(result.get('featureAnalyses', []))}")

        resp2 = session.post(f"{webapi}/cohort-characterization/{char_id}/generation/cdmpv53_251128", timeout=30)
        if resp2.status_code == 200:
            gen = resp2.json()
            print(f"  Execution started: {gen.get('executionId', '?')}")
        else:
            print(f"  Exec failed: [{resp2.status_code}]")
    else:
        print(f"Char FAILED: [{resp.status_code}] {resp.text[:300]}")
