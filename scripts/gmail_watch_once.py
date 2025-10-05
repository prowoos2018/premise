from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN="/home/prewoos2018/premise/secrets/gmail_token.json"

# Pub/Sub이 있는 프로젝트 ID (토픽 만든 곳!)
PROJECT_ID="lexical-period-458507-k9"
TOPIC=f"projects/{PROJECT_ID}/topics/gmail-orders"

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/gmail.readonly"])
svc = build("gmail","v1",credentials=creds, cache_discovery=False)

# INBOX만 감시 (원하면 labelIds 제거 가능)
resp = svc.users().watch(userId="me", body={"topicName": TOPIC, "labelIds": ["INBOX"]}).execute()
print(resp)
