# routes/orders.py
from flask import (
    Blueprint, session, redirect, url_for,
    current_app, request, abort, jsonify, make_response
)
import requests, json, os, traceback
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from config import Config
from routes.utils import login_required
from services.sheet_service import SheetService
from services.imweb_service import get_imweb_token
# 파일 상단 import에 추가
import time, random
from googleapiclient.errors import HttpError
from services.aligo_service import AligoService

aligo = AligoService()


RETRY_STATUS = {429, 500, 502, 503, 504}

def _exec_with_retry(request, label: str, max_attempts: int = 6, base_sleep: float = 0.7):
    """
    Google Sheets API request.execute() 재시도 래퍼.
    429/5xx에서 지수 백오프로 재시도. 각 시도마다 상세 로그 남김.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            # discovery는 execute(num_retries=...)도 지원하지만,
            # 우리가 커스텀 백오프/로그를 원해 직접 감싼다.
            resp = request.execute()
            if attempt > 1:
                current_app.logger.warning("[%s] 성공 (attempt=%d)", label, attempt)
            return resp
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            body = ""
            try:
                body = e.content.decode("utf-8", errors="ignore")
            except Exception:
                body = str(e)
            current_app.logger.error("[%s] HttpError attempt=%d status=%s body=%s",
                                     label, attempt, status, body[:600])

            if status in RETRY_STATUS and attempt < max_attempts:
                sleep = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 0.4)
                time.sleep(sleep)
                continue
            raise
        except Exception as e:
            current_app.logger.exception("[%s] Exception attempt=%d", label, attempt)
            if attempt < max_attempts:
                sleep = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 0.4)
                time.sleep(sleep)
                continue
            raise

orders_bp = Blueprint("orders", __name__)

def _html_error(msg: str, code: int = 500, detail: str | None = None):
    body = f"<h2>주문 동기화 에러</h2><p>{msg}</p>"
    if detail:
        body += f"<pre style='white-space:pre-wrap'>{detail}</pre>"
    resp = make_response(body, code)
    return resp

def _require_config(key: str) -> str:
    val = current_app.config.get(key) or getattr(Config, key, None)
    if not val:
        raise RuntimeError(f"필수 설정 누락: {key}")
    return val

def _safe_get(d: dict, path: list[str], default=None):
    cur = d
    try:
        for k in path:
            if isinstance(k, int):
                cur = (cur or [])[k]
            else:
                cur = (cur or {}).get(k)
        return cur if cur is not None else default
    except Exception:
        return default

def _do_sync(token: str):
    """IMWEB 주문 → 구글시트 동기화 → 알림톡 발송."""
    try:
        # ========= 0) 필수 설정 확인 =========
        sheet_id = _require_config("SHEET_ID")
        site_code = _require_config("IMWEB_SITE_CODE")
    except Exception as e:
        current_app.logger.exception("설정 확인 중 오류")
        return _html_error("환경설정 누락으로 동기화 불가", 500, str(e))

    if not token:
        current_app.logger.error("IMWEB API 토큰이 없습니다")
        return _html_error("IMWEB API 토큰이 없습니다", 401)

    # ========= 1) 이미 업데이트한 주문번호 수집 (주문번호 시트) =========
    try:
        sheet_svc = SheetService()
        sheet_id = _require_config("SHEET_ID")  # 안전하게 한 번 더 보장
        req = sheet_svc.sheet.values().get(
            spreadsheetId=sheet_id,
            range="주문번호!A2:A"
        )
        resp = _exec_with_retry(req, "주문번호 읽기")
        existing_order_no_set = {
            (row[0] or "").strip()
            for row in resp.get("values", [])
            if row and (row[0] or "").strip()
        }
        current_app.logger.debug("기존 주문번호 %d건 로드", len(existing_order_no_set))
    except HttpError as e:
        status = getattr(e.resp, "status", "unknown")
        body = ""
        try:
            body = e.content.decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        return _html_error(
            "주문번호 시트 읽기 실패 (Google API)",
            500,
            f"HTTP {status}\n{body}"
        )
    except Exception as e:
        return _html_error("주문번호 시트 읽기 실패 (일반)", 500, repr(e))


    # ========= 2) IMWEB 주문 가져오기 =========
    try:
        url = "https://openapi.imweb.me/orders"
        params = {"siteCode": site_code, "page": 1, "limit": 100}
        headers = {"Authorization": f"Bearer {token}"}
        current_app.logger.debug("ORDERS REQUEST url=%s params=%s", url, params)
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        current_app.logger.debug("ORDERS RESPONSE %s %s", resp.status_code, resp.text[:800])
        resp.raise_for_status()
        data = resp.json()
        if data.get("statusCode") != 200:
            msg = f"IMWEB 주문 조회 실패: {data}"
            current_app.logger.error(msg)
            return _html_error("IMWEB 주문 조회 실패", 400, json.dumps(data, ensure_ascii=False))
        orders = _safe_get(data, ["data", "list"], []) or []
        current_app.logger.info("IMWEB 주문 %d건 수신", len(orders))
    except Exception as e:
        current_app.logger.exception("주문 조회 중 오류")
        return _html_error("IMWEB 주문 조회 중 예외", 500, str(e))

    # ========= 3) 신규 주문 선별 =========
    new_rows = []
    new_order_nos = []

    try:
        for o in orders:
            section0 = _safe_get(o, ["sections", 0], {}) or {}
            status = section0.get("orderSectionStatus")
            payment0 = _safe_get(o, ["payments", 0], {}) or {}
            payment_status = payment0.get("paymentStatus")

            if status not in {
                "PRODUCT_PREPARATION",
                "SHIPPING_READY",
                "SHIPPING",
                "SHIPPING_COMPLETE",
                "PURCHASE_CONFIRMATION",
            } or (status == "PRODUCT_PREPARATION" and payment_status != "PAYMENT_COMPLETE"):
                continue

            order_no = str(o.get("orderNo", "")).strip()
            if not order_no or order_no in existing_order_no_set:
                continue

            prod_name = _safe_get(section0, ["sectionItems", 0, "productInfo", "prodName"], "") or ""
            orderer_name = o.get("ordererName", "") or ""
            orderer_email = o.get("ordererEmail", "") or ""
            orderer_call = o.get("ordererCall", "") or ""
            total_price = o.get("totalPrice", "")

            start_date = end_date = ""
            pay_iso = payment0.get("paymentCompleteTime")
            if pay_iso:
                try:
                    # '2025-08-11T12:34:56Z' → fromisoformat 호환
                    dt = datetime.fromisoformat(pay_iso.replace("Z", "+00:00")).astimezone()
                    start_date = dt.strftime("%Y.%m.%d")
                    months = 0
                    name = prod_name or ""
                    if "6개월" in name:
                        months = 6
                    elif "12개월" in name:
                        months = 12
                    elif "24개월" in name:
                        months = 24
                    if months:
                        end_date = (dt + relativedelta(months=months) - timedelta(days=1)).strftime("%Y.%m.%d")
                except Exception:
                    current_app.logger.warning("결제완료일 파싱 실패: %s", pay_iso)

            new_rows.append([
                None, None, None,            # A,B,C
                order_no,                    # D
                "결제완료",                   # E
                prod_name,                   # F
                orderer_name,                # G
                orderer_email,               # H
                orderer_call,                # I
                str(total_price),            # J
                start_date,                  # K
                end_date,                    # L
                None, None, None             # M,N,O
            ])
            new_order_nos.append(order_no)

        current_app.logger.info("신규 행 후보 %d건", len(new_rows))
    except Exception as e:
        current_app.logger.exception("신규 주문 선별 중 오류")
        return _html_error("신규 주문 선별 실패", 500, str(e))

    # ========= 4) 통합시트 쓰기 & 주문번호 추가 =========
    try:
        if new_rows:
            # 통합시트 값 읽기 (빈 자리 탐색) — 재시도 적용
            req = sheet_svc.sheet.values().get(
                spreadsheetId=sheet_id,
                range="통합시트!A2:L"
            )
            resp = _exec_with_retry(req, "통합시트 읽기", max_attempts=8, base_sleep=0.8)
            existing = resp.get("values", [])

            # 첫 번째 빈 D열 위치 찾기
            start_row = None
            for idx, row in enumerate(existing, start=2):
                if len(row) <= 3 or not (row[3] or "").strip():
                    start_row = idx
                    break
            if start_row is None:
                start_row = 2 + len(existing)

            end_row = start_row + len(new_rows) - 1
            write_range = f"통합시트!A{start_row}:O{end_row}"

            # 값 업데이트 — 재시도 적용
            req = sheet_svc.sheet.values().update(
                spreadsheetId=sheet_id,
                range=write_range,
                valueInputOption="USER_ENTERED",
                body={"values": new_rows}
            )
            _ = _exec_with_retry(req, "통합시트 쓰기")
            current_app.logger.info("통합시트에 %d건 동기화 (%s)", len(new_rows), write_range)

            # 주문번호 시트 Append — 재시도 적용
            values_to_append = [[no] for no in new_order_nos]
            req = sheet_svc.sheet.values().append(
                spreadsheetId=sheet_id,
                range="주문번호!A:A",
                valueInputOption="USER_ENTERED",
                body={"values": values_to_append}
            )
            _ = _exec_with_retry(req, "주문번호 Append")
            current_app.logger.info("주문번호에 %d건 추가", len(values_to_append))
        else:
            current_app.logger.info("신규 주문 없음 (중복 혹은 상태 미충족)")
    except Exception as e:
        current_app.logger.exception("시트 쓰기 중 오류")
        return _html_error("시트 쓰기 실패", 500, str(e))


    # ========= 5) 자동 알림톡 발송 =========
    try:
        all_rows = sheet_svc.fetch_all(tab="통합시트")

        sent_order_nos = {
            (r[3] if len(r) > 3 else "").strip()
            for r in all_rows
            if len(r) > 2 and (r[2] or "").strip().lower() == "o"
        }

        updates = []
        sent_cnt = 0

        for idx, row in enumerate(all_rows, start=2):
            flag = (row[2] if len(row) > 2 else "").strip().lower()
            order_no = (row[3] if len(row) > 3 else "").strip()
            status = (row[4] if len(row) > 4 else "")

            if flag == "o" or order_no in sent_order_nos or status != "결제완료":
                continue

            link = row[1] if len(row) > 1 else ""
            phone_raw = row[8] if len(row) > 8 else ""
            phone = "".join(ch for ch in (phone_raw or "") if ch.isdigit())

            if not phone:
                current_app.logger.warning("%d행 전화번호 없음, 스킵 (order_no=%s)", idx, order_no)
                continue

            current_app.logger.info("%d행 주문번호=%s 발송 시도 → %s", idx, order_no, phone)
            result = aligo.send_messages([{"mobile": phone, "note1": link}])[0]
            current_app.logger.info("%d행 응답: %s", idx, result)
            current_app.logger.info("%d행 알리고 템플릿 코드: %s", idx, Config.ALIGO_TPL_CODE)

            if str(result.get("status")) == "1":
                sent_cnt += 1
                updates.append({"row": idx, "value": "o"})
                sent_order_nos.add(order_no)
            else:
                current_app.logger.error("%d행 발송 실패: %s", idx, result)

        if updates:
            sheet_svc.batch_update(updates, tab="통합시트", col="C")
            current_app.logger.info("알림톡 발송 및 C열 업데이트 %d건", sent_cnt)
        else:
            current_app.logger.info("알림톡 발송 대상 없음")
    except Exception as e:
        current_app.logger.exception("자동 알림톡 발송 중 오류")
        # 발송 실패는 동기화 자체를 실패로 만들지 않음
        pass

    return "<h1>주문 동기화 및 자동 알림톡 발송 완료</h1>"

@orders_bp.route("/orders")
@login_required
def orders():
    """
    수동 동기화: 토큰 발급/갱신 후 _do_sync(token)
    """
    try:
        token = get_imweb_token()
        if token:
            session["access_token"] = token  # 참고용
        else:
            raise RuntimeError("get_imweb_token()이 빈 토큰을 반환")
    except Exception as e:
        current_app.logger.exception("수동 동기화용 토큰 발급 실패")
        return _html_error("IMWEB 토큰 발급 실패", 401, str(e))

    try:
        return _do_sync(token)
    except Exception as e:
        current_app.logger.exception("/orders 핸들러 예외")
        return _html_error("동기화 처리 중 예외", 500, traceback.format_exc())

@orders_bp.route("/internal/orders-sync")
def internal_orders_sync():
    """
    서버 내부(예: 크론) 호출용: sync_token 검사 후 실행
    """
    try:
        sync_token_cfg = _require_config("SYNC_TOKEN")
    except Exception as e:
        current_app.logger.exception("SYNC_TOKEN 설정 누락")
        return _html_error("SYNC_TOKEN 설정 누락", 500, str(e))

    sync_token = request.args.get("sync_token")
    if not sync_token or sync_token != sync_token_cfg:
        current_app.logger.warning("Unauthorized sync attempt - sync_token=%s", sync_token)
        abort(401)

    try:
        user_token = get_imweb_token()
        return _do_sync(user_token)
    except Exception as e:
        current_app.logger.exception("Internal sync 에러")
        return _html_error("Internal sync 에러", 500, str(e))

@orders_bp.route("/debug_token")
def debug_token():
    """디버그용: 현재 토큰 발급이 잘 되는지 확인"""
    try:
        token = get_imweb_token()
        return jsonify({"token": token}), 200
    except Exception as e:
        current_app.logger.exception("DEBUG_TOKEN 에러")
        return jsonify({"error": str(e)}), 500

@orders_bp.route("/debug/sheets")
def debug_sheets():
    """
    시트 메타/권한/탭 목록 디버그용:
    - SHEET_ID가 맞는지
    - 서비스계정 권한이 있는지
    - '주문번호' 탭이 실제로 존재하는지
    """
    try:
        sheet_id = _require_config("SHEET_ID")
    except Exception as e:
        return _html_error("SHEET_ID 설정 누락", 500, str(e))

    try:
        # 메타 조회
        svc = SheetService().svc  # 필요하면 SheetService에서 svc(= build("sheets",...)) 제공
        # 만약 SheetService에 svc가 없다면, 아래 한 줄로 대체:
        # from infra.google_client import _get_credentials
        # svc = build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)

        meta = svc.spreadsheets().get(
            spreadsheetId=sheet_id,
            includeGridData=False
        ).execute()

        props = meta.get("properties", {})
        sheets = meta.get("sheets", []) or []
        titles = [s.get("properties", {}).get("title") for s in sheets]

        body = {
            "spreadsheetId": sheet_id,
            "title": props.get("title"),
            "sheet_titles": titles,
            "hint": "여기 목록에 '주문번호'가 반드시 있어야 합니다.",
        }
        return jsonify(body), 200

    except HttpError as e:
        status = getattr(e.resp, "status", "unknown")
        body = ""
        try:
            body = e.content.decode("utf-8", errors="ignore")
        except Exception:
            body = str(e)
        return _html_error("Sheets 메타 조회 실패 (Google API)", 500, f"HTTP {status}\n{body}")
    except Exception as e:
        return _html_error("Sheets 메타 조회 실패 (일반)", 500, repr(e))