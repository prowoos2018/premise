from flask import (
    Blueprint, session, redirect, url_for,
    current_app, request, abort, jsonify
)
import requests, json, os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from config import Config
from routes.utils import login_required
from services.sheet_service import SheetService
from services.directsend_service import DirectSendService
from services.imweb_service import get_imweb_token

orders_bp = Blueprint("orders", __name__)

def _do_sync(token):
    """IMWEB API 호출 → 구글 시트("통합시트") 동기화 → 알림톡 발송,
       그리고 이미 업데이트된 주문번호는 "주문번호"에 저장하여
       재갱신(중복)되지 않도록 처리합니다.
    """
    if not token:
        current_app.logger.error("IMWEB API 토큰이 없습니다")
        abort(401)

    # =====================================
    # 1) 이미 업데이트한 주문번호 수집 (주문번호)
    # =====================================
    sheet_svc = SheetService()
    try:
        order_no_resp = sheet_svc.sheet.values().get(
            spreadsheetId=Config.SHEET_ID,
            range="주문번호!A2:A"  # 2행부터 A열만
        ).execute()
        # [["1000000001"], ["1000000002"], ... ] 형태의 값
        order_no_values = order_no_resp.get("values", [])
        existing_order_no_set = set()
        for row_data in order_no_values:
            if row_data and row_data[0].strip():
                existing_order_no_set.add(row_data[0].strip())
    except Exception:
        current_app.logger.exception("주문번호 읽기 중 오류")
        return "주문번호 읽기 실패", 500

    # =====================================
    # 2) IMWEB 주문 가져오기
    # =====================================
    try:
        # 1) 최신 발급된 토큰을 읽어와서
        access_token = current_app.config.get("IMWEB_ACCESS_TOKEN")
        if not access_token:
            current_app.logger.error("IMWEB_ACCESS_TOKEN이 설정되지 않음")
            return "토큰 없음", 401

        url = "https://openapi.imweb.me/orders"
        params = {
            "siteCode": current_app.config["IMWEB_SITE_CODE"],
            "page":  1,
            "limit": 100,
        }
        current_app.logger.debug(f"ORDERS REQUEST → url={url}, params={params}")

        # 2) Authorization 헤더에 Bearer 토큰 실어서 요청
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        # 1) 항상 최신 토큰을 발급 혹은 캐시에서 꺼내 옵니다.
        token = get_imweb_token()
        current_app.logger.debug(f"Using IMWEB token: {token[:8]}...")

        # 2) 헤더에 실어서 요청
        resp = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        # =====================================
        # (디버깅) 받은 주문 중 최근 3개만 로깅
        # =====================================
        orders_list = data.get("data", {}).get("list", [])
        recent_orders = orders_list[:3]  # 리스트가 최신순이면 [:3], 오래된 순이면 [-3:]
        # current_app.logger.debug(
        #     "Fetched %d raw orders, logging %d recent: %s",
        #     len(orders_list),
        #     len(recent_orders),
        #     json.dumps(recent_orders, ensure_ascii=False)
        # )
        if data.get("statusCode") != 200:
            current_app.logger.error("주문 조회 실패: %s", data)
            return "주문 조회 실패", 400
        orders = data["data"]["list"]
    except Exception:
        current_app.logger.exception("주문 조회 중 오류")
        return "주문 조회 실패", 500

    # =====================================
    # 3) 통합시트에 추가할 신규 주문만 선별
    # =====================================
    new_rows = []
    new_order_nos = []  # 이번에 새로 업데이트하는 주문번호들 (주문번호에 추가할 예정)

    for o in orders:
        section = o.get("sections", [{}])[0]
        status = section.get("orderSectionStatus")
        # 결제 상태 가져오기
        payment_status = o.get("payments", [{}])[0].get("paymentStatus")

        # 필터링: PRODUCT_PREPARATION 단계는 결제완료된 주문만, 나머 단계는 그대로 처리
        if status not in [
            "PRODUCT_PREPARATION",
            "SHIPPING_READY",
            "SHIPPING",
            "SHIPPING_COMPLETE",
            "PURCHASE_CONFIRMATION",
        ] or (status == "PRODUCT_PREPARATION" and payment_status != "PAYMENT_COMPLETE"):
            continue

        order_no = str(o.get("orderNo", "")).strip()
        # 이미 주문번호에 있으면 중복으로 간주하여 스킵
        if not order_no or order_no in existing_order_no_set:
            continue

        # 일단 여기까지 왔다면 신규 주문번호이므로 업데이트 진행
        prod_name    = section.get("sectionItems", [{}])[0]\
                            .get("productInfo", {})\
                            .get("prodName", "")
        orderer_name = o.get("ordererName", "")
        orderer_email= o.get("ordererEmail", "")
        orderer_call = o.get("ordererCall", "")
        total_price  = o.get("totalPrice", "")

        start_date = end_date = ""
        pay = o.get("payments", [{}])[0].get("paymentCompleteTime")
        if pay:
            dt = datetime.fromisoformat(pay.replace("Z", ""))
            start_date = dt.strftime("%Y.%m.%d")
            months = 0
            if "6개월" in prod_name:
                months = 6
            elif "12개월" in prod_name:
                months = 12
            elif "24개월" in prod_name:
                months = 24
            if months:
                end_date = (
                    dt + relativedelta(months=months) - timedelta(days=1)
                ).strftime("%Y.%m.%d")

        new_rows.append([
            None, None, None,   # A,B,C
            order_no,           # D
            "결제완료",          # E
            prod_name,          # F
            orderer_name,       # G
            orderer_email,      # H
            orderer_call,       # I
            str(total_price),   # J
            start_date,         # K
            end_date,           # L
            None, None, None    # M,N,O
        ])

        new_order_nos.append(order_no)

    # =====================================
    # 4) 통합시트에 신규행 쓰기
    # =====================================
    if new_rows:
        # 통합시트 기존 데이터(A2:L) 불러서, D열 비어있는 첫 행번호 찾기
        resp = sheet_svc.sheet.values().get(
            spreadsheetId=Config.SHEET_ID,
            range="통합시트!A2:L"
        ).execute()
        existing = resp.get("values", [])

        start_row = None
        for idx, row in enumerate(existing, start=2):
            # D열(인덱스 3)이 비어있으면 그 행에부터 채움
            if len(row) <= 3 or not row[3].strip():
                start_row = idx
                break
        if start_row is None:
            # 통합시트가 이미 차있으면 마지막 다음 행에 이어서 쓰기
            start_row = 2 + len(existing)
        end_row    = start_row + len(new_rows) - 1
        write_range= f"통합시트!A{start_row}:O{end_row}"

        try:
            sheet_svc.sheet.values().update(
                spreadsheetId=Config.SHEET_ID,
                range=write_range,
                valueInputOption="USER_ENTERED",
                body={"values": new_rows}
            ).execute()
            current_app.logger.info(
                "통합시트에 %d건 동기화 (%s)",
                len(new_rows), write_range
            )
        except Exception:
            current_app.logger.exception("통합시트 쓰기 중 오류")
            return "통합시트 쓰기 실패", 500

        # 이제 주문번호에도 신규 주문번호를 한 번에 Append
        # [[order_no1],[order_no2] ...] 형태로 만들어야 함
        values_to_append = [[no] for no in new_order_nos]
        try:
            sheet_svc.sheet.values().append(
                spreadsheetId=Config.SHEET_ID,
                range="주문번호!A:A",
                valueInputOption="USER_ENTERED",
                body={"values": values_to_append}
            ).execute()
            current_app.logger.info(
                "주문번호에 %d건 추가 기록", len(values_to_append)
            )
        except Exception as e:
            current_app.logger.exception("주문번호 Append 중 오류")
            current_app.logger.error("Exception details: %s", e)
            return "주문번호 Append 실패", 500


    else:
        current_app.logger.info("신규 주문 없음 (중복 혹은 구매확정 아님)")

    # =====================================
    # 5) 자동 알림톡 발송
    # =====================================
    try:
        all_rows = sheet_svc.fetch_all(tab="통합시트")
        ds_svc   = DirectSendService()

        # 이미 알림톡 보낸 주문번호 (C열='o')를 모아둠
        sent_order_nos = {
            (r[3] if len(r) > 3 else "").strip()
            for r in all_rows
            if len(r) > 2 and r[2].strip().lower() == "o"
        }

        updates = []
        sent_cnt = 0

        for idx, row in enumerate(all_rows, start=2):

            flag     = (row[2] if len(row) > 2 else "").strip().lower()
            order_no = (row[3] if len(row) > 3 else "").strip()
            status   = (row[4] if len(row) > 4 else "")

            # 이미 보냈거나, 결제완료가 아니면 스킵
            if flag == "o" or order_no in sent_order_nos or status != "결제완료":
                continue

            link  = row[1] if len(row) > 1 else ""
            phone = "".join(filter(str.isdigit, row[8] if len(row) > 8 else ""))

            current_app.logger.info(f"{idx}행 주문번호={order_no} 발송 시도 → {phone}")
            result = ds_svc.send_messages([
                {"mobile": phone, "note1": link}
            ])[0]
            current_app.logger.info(f"{idx}행 응답: {result}")
            current_app.logger.info(f"{idx}템플릿 번호: {Config.DS_TEMPLATE_NO}")

            if result.get("status") == "1":
                sent_cnt += 1
                updates.append({"row": idx, "value": "o"})
                sent_order_nos.add(order_no)
            else:
                current_app.logger.error(f"{idx}행 발송 실패: {result}")

        if updates:
            sheet_svc.batch_update(updates, tab="통합시트", col="C")
            current_app.logger.info(
                "알림톡 발송 완료 및 C열 업데이트: %d건",
                sent_cnt
            )
        else:
            current_app.logger.info("알림톡 발송 대상 없음")
    except Exception:
        current_app.logger.exception("자동 알림톡 발송 중 오류")

    return "<h1>주문 동기화 및 자동 알림톡 발송 완료</h1>"


@orders_bp.route("/orders")
@login_required
def orders():
    """
    사용자 요청 시 수동 동기화 실행:
    - get_imweb_token() 으로 토큰 발급/갱신 후 _do_sync(token) 호출
    """
    try:
        token = get_imweb_token()
        session["access_token"] = token
    except Exception:
        current_app.logger.exception("수동 동기화용 토큰 발급 실패")
        abort(401, description="토큰 발급 실패")

    return _do_sync(token)


@orders_bp.route("/internal/orders-sync")
def internal_orders_sync():
    """
    서버 내부(예: 크론잡)에서 호출할 수 있는 엔드포인트:
    sync_token 쿼리스트링 검사 후 _do_sync(token)
    """
    sync_token = request.args.get("sync_token")
    current_app.logger.debug(f"internal_orders_sync 호출 - sync_token={{sync_token}}")
    if not sync_token or sync_token != current_app.config["SYNC_TOKEN"]:
        current_app.logger.warning(f"Unauthorized sync attempt - sync_token={{sync_token}}")
        abort(401)

    try:
        current_app.logger.info("Starting internal orders sync")
        user_token = get_imweb_token()
        current_app.logger.debug(f"Obtained IMWeb token: {{user_token}}")
        result = _do_sync(user_token)
        current_app.logger.info("Internal orders sync completed successfully")
        current_app.logger.debug(f"Sync result: {{result}}")
        return result
    except Exception as e:
        current_app.logger.exception("Internal sync 에러 발생")
        return f"Internal sync 에러: {e}", 500


@orders_bp.route("/debug_token")
def debug_token():
    """디버그용: 현재 토큰 발급이 잘 되는지 확인"""
    try:
        token = get_imweb_token()
        return jsonify({"token": token}), 200
    except Exception as e:
        current_app.logger.exception("DEBUG_TOKEN 에러")
        return jsonify({"error": str(e)}), 500
