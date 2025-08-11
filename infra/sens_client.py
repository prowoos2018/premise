import time, hmac, hashlib, base64, requests
from config import Config

def make_signature(method: str, uri: str, timestamp: str):
    msg = f"{method} {uri}\n{timestamp}\n{Config.SENS_ACCESS_KEY}"
    return base64.b64encode(
        hmac.new(Config.SENS_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()

def send_alimtalk_batch(batch):
    uri = f"/alimtalk/v2/services/{Config.SENS_SERVICE_ID}/messages"
    url = f"https://sens.apigw.ntruss.com{uri}"
    ts  = str(int(time.time() * 1000))
    sig = make_signature("POST", uri, ts)

    body = {
        "plusFriendId": Config.PLUS_FRIEND_ID,
        "templateCode": Config.TEMPLATE_CODE,
        "messages": [
            {
                "to": item["to"],
                "kakaoTemplateVars": item["vars"],
                "smsSenderNo": Config.SENDER_NO,
                "smsContent": f"[대체] {item['vars']['LINK']}"
            } for item in batch
        ]
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "x-ncp-iam-access-key": Config.SENS_ACCESS_KEY,
        "x-ncp-apigw-timestamp": ts,
        "x-ncp-apigw-signature-v2": sig
    }
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()
