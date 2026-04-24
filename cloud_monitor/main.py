"""feedernet Estimation 모니터링 Cloud Function.

Cloud Scheduler (매 1시간) → Cloud Function → 상태 체크
- 완료 기관이 늘어나면 Telegram 알림
- 전체 완료 시 최종 알림
- 변화 없으면 알림 안 함

이전 상태는 GCS에 JSON으로 저장 (stateless function 간 상태 유지).
"""

import os
import json
import logging
import requests
import functions_framework

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("feedernet_monitor")

# ── 설정 ──────────────────────────────────────────────
PORTAL_URL = "https://www.feedernet.com"
FEEDERNET_EMAIL = os.environ.get("FEEDERNET_EMAIL")
FEEDERNET_PASSWORD = os.environ.get("FEEDERNET_PASSWORD")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "investment-os-regiem-state")
STATE_BLOB = "monitor/feedernet_monitor_state.json"

# 모니터링 대상
# - v3 analyses 11018/11019 removed 2026-04-19 (completed/cancelled)
# - v4 appendectomy 11034-11038, 11044 removed 2026-04-24 (completed)
MONITOR_TARGETS = {
    # allergic diseases (22 sites, v2 spec with NC 54) — added 2026-04-24
    11029: {"name": "AD_allergic_tic_adhd_v1 (22 sites)", "project_id": 5104},
}


# ── GCS 상태 저장/로드 ────────────────────────────────

def load_previous_state() -> dict:
    """GCS에서 이전 완료 수 로드. 없으면 빈 dict."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(STATE_BLOB)
        if blob.exists():
            return json.loads(blob.download_as_text())
    except Exception as e:
        logger.warning(f"Failed to load previous state: {e}")
    return {}


def save_current_state(state: dict):
    """현재 완료 수를 GCS에 저장."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(STATE_BLOB)
        blob.upload_from_string(json.dumps(state), content_type="application/json")
        logger.info("State saved to GCS")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


# ── feedernet API ─────────────────────────────────────

def login_feedernet(session: requests.Session) -> bool:
    resp = session.post(
        f"{PORTAL_URL}/api/v1/auth/login",
        json={"email": FEEDERNET_EMAIL, "password": FEEDERNET_PASSWORD},
        timeout=30,
    )
    if resp.status_code == 200 and resp.json().get("result"):
        logger.info("feedernet login OK")
        return True
    logger.error(f"feedernet login failed: {resp.text[:200]}")
    return False


def get_execution_status(session: requests.Session, project_id: int, analysis_id: int) -> dict:
    """기관별 최신 실행 상태 요약 반환."""
    resp = session.get(
        f"{PORTAL_URL}/api/v1/project/{project_id}/analysis/{analysis_id}/execution",
        timeout=30,
    )
    resp.raise_for_status()
    groups = resp.json().get("content", [])

    # Pick LATEST execution per cdmId by max eid (not first-match which is non-deterministic)
    latest_by_cdm = {}
    for group in groups:
        for ex in group.get("executionList", []):
            cdm_id = ex.get("cdmId")
            if cdm_id is None:
                continue
            prev = latest_by_cdm.get(cdm_id)
            if prev is None or (ex.get("id", 0) or 0) > (prev.get("id", 0) or 0):
                latest_by_cdm[cdm_id] = ex

    counts = {"COMPLETE": 0, "RUNNING": 0, "FAILED": 0, "WAITING": 0, "CANCELED": 0}
    details = {"COMPLETE": [], "RUNNING": [], "FAILED": [], "WAITING": [], "CANCELED": []}

    for ex in latest_by_cdm.values():
        status = ex.get("executionStatus", "")
        org = ex.get("orgName", "?")

        if status == "FINISHED_SUCCESSFULLY":
            tag = "COMPLETE"
        elif status == "EXECUTING_DOCKER":
            tag = "RUNNING"
        elif status == "WAITING":
            tag = "WAITING"
        elif status == "CANCELED":
            tag = "CANCELED"
        else:
            tag = "FAILED"

        counts[tag] += 1
        details[tag].append(org)

    total = sum(counts.values())
    all_done = total > 0 and counts["RUNNING"] == 0 and counts["WAITING"] == 0

    return {
        "total": total,
        "counts": counts,
        "details": details,
        "all_done": all_done,
    }


# ── Telegram ──────────────────────────────────────────

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }, timeout=15)
    if resp.status_code != 200:
        logger.error(f"Telegram send failed: {resp.text[:200]}")
    else:
        logger.info("Telegram message sent")


# ── Cloud Function entrypoint ─────────────────────────

@functions_framework.http
def monitor(request):
    """Cloud Scheduler에서 HTTP로 호출."""
    print(f"[MONITOR] invoked; targets={list(MONITOR_TARGETS.keys())}")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "FedernetMonitor/1.0",
        "Accept": "application/json",
    })

    if not login_feedernet(session):
        send_telegram("feedernet 모니터링 로그인 실패")
        return ("login failed", 500)
    print("[MONITOR] login OK")

    prev_state = load_previous_state()
    # _retired = analyses that completed and were auto-removed from monitoring
    retired = set(prev_state.get("_retired", []))
    current_state = {}
    messages = []
    should_notify = False
    newly_retired = []

    for analysis_id, target in MONITOR_TARGETS.items():
        key = str(analysis_id)
        if key in retired:
            print(f"[MONITOR] skip {key} (retired)")
            continue
        project_id = target["project_id"]
        name = target["name"]

        try:
            status = get_execution_status(session, project_id, analysis_id)
        except Exception as e:
            logger.error(f"{name}: 조회 실패 - {e}")
            continue

        c = status["counts"]
        total = status["total"]
        prev_complete = prev_state.get(key, {}).get("complete", 0)
        new_complete = c["COMPLETE"] - prev_complete

        current_state[key] = {"complete": c["COMPLETE"], "total": total}

        if new_complete > 0:
            should_notify = True

        line = (
            f"<b>{name}</b>\n"
            f"  총 {total}개 기관\n"
            f"  COMPLETE: {c['COMPLETE']}  |  RUNNING: {c['RUNNING']}  |  "
            f"FAILED: {c['FAILED']}  |  WAITING: {c['WAITING']}"
        )

        if new_complete > 0:
            new_orgs = status["details"]["COMPLETE"][-new_complete:]
            line += f"\n  +{new_complete} 새 완료: {', '.join(new_orgs)}"
        if c["RUNNING"] > 0:
            line += f"\n  실행중: {', '.join(status['details']['RUNNING'])}"
        if c["FAILED"] > 0:
            line += f"\n  실패: {', '.join(status['details']['FAILED'])}"

        # Auto-retire when all done
        if status["all_done"]:
            line += "\n  ✅ ALL DONE — 이후 모니터링 중단"
            retired.add(key)
            newly_retired.append(name)
            should_notify = True

        messages.append(line)

    current_state["_retired"] = sorted(retired)
    save_current_state(current_state)

    all_studies_done = len(messages) == 0  # all targets retired → nothing to monitor

    # 알림 판단: 완료 수 증가 or 전체 완료
    print(f"[MONITOR] should_notify={should_notify} all_done={all_studies_done} n_msgs={len(messages)}")
    if all_studies_done:
        msg = f"<b>ALL COMPLETE - feedernet Estimation 전체 완료</b>\n\n" + "\n\n".join(messages)
        send_telegram(msg)
        print("[MONITOR] ALL DONE Telegram sent")
    elif should_notify:
        msg = f"<b>feedernet Estimation 진행 업데이트</b>\n\n" + "\n\n".join(messages)
        send_telegram(msg)
        print("[MONITOR] UPDATE Telegram sent")
    else:
        print("[MONITOR] no change - skip Telegram")

    return ("ok", 200)
