"""17개 바이오마커 × 5 시간구간 Characterization 생성 + 14개 기관 배포"""
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"g:\내 드라이브\0.claude_workspace\data_analysis\atlas_auto_with_claude\automation")
from credentials import get_feedernet_credentials
from feedernet_client import FedernetClient


def get_latest_static_source(sources):
    static = []
    for s in sources:
        sn = s["sourceName"]
        if "monthly" in sn.lower() or "weekly" in sn.lower():
            continue
        m = re.search(r"_(\d+)$", sn)
        if m:
            static.append((int(m.group(1)), s))
    if static:
        return sorted(static, key=lambda x: x[0])[-1][1]
    return sources[-1] if sources else None


# 17개 바이오마커
BIOMARKERS = [
    (3000905, "WBC", "Leukocytes [#/volume] in Blood"),
    (3017732, "Neutro", "Neutrophils [#/volume] in Blood"),
    (3004327, "Lympho", "Lymphocytes [#/volume] in Blood"),
    (3013115, "Eosino", "Eosinophils [#/volume] in Blood"),
    (3002385, "Mono", "Monocytes [#/volume] in Blood"),
    (3037575, "Baso", "Basophils [#/volume] in Blood"),
    (3020460, "CRP", "C reactive protein [Mass/volume] in Serum or Plasma"),
    (3013707, "ESR", "Erythrocyte sedimentation rate"),
    (3004501, "GlucDM", "Glucose [Mass/volume] in Serum or Plasma"),
    (3004501, "GlucPre", "Glucose [Mass/volume] in Serum or Plasma"),
    (3004410, "HbA1c", "Hemoglobin A1c/Hemoglobin.total in Blood"),
    (3022192, "TG", "Triglyceride [Mass/volume] in Serum or Plasma"),
    (3007070, "HDL", "Cholesterol in HDL [Mass/volume] in Serum or Plasma"),
    (3006923, "ALT", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
    (3000963, "Hgb", "Hemoglobin [Mass/volume] in Blood"),
    (3000285, "UA", "Urate [Mass/volume] in Serum or Plasma"),
    (3024561, "Alb", "Albumin [Mass/volume] in Serum or Plasma"),
]

TIME_WINDOWS = [
    ("Pre365", 365, -1, 1, -1),
    ("Pst1_30", 1, 1, 30, 1),
    ("Pst31_90", 31, 1, 90, 1),
    ("Pst91_365", 91, 1, 365, 1),
    ("Pst1y3y", 366, 1, 1095, 1),
]

# ===== Phase 1: KHNMC에서 template FA 생성 =====
print("=== Phase 1: KHNMC에서 FA 생성 ===")
client = FedernetClient()
client.login_portal(*get_feedernet_credentials())
client.connect_site(7, 203)

# FA 372 (WindowedCriteria template) 존재 확인
resp = client.session.get(f"{client.webapi_url}/feature-analysis/372", timeout=15)
template_id = 372
print(f"Template FA 372: {resp.json().get('name')}")

# 17 × 5 = 85개 FA 생성 (copy+PUT 2단계)
created_fas = []

for concept_id, short, concept_name in BIOMARKERS:
    for wname, sd, sc, ed, ec in TIME_WINDOWS:
        fa_name = f"[B17] {short}_{wname}"

        # copy
        resp = client.session.get(f"{client.webapi_url}/feature-analysis/{template_id}/copy", timeout=15)
        if resp.status_code != 200:
            print(f"  FAIL copy: {fa_name}")
            continue

        new_fa = resp.json()
        new_id = new_fa["id"]

        # 1차 PUT: 이름 + 시간
        new_fa["name"] = fa_name
        new_fa["design"][0]["expression"]["StartWindow"] = {
            "Start": {"Days": sd, "Coeff": sc},
            "End": {"Days": ed, "Coeff": ec},
            "UseIndexEnd": False, "UseEventEnd": False,
        }

        resp2 = client.session.put(f"{client.webapi_url}/feature-analysis/{new_id}", json=new_fa, timeout=15)
        if resp2.status_code != 200:
            print(f"  FAIL PUT1: {fa_name}")
            client.session.delete(f"{client.webapi_url}/feature-analysis/{new_id}", timeout=15)
            continue

        # 2차 PUT: concept
        fa_updated = resp2.json()
        fa_updated["design"][0]["expression"]["Criteria"]["Measurement"]["CodesetId"] = 0
        fa_updated["conceptSets"] = [{
            "id": 0, "name": short,
            "expression": {"items": [{
                "concept": {
                    "CONCEPT_ID": concept_id, "CONCEPT_NAME": concept_name,
                    "STANDARD_CONCEPT": "S", "STANDARD_CONCEPT_CAPTION": "Standard",
                    "INVALID_REASON": "V", "INVALID_REASON_CAPTION": "Valid",
                    "DOMAIN_ID": "Measurement", "VOCABULARY_ID": "LOINC",
                    "CONCEPT_CLASS_ID": "Lab Test",
                },
                "isExcluded": False, "includeDescendants": True, "includeMapped": False,
            }]}
        }]

        resp3 = client.session.put(f"{client.webapi_url}/feature-analysis/{new_id}", json=fa_updated, timeout=15)
        if resp3.status_code == 200:
            created_fas.append(new_id)
            sys.stdout.write(".")
            sys.stdout.flush()
        else:
            print(f"  FAIL PUT2: {fa_name}")
            client.session.delete(f"{client.webapi_url}/feature-analysis/{new_id}", timeout=15)

print(f"\nCreated {len(created_fas)} FAs in KHNMC")

# Characterization 생성
all_fas = [{"id": 74, "type": "PRESET", "domain": "DEMOGRAPHICS"}]
for fid in created_fas:
    all_fas.append({"id": fid, "type": "CRITERIA_SET", "domain": "MEASUREMENT"})

char = {
    "name": "Bio17_PrePost_v2",
    "cohorts": [{"id": 1072, "name": "E01_Appendectomy_ms"}],
    "featureAnalyses": all_fas,
    "parameters": [], "stratas": [], "strataOnly": False, "strataConceptSets": [],
}

resp = client.session.post(f"{client.webapi_url}/cohort-characterization", json=char, timeout=15)
khnmc_char_id = resp.json().get("id")
print(f"KHNMC Characterization ID={khnmc_char_id} ({len(all_fas)} FAs)")

# KHNMC에서 실행
sk = "cdmpv53_251128"
client.generate_cohort(1072, sk)
client.wait_for_cohort_generation(1072, sk, timeout=300)
resp2 = client.session.post(f"{client.webapi_url}/cohort-characterization/{khnmc_char_id}/generation/{sk}", timeout=30)
print(f"KHNMC execution: gen={resp2.json().get('executionId', '?')}")

# Export
resp_exp = client.session.get(f"{client.webapi_url}/cohort-characterization/{khnmc_char_id}/export", timeout=30)
char_export = resp_exp.json()
print(f"Exported: {len(char_export.get('featureAnalyses', []))} FAs")

# ===== Phase 2: 13개 기관 배포 (KHNMC 제외) =====
print("\n=== Phase 2: 13개 기관 배포 ===")

sites_13 = [
    (9, 191, "AUMC"), (95, 227, "CHNUH"), (16, 196, "DCMC"),
    (86, 224, "GNUCH"), (88, 198, "GNUH"), (117, 256, "HUMC"),
    (81, 222, "ISH"), (93, 226, "JCMJ"), (4, 201, "KDH"),
    (10, 213, "KWMC"), (28, 207, "SCHCA"), (30, 208, "SCHGM"),
    (27, 209, "SCHSU"),
]

for gid, sid, code in sites_13:
    try:
        c = FedernetClient()
        c.login_portal(*get_feedernet_credentials())
        c.connect_site(gid, sid)

        sources = c.get_sources()
        latest = get_latest_static_source(sources)
        if not latest:
            print(f"  {code}: NO SOURCE")
            continue
        sk = latest["sourceKey"]

        # import
        imp = json.loads(json.dumps(char_export))
        imp.pop("id", None)
        imp["name"] = f"Bio17_{code}"

        resp = c.session.post(f"{c.webapi_url}/cohort-characterization/import", json=imp, timeout=30)
        if resp.status_code != 200:
            print(f"  {code}: Import FAILED")
            continue

        cid = resp.json().get("id")

        # 코호트 Generate
        cohorts = c.list_cohort_definitions()
        app = [co for co in cohorts if "Appendectomy" in co.get("name", "")]
        if app:
            c.generate_cohort(app[-1]["id"], sk)
            c.wait_for_cohort_generation(app[-1]["id"], sk, timeout=300)

        # 실행
        resp2 = c.session.post(f"{c.webapi_url}/cohort-characterization/{cid}/generation/{sk}", timeout=30)
        if resp2.status_code == 200:
            print(f"  {code}: OK (Char={cid}, {latest['sourceName']})")
        else:
            print(f"  {code}: Exec FAILED")
    except Exception as e:
        print(f"  {code}: ERROR {str(e)[:60]}")

print("\nDone")
