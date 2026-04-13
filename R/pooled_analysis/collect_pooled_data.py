"""
Pooled Analysis용 데이터 수집
- 각 기관별 export CSV (cohort_method_result, comparison_summary 등) 통합
- CmData zip 압축 해제 (IPD level CohortMethodData)
- 기관별 om (outcome model), Ps (propensity score), balance 파일 수집

Usage:
    python collect_pooled_data.py <results_dir> [pooled_dir]

    results_dir: 기관별 result.zip 해제된 폴더 (예: ./results_v7)
    pooled_dir:  출력 폴더 (기본: ./pooled_analysis 현재 디렉토리)
"""
import sys, os, shutil, csv, zipfile
from collections import defaultdict

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 경로 설정
if len(sys.argv) >= 2:
    RESULTS = sys.argv[1]
else:
    RESULTS = os.path.join(os.path.dirname(__file__), "..", "..", "results")

if len(sys.argv) >= 3:
    POOLED = sys.argv[2]
else:
    POOLED = os.path.dirname(__file__) or "."

os.makedirs(POOLED, exist_ok=True)
os.makedirs(os.path.join(POOLED, "export_combined"), exist_ok=True)
os.makedirs(os.path.join(POOLED, "cmData"), exist_ok=True)

# 기관 목록
sites = [d for d in os.listdir(RESULTS) if os.path.isdir(os.path.join(RESULTS, d))]
sites.sort()
print(f"=== {len(sites)}개 기관 ===")
for s in sites:
    print(f"  {s}")

# 1. Export CSV 통합 (기관별 database_id로 구분됨)
print("\n=== 1. Export CSV 통합 ===")
csv_files = [
    "cohort_method_result.csv",
    "comparison_summary.csv",
    "covariate_balance.csv",
    "exposure_summary.csv",
    "attrition.csv",
    "cm_follow_up_dist.csv",
    "covariate.csv",
    "covariate_analysis.csv",
    "database.csv",
    "exposure_of_interest.csv",
    "kaplan_meier_dist.csv",
    "negative_control_outcome.csv",
    "outcome_of_interest.csv",
    "preference_score_dist.csv",
    "propensity_model.csv",
    "likelihood_profile.csv",
]

for csv_name in csv_files:
    combined_rows = []
    header = None

    for site in sites:
        csv_path = os.path.join(RESULTS, site, "script", "extras", "result", "export", csv_name)
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            h = next(reader)
            if header is None:
                header = h
            for row in reader:
                combined_rows.append(row)

    if header and combined_rows:
        out_path = os.path.join(POOLED, "export_combined", csv_name)
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(combined_rows)
        print(f"  {csv_name}: {len(combined_rows)}행 ({len(sites)}개 기관)")

# 2. CmData zip 압축 해제
print("\n=== 2. CmData zip 압축 해제 ===")
for site in sites:
    cm_dir = os.path.join(RESULTS, site, "script", "extras", "result", "cmOutput")
    if not os.path.isdir(cm_dir):
        continue

    for zf in os.listdir(cm_dir):
        if zf.startswith("CmData") and zf.endswith(".zip"):
            base = zf.replace(".zip", "")
            out_dir = os.path.join(POOLED, "cmData", site, base)
            os.makedirs(out_dir, exist_ok=True)

            zip_path = os.path.join(cm_dir, zf)
            try:
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(out_dir)
                size_mb = os.path.getsize(zip_path) / (1024*1024)
                print(f"  {site}/{zf} ({size_mb:.1f} MB)")
            except Exception as e:
                print(f"  {site}/{zf} FAILED: {e}")

# 3. 주요 결과 파일 요약
print("\n=== 3. Pooled cohort_method_result 요약 ===")
cmr_path = os.path.join(POOLED, "export_combined", "cohort_method_result.csv")
if os.path.exists(cmr_path):
    with open(cmr_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    tco_sites = defaultdict(set)
    tco_has_result = defaultdict(int)

    for row in rows:
        key = (row["target_id"], row["comparator_id"], row["outcome_id"])
        tco_sites[key].add(row["database_id"])
        if row.get("rr") and row["rr"] != "NA":
            tco_has_result[key] += 1

    print(f"  총 {len(rows)}행, {len(tco_sites)} TCO 조합")
    print(f"\n  {'Target':>8} {'Comp':>8} {'Outcome':>8} {'기관수':>6} {'결과有':>6}")
    print(f"  {'-'*45}")
    for key in sorted(tco_sites.keys()):
        t, c, o = key
        n_sites = len(tco_sites[key])
        n_result = tco_has_result.get(key, 0)
        print(f"  {t:>8} {c:>8} {o:>8} {n_sites:>6} {n_result:>6}")

print(f"\n=== 완료 ===")
