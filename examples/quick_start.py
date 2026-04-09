"""
Quick Start - atlas-auto 사용 예제
===================================
pip install atlas-auto (또는 pip install -e .) 후 실행
"""

from atlas_auto import FedernetClient, EstimationBuilder


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 1: 로그인 & 기관 연결
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def step1_login() -> FedernetClient:
    client = FedernetClient()

    # 방법 A: 이메일/PW
    # client.login_portal("your@email.com", "YOUR_PW")

    # 방법 B: 브라우저 쿠키
    # client.login_with_cookie_string("JSESSIONID=abc123; token=xyz456")

    # 방법 C: Bearer 토큰
    # client.login_with_bearer_token("eyJhbGciOiJIUzUxMiJ9...")

    # 기관 연결 (ATLAS URL에서 group_id, site_id 추출)
    # client.connect_site(7, 203)
    # 또는: client.connect_site(atlas_url="https://www.feedernet.com/atlas-resolve/v2.12.0/7/203/main")

    return client


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 2: 탐색
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def step2_explore(client: FedernetClient):
    sources = client.get_sources()
    for s in sources:
        print(f"소스: {s.get('sourceName')} (key={s.get('sourceKey')})")

    cohorts = client.list_cohort_definitions()
    print(f"\n코호트: {len(cohorts)}개")
    for c in cohorts[:20]:
        print(f"  ID={c.get('id')}: {c.get('name')}")

    estimations = client.list_estimations()
    print(f"\nEstimation: {len(estimations)}개")
    for e in estimations[:10]:
        print(f"  ID={e.get('id')}: {e.get('name')}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 3: 코호트 업로드 & Generate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def step3_cohorts(client: FedernetClient, package_dir: str) -> dict:
    from pathlib import Path

    cohorts_dir = Path(package_dir) / "inst" / "cohorts"
    source_key = client.get_source_key()

    # 코호트명 맵 (자신의 연구에 맞게 수정)
    cohort_names = {
        1072: "E01_Appendectomy",
        1074: "E02_Cholecystectomy",
        # ... 추가
    }

    cohort_map = {}
    for cid, name in cohort_names.items():
        json_path = cohorts_dir / f"{cid}.json"
        if json_path.exists():
            result = client.create_cohort_from_json_file(f"[Auto] {name}", str(json_path))
            cohort_map[cid] = result["id"]
            print(f"  {cid} -> {result['id']} ({name})")

    # Generate
    for local_id, remote_id in cohort_map.items():
        client.generate_cohort(remote_id, source_key)

    for local_id, remote_id in cohort_map.items():
        ok = client.wait_for_cohort_generation(remote_id, source_key)
        print(f"  코호트 {remote_id}: {'OK' if ok else 'FAILED'}")

    return cohort_map


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 4: Estimation 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def step4_estimation(client: FedernetClient, package_dir: str, cohort_map: dict):
    builder = EstimationBuilder.from_existing_package(package_dir)
    spec = builder.build()

    # 코호트 ID 매핑 적용
    for cd in spec.get("cohortDefinitions", []):
        if cd["id"] in cohort_map:
            cd["id"] = cohort_map[cd["id"]]

    tcos = spec["estimationAnalysisSettings"]["analysisSpecification"]["targetComparatorOutcomes"]
    for tco in tcos:
        if tco["targetId"] in cohort_map:
            tco["targetId"] = cohort_map[tco["targetId"]]
        if tco["comparatorId"] in cohort_map:
            tco["comparatorId"] = cohort_map[tco["comparatorId"]]
        tco["outcomeIds"] = [cohort_map.get(oid, oid) for oid in tco["outcomeIds"]]

    # Import & 실행
    est_result = client.import_estimation(spec)
    est_id = est_result["id"]
    print(f"Estimation Import: ID={est_id}")

    source_key = client.get_source_key()
    client.run_estimation(est_id, source_key)

    gen_info = client.wait_for_estimation(est_id, timeout=3600)
    status = gen_info.get("status", {}).get("name", "?") if gen_info else "TIMEOUT"
    print(f"Estimation: {status}")

    if status == "COMPLETE":
        from pathlib import Path
        Path("./output").mkdir(exist_ok=True)
        gen_id = gen_info["id"]
        client.download_estimation_results(gen_id, f"./output/results_{gen_id}.zip")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    print("""
atlas-auto Quick Start
======================
아래 코드의 주석을 해제하고 credentials을 입력하세요.
""")

    # client = step1_login()
    # step2_explore(client)
    # cohort_map = step3_cohorts(client, "/path/to/study_package")
    # step4_estimation(client, "/path/to/study_package", cohort_map)
