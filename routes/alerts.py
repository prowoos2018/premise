# routes/alerts.py
from flask import Blueprint, render_template_string, request, jsonify, current_app, make_response
from services.sheet_service import SheetService
from services.aligo_service import AligoService
from googleapiclient.errors import HttpError
import json

alerts_bp = Blueprint("alerts", __name__)
aligo = AligoService()

def _html_error(msg: str, code: int = 500, detail: str | None = None):
    body = f"<h2>알림톡 발송 에러</h2><p>{msg}</p>"
    if detail:
        body += f"<pre style='white-space:pre-wrap'>{detail}</pre>"
    return make_response(body, code)

@alerts_bp.route("/send-invite")
def send_invite():
    try:
        sheet_svc = SheetService()
        # 1) 시트 전체 읽기
        rows = sheet_svc.fetch_all(tab="통합시트")
        if not rows:
            return "<p>통합시트에 데이터가 없습니다.</p>"
    except HttpError as e:
        status = getattr(e.resp, "status", "unknown")
        try:
            body = e.content.decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        return _html_error("시트 조회 실패 (Google API)", 500, f"HTTP {status}\n{body}")
    except Exception as e:
        current_app.logger.exception("/send-invite: 시트 읽기 중 예외")
        return _html_error("시트 조회 실패 (일반)", 500, repr(e))

    # 2) 이미 발송된(=C열 o) 주문번호 집합
    sent_order_nos = {
        (row[3] if len(row) > 3 else "").strip()
        for row in rows
        if len(row) > 2 and (row[2] or "").strip().lower() == "o"
    }

    updates = []
    sent_count = 0
    tried_count = 0

    try:
        # 3) 한 행씩 순회하며 발송
        for idx, row in enumerate(rows, start=2):
            # C열: 발송여부
            flag = (row[2] if len(row) > 2 else "").strip().lower()
            if flag == "o":
                continue

            # D열: 주문번호
            order_no = (row[3] if len(row) > 3 else "").strip()
            if not order_no:
                continue

            if order_no in sent_order_nos:
                # 이미 발송된 주문번호면 skip
                current_app.logger.debug("%d행 주문번호 %s → 이미 발송됨, 건너뜀", idx, order_no)
                continue

            # E열: 주문상태
            status = (row[4] if len(row) > 4 else "")
            if status != "결제완료":
                continue

            # B열: 링크, I열: 전화번호
            link  = row[1] if len(row) > 1 else ""
            phone_raw = row[8] if len(row) > 8 else ""
            phone = "".join(ch for ch in (phone_raw or "") if ch.isdigit())

            if not phone:
                current_app.logger.warning("%d행 전화번호 없음, 스킵 (order_no=%s)", idx, order_no)
                continue

            tried_count += 1
            current_app.logger.info("%d행 발송 시도 → 주문번호=%s, phone=%s, link=%s", idx, order_no, phone, link)

            # 알리고 발송 (DirectSend 대체)
            try:
                res = aligo.send_messages([{"mobile": phone, "note1": link}])[0]
            except Exception as e:
                current_app.logger.exception("%d행 알리고 호출 중 예외", idx)
                return _html_error("알리고 호출 중 예외", 500, repr(e))

            current_app.logger.info("%d행 알리고 응답: %s", idx, res)

            if str(res.get("status")) == "1":
                sent_count += 1
                updates.append({"row": idx, "value": "o"})
                sent_order_nos.add(order_no)
            else:
                # 실패 원인 화면에서도 보이게
                return _html_error(
                    "알림톡 발송 실패",
                    500,
                    json.dumps(res, ensure_ascii=False)
                )

        # 4) C열 일괄 업데이트
        if updates:
            try:
                sheet_svc.batch_update(updates, tab="통합시트", col="C")
            except HttpError as e:
                status = getattr(e.resp, "status", "unknown")
                try:
                    body = e.content.decode("utf-8", errors="ignore")
                except Exception:
                    body = str(e)
                return _html_error("시트 업데이트 실패 (Google API)", 500, f"HTTP {status}\n{body}")
            except Exception as e:
                current_app.logger.exception("시트 업데이트 실패(일반)")
                return _html_error("시트 업데이트 실패 (일반)", 500, repr(e))
            msg = f"총 {sent_count}건 발송 완료 (시도 {tried_count}건)"
        else:
            msg = f"전송 대상이 없습니다. (시도 {tried_count}건)"

        return render_template_string("""
          <h1>알림톡 발송 결과</h1>
          <p>{{msg}}</p>
          <p><a href="{{ url_for('alerts.send_invite') }}">다시 발송</a></p>
        """, msg=msg)

    except Exception as e:
        current_app.logger.exception("/send-invite 처리 중 예외")
        return _html_error("알림톡 처리 중 예외", 500, repr(e))


# 웹훅: 단건 발송
import os
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

@alerts_bp.route("/webhook-invite", methods=["POST"])
def webhook_invite():
    if request.args.get("key") != WEBHOOK_SECRET:
        return "Unauthorized", 401

    data = request.get_json(silent=True) or {}
    row   = data.get("row")
    phone = data.get("phone")
    link  = data.get("link")

    if not phone:
        return jsonify({"error": "phone is required"}), 400

    try:
        res = aligo.send_messages([{"mobile": phone, "note1": link}])
    except Exception as e:
        current_app.logger.exception("웹훅 알리고 호출 중 예외")
        return jsonify({"error": repr(e)}), 500

    if all(r.get("status") == "1" for r in res):
        try:
            if row:
                SheetService().batch_update([{"row": row, "value": "o"}], tab="통합시트", col="C")
        except Exception:
            current_app.logger.exception("웹훅: 시트 업데이트 실패")

    return jsonify(res), 200
