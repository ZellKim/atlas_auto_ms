"""다기관 Characterization 배포 — KHNMC export → 각 기관 import + 실행"""
import sys, json, re, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"g:\내 드라이브\KHNMC\atlas_auto_with_claude\automation")
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


# ===== Phase 1: KHNMC에서 Characterization export =====
print("=== Phase 1: KHNMC export ===")
client = FedernetClient()
client.login_portal(*get_feedernet_credentials())
client.connect_site(7, 203)

# Char 121 (Quick_5bio_test) export — WBC/Neutro/Lympho/CRP 포함
resp = client.session.get(f"{client.webapi_url}/cohort-characterization/121/export", timeout=30)
char_json = resp.json()
print(f"  Exported: {char_json['name']}")
print(f"  Cohorts: {len(char_json.get('cohorts', []))}")
print(f"  FAs: {len(char_json.get('featureAnalyses', []))}")

# ===== Phase 2: 각 기관에 import + 실행 =====
# 분석에 포함된 14개 기관 (CAUHS, DAEGU_DONGSAN 제외) + 추가 대기 기관
sites = [
    # (group_id, site_id, code, name)
    (9, 191, "AUMC", "아주대학교병원"),
    (95, 227, "CHNUH", "충남대학교병원"),
    (16, 196, "DCMC", "대구가톨릭대학교병원"),
    (86, 224, "GNUCH", "창원경상국립대학교병원"),  # 이미 실행됨 — skip
    (88, 198, "GNUH", "경상국립대학교병원"),
    (117, 256, "HUMC", "동탄성심병원"),
    (81, 222, "ISH", "국제성모병원"),
    (69, 226, "JCMJ", "제천명지병원"),
    (4, 201, "KDH", "강동성심병원"),
    # (7, 203, "KHNMC", "강동경희대학교병원"),  # 이미 실행 중
    (10, 213, "KWMC", "강원대학교병원"),
    (28, 207, "SCHCA", "순천향대 천안병원"),
    (30, 208, "SCHGM", "순천향대 구미병원"),
    (27, 209, "SCHSU", "순천향대 서울병원"),
    (29, 206, "SCHBC", "순천향대 부천병원"),
]

results = []

for gid, sid, code, name in sites:
    print(f"\n=== {code} ({name}) [{gid}/{sid}] ===")

    try:
        c = FedernetClient()
        c.login_portal(*get_feedernet_credentials())
        c.connect_site(gid, sid)

        # source 확인
        sources = c.get_sources()
        latest = get_latest_static_source(sources)
        if not latest:
            print(f"  NO SOURCE")
            results.append({"code": code, "status": "NO_SOURCE"})
            continue

        sk = latest["sourceKey"]
        print(f"  Source: {latest['sourceName']} ({sk})")

        # import
        import_json = json.loads(json.dumps(char_json))
        import_json.pop("id", None)
        import_json["name"] = f"BioPrePost_{code}"

        resp = c.session.post(
            f"{c.webapi_url}/cohort-characterization/import",
            json=import_json, timeout=30,
        )
        if resp.status_code != 200:
            print(f"  Import FAILED [{resp.status_code}]")
            results.append({"code": code, "status": "IMPORT_FAILED"})
            continue

        char_id = resp.json().get("id")
        print(f"  Imported: Char ID={char_id}")

        # 코호트 Generate
        cohorts = c.list_cohort_definitions()
        app = [co for co in cohorts if "Appendectomy" in co.get("name", "")]
        if app:
            cid = app[-1]["id"]
            print(f"  Generating cohort {cid}...")
            c.generate_cohort(cid, sk)
            c.wait_for_cohort_generation(cid, sk, timeout=300)
        else:
            print(f"  Appendectomy cohort not found — may be created by import")

        # Characterization 실행
        resp2 = c.session.post(
            f"{c.webapi_url}/cohort-characterization/{char_id}/generation/{sk}",
            timeout=30,
        )
        if resp2.status_code == 200:
            gen_id = resp2.json().get("executionId", "?")
            print(f"  Execution started: gen={gen_id}")
            results.append({
                "code": code, "name": name,
                "group_id": gid, "site_id": sid,
                "char_id": char_id, "gen_id": gen_id,
                "source": latest["sourceName"],
                "sourceKey": sk,
                "status": "STARTED",
            })
        else:
            print(f"  Exec FAILED [{resp2.status_code}]")
            results.append({"code": code, "status": "EXEC_FAILED"})

    except Exception as e:
        print(f"  ERROR: {str(e)[:100]}")
        results.append({"code": code, "status": f"ERROR: {str(e)[:80]}"})

# 결과 저장
with open(r"C:\Users\data1\Desktop\atlas_auto_cmdata\char_multisite_deploy.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n\n=== Summary ===")
started = sum(1 for r in results if r.get("status") == "STARTED")
failed = sum(1 for r in results if r.get("status") != "STARTED")
print(f"Started: {started}, Failed: {failed}")
for r in results:
    print(f"  {r.get('code', '?')}: {r.get('status', '?')}")
