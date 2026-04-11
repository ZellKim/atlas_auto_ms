# feedernet Estimation 모니터링 - GCP Cloud Functions 배포

## 개요

```
Cloud Scheduler (매 1시간)
    ↓ HTTP trigger
Cloud Function (feedernet-monitor)
    ↓
    1. feedernet 로그인
    2. Analysis 10957 (v7b), 10961 (biomarker) 상태 조회
    3. Telegram 알림 전송
    4. 전체 완료 시 "ALL COMPLETE" 알림
```

## 비용: $0/월 (무료 티어 내)

---

## 배포 순서

### 변수 설정

```bash
PROJECT_ID="investment-os-chain"
REGION="us-east1"
SA="chain-collector@${PROJECT_ID}.iam.gserviceaccount.com"
```

### Step 1: Secrets 등록 (feedernet 인증 - 1회만)

```bash
echo -n "20230172@khnmc.or.kr" | gcloud secrets create FEEDERNET_EMAIL --data-file=- --replication-policy=automatic
echo -n "비밀번호" | gcloud secrets create FEEDERNET_PASSWORD --data-file=- --replication-policy=automatic

# 서비스 계정 접근 권한
for SECRET in FEEDERNET_EMAIL FEEDERNET_PASSWORD; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
done
```

> TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID는 이미 등록됨 (daily-run에서 사용 중)

### Step 2: Cloud Function 배포

```bash
cd cloud_monitor

gcloud functions deploy feedernet-monitor \
  --gen2 \
  --region=$REGION \
  --runtime=python312 \
  --entry-point=monitor \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account=$SA \
  --memory=256Mi \
  --timeout=60s \
  --set-env-vars="GCS_BUCKET=investment-os-regiem-state" \
  --set-secrets="FEEDERNET_EMAIL=FEEDERNET_EMAIL:latest,FEEDERNET_PASSWORD=FEEDERNET_PASSWORD:latest,TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_CHAT_ID=TELEGRAM_CHAT_ID:latest"
```

### Step 3: Cloud Scheduler 설정 (1시간마다)

```bash
# Function URL 확인
FUNCTION_URL=$(gcloud functions describe feedernet-monitor --region=$REGION --gen2 --format='value(serviceConfig.uri)')

gcloud scheduler jobs create http feedernet-monitor-trigger \
  --location=$REGION \
  --schedule="0 * * * *" \
  --time-zone="Asia/Seoul" \
  --uri="${FUNCTION_URL}" \
  --http-method=POST \
  --oidc-service-account-email=$SA
```

### Step 4: 수동 테스트

```bash
# 즉시 실행
gcloud scheduler jobs run feedernet-monitor-trigger --location=$REGION

# 로그 확인
gcloud functions logs read feedernet-monitor --region=$REGION --gen2 --limit=20
```

---

## 완료 후 정리

모든 estimation이 완료되면 스케줄러를 중지:

```bash
gcloud scheduler jobs pause feedernet-monitor-trigger --location=$REGION
```

다시 필요할 때:

```bash
gcloud scheduler jobs resume feedernet-monitor-trigger --location=$REGION
```

완전 삭제:

```bash
gcloud scheduler jobs delete feedernet-monitor-trigger --location=$REGION
gcloud functions delete feedernet-monitor --region=$REGION --gen2
```

---

## 모니터링 대상 변경

`main.py`의 `MONITOR_TARGETS` dict를 수정 후 재배포:

```bash
gcloud functions deploy feedernet-monitor ... (위와 동일)
```
