from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
TOKEN="/home/prewoos2018/premise/secrets/gmail_token.json"
PROJECT_ID="lexical-period-458507-k9"
TOPIC=f"projects/{PROJECT_ID}/topics/gmail-orders"
svc = build("gmail","v1",credentials=Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/gmail.readonly"]), cache_discovery=False)
print(svc.users().watch(userId="me", body={"topicName": TOPIC, "labelIds":["INBOX"]}).execute())
