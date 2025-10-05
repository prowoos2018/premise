import os, re, time, requests
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.cloud import pubsub_v1

# Gmail 토큰
GMAIL_TOKEN="/home/prewoos2018/premise/secrets/gmail_token.json"

# Pub/Sub 구독 (lexical 프로젝트)
PROJECT_ID="lexical-period-458507-k9"
SUBSCRIPTION=f"projects/{PROJECT_ID}/subscriptions/gmail-orders-sub"

# state 저장 (히스토리 기준선)
STATE_DIR="/home/prewoos2018/premise/runtime"
LAST_HID=f"{STATE_DIR}/gmail_history_id.txt"

# 매칭되면 호출할 내부 엔드포인트
ORDER_SYNC_URL="http://127.0.0.1/internal/orders-sync?sync_token=d2c0c892-68c3-4726-8553-ebba2c2ae928"

# 제목 패턴
SUBJECT_RE = re.compile(r"(?:\[[^\]]+\]\s*)*.*주문.*결제.*완료\s*되었", re.I)

def gmail():
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, ["https://www.googleapis.com/auth/gmail.readonly"])
    return build("gmail","v1",credentials=creds, cache_discovery=False)

def get_last_hid():
    try:
        return Path(LAST_HID).read_text().strip()
    except FileNotFoundError:
        return None

def set_last_hid(hid:str):
    Path(STATE_DIR).mkdir(parents=True, exist_ok=True)
    Path(LAST_HID).write_text(str(hid))

def list_new_message_ids(start_history_id:str|None):
    g = gmail()
    user="me"
    if not start_history_id:
        # 최초 실행: 현재 시점을 기준선으로만 저장(과거 메일 중복 처리 방지)
        prof = g.users().getProfile(userId=user).execute()
        set_last_hid(prof.get("historyId"))
        return []
    msgs=[]
    token=None
    while True:
        res = g.users().history().list(
            userId=user,
            startHistoryId=start_history_id,
            historyTypes=["messageAdded"],
            pageToken=token
        ).execute()
        for h in res.get("history",[]):
            for m in h.get("messagesAdded",[]):
                msgs.append(m["message"]["id"])
        token=res.get("nextPageToken")
        if not token:
            if "historyId" in res:
                set_last_hid(res["historyId"])
            break
    return msgs

def get_subject(mid:str)->str:
    g=gmail()
    m=g.users().messages().get(userId="me", id=mid, format="metadata",
                               metadataHeaders=["Subject"]).execute()
    headers={h["name"]:h["value"] for h in m.get("payload",{}).get("headers",[])}
    return headers.get("Subject","")

def maybe_trigger(mid:str, retries=3, backoff=2):
    subj=get_subject(mid)
    if SUBJECT_RE.search(subj):
        try:
            r=requests.get(ORDER_SYNC_URL, timeout=20)
            print(f"[SYNC] {mid} {r.status_code} {subj}", flush=True)
        except Exception as e:
            print(f"[SYNC ERR] {mid} {e}", flush=True)
    else:
        print(f"[SKIP] {mid} {subj}", flush=True)

def main():
    # Pub/Sub는 ADC(애플리케이션 기본자격) 사용
    subscriber=pubsub_v1.SubscriberClient()
    sub_path=SUBSCRIPTION
    print("[START] pull loop:", sub_path, flush=True)

    # 기준선 1회 초기화
    _ = list_new_message_ids(get_last_hid())

    with subscriber:
        while True:
            resp=subscriber.pull(subscription=sub_path, max_messages=10, timeout=30)
            if resp.received_messages:
                mids=list_new_message_ids(get_last_hid())
                for mid in mids:
                    maybe_trigger(mid)
                subscriber.acknowledge(subscription=sub_path,
                                       ack_ids=[m.ack_id for m in resp.received_messages])
            else:
                time.sleep(2)

if __name__=="__main__":
    main()
