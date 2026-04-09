"""완료된 기관 result.zip 일괄 다운로드 예제

CLI로도 가능:
    atlas-auto download --config config.yaml --project 2908 --analysis 10858 --research "패키지명"
"""
import os
from atlas_auto import FedernetClient

# ── 설정 ──
EMAIL = "your@email.com"          # feedernet 이메일
PASSWORD = "YOUR_PW"              # feedernet 비밀번호
PROJECT_ID = 2908                 # feedernet 프로젝트 ID
ANALYSIS_ID = 10858               # feedernet analysis ID
TARGET_RESEARCH = "E01_E04_clinical_ms_v6_nomatch"  # 연구 패키지명
OUTPUT_DIR = "./results"

# ── 실행 ──
client = FedernetClient()
client.login_portal(EMAIL, PASSWORD)

os.makedirs(OUTPUT_DIR, exist_ok=True)

groups = client.get_analysis_executions(PROJECT_ID, ANALYSIS_ID)

latest_completed = {}
for group in groups:
    if group.get("researchName") != TARGET_RESEARCH:
        continue
    for ex in group.get("executionList", []):
        if ex.get("executionStatus") == "FINISHED_SUCCESSFULLY":
            cdm = ex.get("cdmName", "?")
            if cdm not in latest_completed:
                latest_completed[cdm] = ex

print(f"완료된 기관: {len(latest_completed)}개\n")

for cdm, ex in sorted(latest_completed.items()):
    exec_id = ex["id"]
    save_name = f"{cdm}_{exec_id}_result.zip"
    save_path = os.path.join(OUTPUT_DIR, save_name)

    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        print(f"  [{cdm}] 이미 존재: {save_name}")
        continue

    try:
        print(f"  [{cdm}] {ex.get('orgName', '?')} 다운로드 중...", end="", flush=True)
        client.download_execution_result(PROJECT_ID, ANALYSIS_ID, exec_id, save_path)
        size_mb = os.path.getsize(save_path) / (1024 * 1024)
        print(f" {size_mb:.1f} MB")
    except Exception as e:
        print(f" FAILED: {e}")
