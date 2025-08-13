# services/aligo_service.py
from infra.aligo_client import send_one, send_batch, is_success
from config import Config

# 승인된 본문을 "그대로" 넣으세요. (아래는 예시 — 콘솔 승인본을 그대로 복붙!)
TEMPLATE_MESSAGE = (
    "프리미즈입니다.\n"
    "주문해 주셔서 감사합니다.\n"
    "등록절차 안내 드리겠습니다.\n"
    "\n"
    "●등록 안내●\n"
    "1. 유튜브 프리미엄 등록 신청 링크에서 신청서 작성\n"
    "2. 영업시간 내 (10:00~21:00) 적용 처리됩니다.\n"
    "3. 적용 완료 후 계정 정보를 변경하셔도 됩니다.\n"
    "\n"
    "▼▼유튜브 프리미엄 등록 신청▼▼\n"
    "https://forms.gle/5Jhy6uZ78KJiM4tX8\n"
    "\n"
    "▼▼비밀번호 변경 방법▼▼\n"
    "https://myaccount.google.com/signinoptions/password\n"
    "\n"
    "※ 백업코드를 반드시 설정 해주세요\n"
    "※ 신청 후 접수 완료 버튼을 눌러주세요"
)

TEMPLATE_SUBJECT = Config.ALIGO_SUBJECT or "프리미즈 개인유튜브 발송알림톡"

class AligoService:
    def send_message(self, payload: dict) -> dict:
        to   = payload.get("mobile") or payload.get("to")
        link = payload.get("note1")  or payload.get("link") or ""  # 버튼 링크로만 사용
        msg  = TEMPLATE_MESSAGE
        res  = send_one(to=to, subject=TEMPLATE_SUBJECT, message=msg, link_url=link)
        return {"status": "1" if is_success(res) else "0", "raw": res}

    def send_messages(self, items: list[dict]) -> list[dict]:
        batch = []
        for it in items:
            to   = it.get("mobile") or it.get("to")
            link = it.get("note1")  or it.get("link") or ""
            msg  = TEMPLATE_MESSAGE
            batch.append({"to": to, "subject": TEMPLATE_SUBJECT, "message": msg, "link": link})
        res_list = send_batch(batch)
        return [{"status": "1" if is_success(r) else "0", "raw": r} for r in res_list]
