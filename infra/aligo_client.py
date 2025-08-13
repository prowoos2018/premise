# infra/aligo_client.py
import requests, json, time, random
from typing import List, Dict
from config import Config
from flask import current_app

BASIC_SEND_URL = "https://kakaoapi.aligo.in/akv10/alimtalk/send/"
RETRY_STATUS = {429, 500, 502, 503, 504}

def _sleep_backoff(attempt: int, base: float = 0.6):
    time.sleep(base * (2 ** (attempt - 1)) + random.uniform(0, 0.3))

def _post_with_retry(data: dict, label: str, max_attempts: int = 5):
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.post(BASIC_SEND_URL, data=data, timeout=15)
            if resp.status_code >= 500 and attempt < max_attempts:
                current_app.logger.warning("[%s] HTTP %s, retry...", label, resp.status_code)
                _sleep_backoff(attempt)
                continue
            return resp
        except requests.RequestException:
            current_app.logger.exception("[%s] request error (attempt=%d)", label, attempt)
            if attempt < max_attempts:
                _sleep_backoff(attempt)
                continue
            raise

def _build_button_json(link_url: str) -> str:
    """
    WL(웹링크) 버튼 1개. 알리고 스펙: linkMo / linkPc
    """
    if not link_url:
        return ""
    button = {
        "button": [{
            "name": Config.ALIGO_BUTTON_NAME or "신청서 작성",
            "linkType": "WL",
            "linkTypeName": "웹링크",
            "linkMo": link_url,
            "linkPc": link_url,
        }]
    }
    return json.dumps(button, ensure_ascii=False)

def send_one(to: str, subject: str, message: str, link_url: str = "") -> dict:
    data = {
        "apikey":     Config.ALIGO_API_KEY,
        "userid":     Config.ALIGO_USER_ID,
        "senderkey":  Config.ALIGO_SENDERKEY,
        "tpl_code":   Config.ALIGO_TPL_CODE,
        "sender":     Config.ALIGO_SENDER,
        "receiver_1": to,
        "subject_1":  subject or "",             # 템플릿과 동일 권장
        "message_1":  message,                   # 본문 100% 동일
    }
    # 강조표기형 템플릿이면 필수
    if Config.ALIGO_EMTITLE:
        data["emtitle_1"] = Config.ALIGO_EMTITLE

    btn = _build_button_json(link_url)
    if btn:
        data["button_1"] = btn  # 문자열(JSON)이어야 함

    current_app.logger.debug("[ALIGO] payload(keys)=%s", list(data.keys()))
    resp = _post_with_retry(data, "alimtalk/send")
    try:
        result = resp.json()
    except Exception:
        result = {"http_status": resp.status_code, "text": resp.text}
    current_app.logger.debug("[ALIGO] result=%s", result)
    return result

def send_batch(items: List[Dict]) -> List[dict]:
    results = []
    for it in items:
        r = send_one(
            to=it.get("to",""),
            subject=it.get("subject",""),
            message=it.get("message",""),
            link_url=it.get("link",""),
        )
        results.append(r)
    return results

def is_success(result: dict) -> bool:
    code = str(result.get("result_code") or result.get("code") or result.get("result") or "")
    return code == "1"
