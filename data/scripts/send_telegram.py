"""
Send a Telegram message via the GCP-stored bot token.
Usage: python send_telegram.py "message text"
"""
import os, sys, subprocess, requests

_GCLOUD_CANDIDATES = [
    "gcloud",  # if on PATH
    r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
    r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"),
]

def _resolve_gcloud():
    override = os.environ.get("GCLOUD_PATH")
    if override and os.path.exists(override):
        return override
    for cand in _GCLOUD_CANDIDATES:
        if cand == "gcloud":
            try:
                r = subprocess.run([cand, "--version"], capture_output=True, text=True, shell=True, timeout=10)
                if r.returncode == 0:
                    return cand
            except Exception:
                continue
        elif os.path.exists(cand):
            return cand
    raise RuntimeError("gcloud not found on PATH or known install paths; set GCLOUD_PATH env var")

_GCLOUD = None

def get_secret(name):
    global _GCLOUD
    if _GCLOUD is None:
        _GCLOUD = _resolve_gcloud()
    cmd = f'"{_GCLOUD}" secrets versions access latest --secret={name}' if _GCLOUD != "gcloud" else f'gcloud secrets versions access latest --secret={name}'
    r = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)
    return r.stdout.strip()

def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else 'Test message'
    token = get_secret('TELEGRAM_BOT_TOKEN')
    chat  = get_secret('TELEGRAM_CHAT_ID')
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    r = requests.post(url, json={'chat_id': chat, 'text': msg, 'parse_mode': 'HTML'}, timeout=15)
    print(f'status={r.status_code}')
    if r.status_code != 200:
        print(r.text[:500])
        sys.exit(1)
    print('Telegram sent OK')

if __name__ == '__main__':
    main()
