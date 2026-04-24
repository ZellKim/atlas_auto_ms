"""
Pooled Analysis 업데이트 파이프라인
1. feedernet에서 신규 완료 기관 확인
2. 신규 result.zip 다운로드 & 압축 해제
3. CmData 추출
4. R Cyclops pooled analysis 재실행

사용법:
  python update_and_rerun.py              # 전체 파이프라인 (다운로드 + 분석)
  python update_and_rerun.py --check      # 현황만 확인
  python update_and_rerun.py --download   # 다운로드만
  python update_and_rerun.py --analyze    # 분석만 (이미 다운로드된 데이터로)
"""
import sys, os, json, zipfile, argparse, subprocess
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "automation"))
from feedernet_client import FedernetClient

# ─── 설정 ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "..", "results")
CMDATA_DIR = os.path.join(BASE_DIR, "cmData")
R_SCRIPT = os.path.join(BASE_DIR, "ipd_pooled_cyclops.R")
R_EXE = r"C:\Program Files\R\R-4.3.1\bin\Rscript.exe"

PROJECT_ID = 2908
ANALYSIS_ID = 10858
TARGET_RESEARCH = "E01_E04_clinical_ms_v6_nomatch"

EMAIL = "20230172@khnmc.or.kr"
PASSWORD = "rlaaudtjr1!"


def login():
    client = FedernetClient()
    client.login_portal(EMAIL, PASSWORD)
    return client


def get_completed_executions(client):
    """완료된 execution 중 TARGET_RESEARCH만 필터 (기관별 최신)"""
    session = client.session
    base = client.portal_url

    resp = session.get(
        f"{base}/api/v1/project/{PROJECT_ID}/analysis/{ANALYSIS_ID}/execution",
        timeout=30)
    resp.raise_for_status()
    groups = resp.json().get("content", [])

    latest = {}
    for group in groups:
        if group.get("researchName") != TARGET_RESEARCH:
            continue
        for ex in group.get("executionList", []):
            if ex.get("executionStatus") == "FINISHED_SUCCESSFULLY":
                cdm = ex.get("cdmName", "?")
                if cdm not in latest:
                    latest[cdm] = ex
    return latest


def get_already_downloaded():
    """이미 다운로드 & 압축 해제된 기관 목록"""
    if not os.path.isdir(RESULTS_DIR):
        return set()
    downloaded = set()
    for d in os.listdir(RESULTS_DIR):
        full = os.path.join(RESULTS_DIR, d)
        if os.path.isdir(full) and os.path.isdir(os.path.join(full, "script")):
            downloaded.add(d)
    return downloaded


def check_status(client):
    """현재 상태 확인"""
    completed = get_completed_executions(client)
    downloaded = get_already_downloaded()

    # 실행 현황도 확인
    session = client.session
    base = client.portal_url
    resp = session.get(
        f"{base}/api/v1/project/{PROJECT_ID}/analysis/{ANALYSIS_ID}/execution",
        timeout=30)
    groups = resp.json().get("content", [])

    # 최신 상태 (researchName 필터)
    latest_all = {}
    for group in groups:
        if group.get("researchName") != TARGET_RESEARCH:
            continue
        for ex in group.get("executionList", []):
            cdm = ex.get("cdmName", "?")
            if cdm not in latest_all:
                latest_all[cdm] = ex

    print("=" * 80)
    print(f"연구: {TARGET_RESEARCH}")
    print(f"완료: {len(completed)}개 | 다운로드됨: {len(downloaded)}개")
    print("=" * 80)

    new_sites = []
    print(f"\n{'상태':<12} {'기관명':<30} {'CDM':<28} {'다운로드':<8}")
    print("-" * 80)

    for cdm in sorted(latest_all.keys()):
        ex = latest_all[cdm]
        status = ex.get("executionStatus", "?")
        org = ex.get("orgName", "?")
        is_downloaded = cdm in downloaded

        if status == "FINISHED_SUCCESSFULLY":
            tag = "COMPLETE"
            dl = "O" if is_downloaded else "NEW"
            if not is_downloaded:
                new_sites.append(cdm)
        elif status == "EXECUTING_DOCKER":
            tag = "RUNNING"
            dl = "-"
        elif status == "WAITING":
            tag = "WAITING"
            dl = "-"
        else:
            tag = "FAILED"
            dl = "-"

        print(f"{tag:<12} {org:<30} {cdm:<28} {dl:<8}")

    print(f"\n신규 다운로드 대상: {len(new_sites)}개")
    if new_sites:
        for s in new_sites:
            print(f"  - {s} ({completed[s]['orgName']})")

    return completed, downloaded, new_sites


def download_new(client, completed, already_downloaded):
    """신규 완료 기관 다운로드 & 압축 해제"""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    session = client.session
    base = client.portal_url

    new_count = 0
    for cdm, ex in sorted(completed.items()):
        if cdm in already_downloaded:
            continue

        exec_id = ex["id"]
        org_name = ex["orgName"]

        try:
            # 파일 목록
            files_resp = session.get(
                f"{base}/api/v1/project/{PROJECT_ID}/analysis/{ANALYSIS_ID}"
                f"/execution/{exec_id}/files", timeout=30)
            files_resp.raise_for_status()
            file_list = files_resp.json().get("content", [])

            target = None
            for f in file_list:
                if f.get("fileName") == "result.zip":
                    target = f
                    break
            if not target:
                print(f"  [{cdm}] result.zip 없음")
                continue

            file_id = target["id"]

            # 다운로드
            save_name = f"{cdm}_{exec_id}_result.zip"
            save_path = os.path.join(RESULTS_DIR, save_name)

            print(f"  [{cdm}] {org_name} 다운로드 중...", end="", flush=True)
            dl_url = (f"{base}/api/v1/project/{PROJECT_ID}/analysis/{ANALYSIS_ID}"
                      f"/execution/{exec_id}/files/{file_id}/download")
            dl_resp = session.get(dl_url, timeout=600, stream=True)
            dl_resp.raise_for_status()

            total = 0
            with open(save_path, "wb") as f:
                for chunk in dl_resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)

            size_mb = total / (1024 * 1024)
            print(f" {size_mb:.1f} MB", end="")

            # 압축 해제
            out_dir = os.path.join(RESULTS_DIR, cdm)
            os.makedirs(out_dir, exist_ok=True)
            with zipfile.ZipFile(save_path, "r") as z:
                z.extractall(out_dir)
            print(f" -> 압축 해제 완료")
            new_count += 1

        except Exception as e:
            print(f" FAILED: {e}")

    print(f"\n신규 다운로드: {new_count}건")
    return new_count


def extract_cmdata():
    """모든 기관의 CmData zip 압축 해제"""
    os.makedirs(CMDATA_DIR, exist_ok=True)

    sites = [d for d in os.listdir(RESULTS_DIR)
             if os.path.isdir(os.path.join(RESULTS_DIR, d, "script"))]

    new_count = 0
    for site in sorted(sites):
        cm_dir = os.path.join(RESULTS_DIR, site, "script", "extras", "result", "cmOutput")
        if not os.path.isdir(cm_dir):
            continue

        for zf in os.listdir(cm_dir):
            if not (zf.startswith("CmData") and zf.endswith(".zip")):
                continue

            base_name = zf.replace(".zip", "")
            out_dir = os.path.join(CMDATA_DIR, site, base_name)

            # 이미 있으면 스킵
            if os.path.isdir(out_dir) and any(f.endswith(".sqlite") for f in os.listdir(out_dir)):
                continue

            os.makedirs(out_dir, exist_ok=True)
            zip_path = os.path.join(cm_dir, zf)
            try:
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(out_dir)
                new_count += 1
            except Exception as e:
                print(f"  CmData 추출 실패: {site}/{zf}: {e}")

    total = len([d for d in os.listdir(CMDATA_DIR) if os.path.isdir(os.path.join(CMDATA_DIR, d))])
    print(f"CmData: {total}개 기관 ({new_count}개 신규 추출)")
    return total


def run_cyclops_analysis():
    """R Cyclops pooled analysis 실행"""
    if not os.path.isfile(R_EXE):
        print(f"R 실행 파일 없음: {R_EXE}")
        return False

    print(f"\nR Cyclops 분석 실행 중...")
    print(f"  스크립트: {R_SCRIPT}")
    print("-" * 60)

    result = subprocess.run(
        [R_EXE, R_SCRIPT],
        capture_output=False,
        text=True,
        timeout=3600,
    )

    if result.returncode == 0:
        print("\nR 분석 완료!")
        return True
    else:
        print(f"\nR 분석 실패 (exit code {result.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Pooled Analysis 업데이트")
    parser.add_argument("--check", action="store_true", help="현황만 확인")
    parser.add_argument("--download", action="store_true", help="다운로드만")
    parser.add_argument("--analyze", action="store_true", help="분석만")
    args = parser.parse_args()

    # 기본: 전체 파이프라인
    do_all = not (args.check or args.download or args.analyze)

    client = login()

    # 1. 현황 확인
    completed, downloaded, new_sites = check_status(client)

    if args.check:
        return

    # 2. 다운로드
    if do_all or args.download:
        if new_sites:
            print(f"\n{'='*80}")
            print("다운로드 시작")
            print(f"{'='*80}")
            download_new(client, completed, downloaded)
        else:
            print("\n신규 다운로드 대상 없음")

    # 3. CmData 추출
    if do_all or args.download or args.analyze:
        print(f"\n{'='*80}")
        print("CmData 추출")
        print(f"{'='*80}")
        n_sites = extract_cmdata()

    # 4. R 분석
    if do_all or args.analyze:
        print(f"\n{'='*80}")
        print(f"Cyclops Pooled Analysis ({n_sites if 'n_sites' in dir() else '?'}개 기관)")
        print(f"{'='*80}")
        run_cyclops_analysis()

        # 결과 요약
        result_path = os.path.join(BASE_DIR, "matched_results_cyclops",
                                    "ipd_pooled_cyclops_1to2_matched_results.csv")
        if os.path.isfile(result_path):
            import csv
            with open(result_path, "r", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            sig = [r for r in rows if r.get("p_value") and r["p_value"] != "NA"
                   and float(r["p_value"]) < 0.05 and r.get("hr") and r["hr"] != "NA"]
            print(f"\n총 {len(rows)}개 분석, 유의(p<0.05): {len(sig)}건")
            for r in sig:
                total_ev = int(r["events_target"]) + int(r["events_comparator"])
                reliable = "OK" if total_ev >= 20 else "LOW"
                print(f"  c{r['comparator_id']} {r['outcome_name']:<25} "
                      f"HR={r['hr']} ({r['ci_lower']}-{r['ci_upper']}) "
                      f"p={r['p_value']} events={total_ev} [{reliable}]")


if __name__ == "__main__":
    main()
