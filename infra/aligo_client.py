# infra/aligo_client.py
import requests
import json
import time, random
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
            # 알리고 응답은 200이라도 result_code가 실패일 수 있음
            if resp.status_code >= 500 and attempt < max_attempts:
                current_app.logger.warning("[%s] HTTP %s, retry...", label, resp.status_code)
                _sleep_backoff(attempt)
                continue
            return resp
        except requests.RequestException as e:
            current_app.logger.exception("[%s] request error (attempt=%d)", label, attempt)
            if attempt < max_attempts:
                _sleep_backoff(attempt)
                continue
            raise

def _build_button_json(link_url: str) -> str:
    """
    WL(웹링크) 버튼 1개 구성. PC/Mobile 둘 다 같은 링크로 설정.
    """
    if not link_url:
        return ""
    button = {
        "button": [{
            "name": Config.ALIGO_BUTTON_NAME or "바로가기",
            "linkType": "WL",
            "linkTypeName": "웹링크",
            "linkM": link_url,
            "linkP": link_url,
        }]
    }
    return json.dumps(button, ensure_ascii=False)

def send_one(to: str, subject: str, message: str, link_url: str = "") -> dict:
    """
    알리고 단건 발송. message는 템플릿과 줄바꿈까지 동일해야 함(치환 후 문자열).
    """
    data = {
        "apikey":    Config.ALIGO_API_KEY,
        "userid":    Config.ALIGO_USER_ID,
        "senderkey": Config.ALIGO_SENDERKEY,
        "tpl_code":  Config.ALIGO_TPL_CODE,
        "sender":    Config.ALIGO_SENDER,
        "receiver_1": to,
        "subject_1": subject or "",
        "message_1": message,
    }
    btn = _build_button_json(link_url)
    if btn:
        data["button_1"] = btn

    current_app.logger.debug("[ALIGO] payload=%s", {k: (v if k!="button_1" else "[json]") for k,v in data.items()})

    resp = _post_with_retry(data, "alimtalk/send")
    try:
        result = resp.json()
    except Exception:
        result = {"http_status": resp.status_code, "text": resp.text}

    current_app.logger.debug("[ALIGO] result=%s", result)
    return result

def send_batch(items: List[Dict]) -> List[dict]:
    """
    여러 건을 순차 발송. 알리고 단건 API를 n번 호출(간단/안전).
    items: [{ "to": "010...", "subject": "...", "message": "...", "link": "https://..." }, ...]
    """
    results = []
    for i, it in enumerate(items, start=1):
        r = send_one(
            to=it.get("to",""),
            subject=it.get("subject",""),
            message=it.get("message",""),
            link_url=it.get("link",""),
        )
        results.append(r)
    return results

def is_success(result: dict) -> bool:
    """
    알리고 성공 판단. 공식 응답은 보통 {"result_code":"1", ...} 형태.
    예외적으로 다른 키가 올 수 있어 방어적으로 처리.
    """
    code = str(result.get("result_code") or result.get("code") or result.get("result") or "")
    return code == "1"
