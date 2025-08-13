# routes/alerts.py

from flask import Blueprint, render_template_string,request, jsonify,current_app
from services.sheet_service import SheetService
from services.directsend_service import DirectSendService
import os

alerts_bp = Blueprint("alerts", __name__)

@alerts_bp.route("/send-invite")
def send_invite():
    sheet_svc = SheetService()
    ds_svc    = DirectSendService()

    # 1) 시트 전체 읽기
    rows = sheet_svc.fetch_all(tab="통합시트")
    if not rows:
        return "<p>통합시트에 데이터가 없습니다.</p>"

    # 2) 이미 발송된(=C열 o) 주문번호 집합
    sent_order_nos = {
        (row[3] if len(row) > 3 else "").strip()
        for row in rows
        if len(row) > 2 and row[2].strip().lower() == "o"
    }

    updates = []
    sent_count = 0

    # 3) 한 행씩 순회하며 발송
    for idx, row in enumerate(rows, start=2):
        # C열: 발송여부
        flag = (row[2] if len(row) > 2 else "").strip().lower()
        if flag == "o":
            continue

        # D열: 주문번호
        order_no = (row[3] if len(row) > 3 else "").strip()
        if order_no in sent_order_nos:
            # 이미 발송된 주문번호면 skip
            current_app.logger.debug(f"{idx}행 주문번호 {order_no} → 이미 발송됨, 건너뜀")
            continue

        # E열: 주문상태
        status = (row[4] if len(row) > 4 else "")
        if status != "결제완료":
            continue

        # B열: 링크, I열: 전화번호
        link  = row[1] if len(row) > 1 else ""
        phone = "".join(filter(str.isdigit, row[8] if len(row) > 8 else ""))

        current_app.logger.info(f"{idx}행 발송 시도 → 주문번호={order_no}, phone={phone}")
        resp = ds_svc.send_message({ "mobile": phone, "note1": link })
        current_app.logger.info(f"{idx}행 발송 응답: {resp}")

        if resp.get("status") == "1":
            sent_count += 1
            updates.append({"row": idx, "value": "o"})
            # 방금 발송한 주문번호도 집합에 추가 (동일번호 또 skip)
            sent_order_nos.add(order_no)
        else:
            current_app.logger.error(f"{idx}행 발송 실패: {resp}")

    # 4) C열 일괄 업데이트
    if updates:
        sheet_svc.batch_update(updates, tab="통합시트", col="C")
        msg = f"총 {sent_count}건 발송 완료"
    else:
        msg = "전송 대상이 없습니다."

    return render_template_string("""
      <h1>알림톡 발송 결과</h1>
      <p>{{msg}}</p>
      <p><a href="{{ url_for('alerts.send_invite') }}">다시 발송</a></p>
    """, msg=msg)



WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")  # .env 에서 설정

@alerts_bp.route("/webhook-invite", methods=["POST"])
def webhook_invite():
    # 1) 간단 인증
    if request.args.get("key") != WEBHOOK_SECRET:
        return "Unauthorized", 401

    data = request.get_json()
    row   = data.get("row")
    phone = data.get("phone")
    link  = data.get("link")

    # 2) 알림톡 발송
    ds_svc = DirectSendService()
    res = ds_svc.send_messages([{
        "mobile": phone,
        "note1":  link   # 템플릿 변수명에 맞춰 조정
    }])

    # 3) 성공 시 시트에 'o' 찍기
    if all(r.get("status") == "1" for r in res):
        SheetService().batch_update([{"row": row, "value": "o"}])

    return jsonify(res), 200