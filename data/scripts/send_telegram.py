"""
Send a Telegram message via the GCP-stored bot token.
Usage: python send_telegram.py "message text"
"""
import sys, subprocess, requests

def get_secret(name):
    # Windows gcloud is a .cmd shim; use shell=True so PATH resolves it
    r = subprocess.run(f'gcloud secrets versions access latest --secret={name}',
                       capture_output=True, text=True, check=True, shell=True)
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
