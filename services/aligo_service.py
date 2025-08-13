# services/aligo_service.py
from infra.aligo_client import send_one, send_batch, is_success
from config import Config

# 템플릿 치환: #{LINK} 변수를 실제 링크로 바꾼다고 가정
# 승인된 템플릿 본문을 그대로 적고, 변수 위치는 {LINK} 로 포맷팅되게 둡니다.
# 예: "안녕하세요.\n이용 링크: {LINK}\n감사합니다."
TEMPLATE_MESSAGE = "안녕하세요.\n이용 링크: {LINK}\n감사합니다."

TEMPLATE_SUBJECT = "알림"  # 수신자에겐 보이지 않지만 필수 필드 요구시 채움

class AligoService:
    """
    기존 DirectSendService 대체용으로, 같은 느낌의 인터페이스 제공
    """
    def send_message(self, payload: dict) -> dict:
        """
        payload 예: {"mobile": "010...", "note1": "https://..."}
        - DirectSend의 note1을 LINK 변수로 매핑
        """
        to    = payload.get("mobile") or payload.get("to")
        link  = payload.get("note1") or payload.get("link") or ""
        msg   = TEMPLATE_MESSAGE.format(LINK=link)
        res   = send_one(to=to, subject=TEMPLATE_SUBJECT, message=msg, link_url=link)
        # 통일된 형태로 리턴: {"status": "1"|"0", "raw": res}
        return {"status": "1" if is_success(res) else "0", "raw": res}

    def send_messages(self, items: list[dict]) -> list[dict]:
        """
        items 예: [{"mobile":"010...", "note1":"https://..."}, ...]
        """
        batch = []
        for it in items:
            to   = it.get("mobile") or it.get("to")
            link = it.get("note1")  or it.get("link") or ""
            msg  = TEMPLATE_MESSAGE.format(LINK=link)
            batch.append({"to": to, "subject": TEMPLATE_SUBJECT, "message": msg, "link": link})
        res_list = send_batch(batch)
        return [{"status": "1" if is_success(r) else "0", "raw": r} for r in res_list]
