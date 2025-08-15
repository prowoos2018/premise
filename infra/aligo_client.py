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

def _build_button_json_from_url(link_url: str) -> str:
    """WL 버튼 1개를 URL로부터 생성 (문자열 JSON 반환)."""
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

def send_one(to: str, subject: str, message: str, link_url: str = "", button_json: str = "") -> dict:
    data = {
        "apikey":     Config.ALIGO_API_KEY,
        "userid":     Config.ALIGO_USER_ID,
        "senderkey":  Config.ALIGO_SENDERKEY,
        "tpl_code":   Config.ALIGO_TPL_CODE,
        "sender":     Config.ALIGO_SENDER,
        "receiver_1": "".join(ch for ch in str(to) if ch.isdigit()),  # 숫자만
        "subject_1":  subject or "",
        "message_1":  message,
    }
    if Config.ALIGO_EMTITLE:
        data["emtitle_1"] = Config.ALIGO_EMTITLE  # 강조표기형일 때만

    # 버튼 문자열 JSON 준비
    btn = button_json or _build_button_json_from_url(link_url)  # 반드시 문자열 반환
    if btn:
        # 호환성: 두 키 모두 전송
        data["button_1"]  = btn
        # data["button_01"] = btn

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
            button_json=it.get("button_json",""),
            link_url=it.get("link",""),
        )
        results.append(r)
    return results

def is_success(result: dict) -> bool:
    # code 값 안전하게 추출 (0도 유효해야 함)
    code_val = result.get("result_code")
    if code_val is None:
        code_val = result.get("code")
    if code_val is None:
        code_val = result.get("result")

    try:
        code_int = int(code_val)
    except Exception:
        code_int = 1  # 알 수 없으면 실패 취급

    msg = str(result.get("message") or "").strip()

    # 🔹 디버그 로그 추가 — 여기서 찍으면 됨
    current_app.logger.debug(
        "[ALIGO is_success] raw_code=%r, parsed=%s, msg=%r",
        code_val, code_int, msg
    )

    # 알리고: code == 0 이면 "성공적으로 전송요청 하였습니다." = 정상 접수
    return (code_int == 0) and ("성공적으로 전송요청" in msg)




