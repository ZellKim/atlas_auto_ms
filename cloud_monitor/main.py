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
# - allergic v2 11029 removed 2026-04-26 (cancelled, replaced by v7)
MONITOR_TARGETS = {
    # allergic v7 (PID 5125) — 23 sites, v6 메서드 + stopOnError=false
    11069: {"name": "allergic v7 (23 sites)", "project_id": 5125},
    # appendectomy v4.2 (PID 5126, artifact name appendectomy_v8) — 6 estimation × 22 sites
    # L3 site-aware default: restrictToCommonPeriod=false + CharlsonIndex=true + VisitCountLongTerm=true
    11070: {"name": "appendectomy v4.2 cbc_wbc",      "project_id": 5126},
    11071: {"name": "appendectomy v4.2 cbc_rbc",      "project_id": 5126},
    11072: {"name": "appendectomy v4.2 chem_hepa",    "project_id": 5126},
    11073: {"name": "appendectomy v4.2 meta_endo",    "project_id": 5126},
    11074: {"name": "appendectomy v4.2 sex_specific", "project_id": 5126},
    11075: {"name": "appendectomy v4.2 clinical",     "project_id": 5126},
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
    """기관별 최신 실행 상태 요약 반환.

    Per-cdm aggregation: cdm 하나에 exec 여러 개 있어도(bulk+sequential 중복 등)
    "any FS exists" 우선, 그 다음 active → cancel → fail 순으로 categorize.
    이렇게 해야 중복 cancel 후에도 진짜 결과 카운트가 맞음.
    """
    resp = session.get(
        f"{PORTAL_URL}/api/v1/project/{project_id}/analysis/{analysis_id}/execution",
        timeout=30,
    )
    resp.raise_for_status()
    groups = resp.json().get("content", [])

    # Per-cdm: collect ALL exec states + remember orgName
    by_cdm = {}
    for group in groups:
        for ex in group.get("executionList", []):
            cdm_id = ex.get("cdmId")
            if cdm_id is None:
                continue
            d = by_cdm.setdefault(cdm_id, {"states": [], "org": ex.get("orgName", "?")})
            d["states"].append(ex.get("executionStatus", ""))

    counts = {"COMPLETE": 0, "RUNNING": 0, "FAILED": 0, "WAITING": 0, "CANCELED": 0}
    details = {"COMPLETE": [], "RUNNING": [], "FAILED": [], "WAITING": [], "CANCELED": []}

    for d in by_cdm.values():
        ss = d["states"]
        org = d["org"]

        if "FINISHED_SUCCESSFULLY" in ss:
            tag = "COMPLETE"
        elif any(s == "EXECUTING_DOCKER" or s == "EXECUTING_PREPARING" or s == "SAVING_RESULT_FILES" for s in ss):
            tag = "RUNNING"
        elif any(s == "WAITING" for s in ss):
            tag = "WAITING"
        elif any(s == "FINISHED_WITH_ERROR" for s in ss):
            tag = "FAILED"
        elif all(s == "CANCELED" for s in ss):
            tag = "CANCELED"
        else:
            tag = "FAILED"  # unknown state — flag as fail

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
            f"WAITING: {c['WAITING']}  |  FAILED: {c['FAILED']}  |  CANCELED: {c['CANCELED']}"
        )

        if new_complete > 0:
            new_orgs = status["details"]["COMPLETE"][-new_complete:]
            line += f"\n  +{new_complete} 새 완료: {', '.join(new_orgs)}"
        if c["RUNNING"] > 0:
            line += f"\n  실행중: {', '.join(status['details']['RUNNING'])}"
        if c["FAILED"] > 0:
            line += f"\n  실패: {', '.join(status['details']['FAILED'])}"

        # Auto-retire when settled (더 이상 RUNNING/WAITING 없음).
        # FAILED 가 있으면 성공으로 오인시키지 않도록 메시지를 명확히 구분.
        # (재시도는 cloud_monitor 범위 밖 — v4_phase_e_monitor.py 가 담당)
        if status["all_done"]:
            if c["FAILED"] > 0:
                line += (f"\n  ⚠️ 종료 — 단 FAILED {c['FAILED']}개 (조치 필요): "
                         f"{', '.join(status['details']['FAILED'])} — 모니터링 중단")
            else:
                line += "\n  ✅ ALL DONE — 이후 모니터링 중단"
            retired.add(key)
            newly_retired.append(name)
            should_notify = True

        messages.append(line)

    current_state["_retired"] = sorted(retired)

    all_studies_done = len(messages) == 0  # all targets retired → nothing to monitor

    # 중복 ALL DONE 방지: prev_state에 _all_done_sent flag 저장
    # MONITOR_TARGETS의 keys 집합으로 hash 비교 → targets 변경 시 flag reset
    targets_sig = ",".join(map(str, sorted(MONITOR_TARGETS.keys())))
    prev_targets_sig = prev_state.get("_targets_sig", "")
    prev_all_done_sent = prev_state.get("_all_done_sent", False)
    targets_changed = targets_sig != prev_targets_sig

    # State 저장
    current_state["_targets_sig"] = targets_sig
    current_state["_all_done_sent"] = prev_all_done_sent  # 기본 유지

    # 알림 판단: 완료 수 증가 or 전체 완료(once)
    print(f"[MONITOR] should_notify={should_notify} all_done={all_studies_done} "
          f"n_msgs={len(messages)} prev_all_done_sent={prev_all_done_sent} targets_changed={targets_changed}")

    if all_studies_done:
        if not prev_all_done_sent or targets_changed:
            msg = f"<b>ALL COMPLETE - feedernet Estimation 전체 완료</b>\n\n" + "\n\n".join(messages)
            send_telegram(msg)
            print("[MONITOR] ALL DONE Telegram sent (first time after retire)")
            current_state["_all_done_sent"] = True
        else:
            print("[MONITOR] all_done already notified — skip")
    elif should_notify:
        msg = f"<b>feedernet Estimation 진행 업데이트</b>\n\n" + "\n\n".join(messages)
        send_telegram(msg)
        print("[MONITOR] UPDATE Telegram sent")
        current_state["_all_done_sent"] = False  # 활성 진행 있음 → flag reset
    else:
        print("[MONITOR] no change - skip Telegram")
        current_state["_all_done_sent"] = False  # 활성 있음(메시지 있음) → flag reset

    save_current_state(current_state)
    return ("ok", 200)
