# import os
# import json
# import logging
# from logging.handlers import RotatingFileHandler
# import requests
# from flask import Flask, request, session, redirect, url_for
# from dotenv import load_dotenv
# from datetime import datetime, timedelta
# from dateutil.relativedelta import relativedelta
# from werkzeug.middleware.proxy_fix import ProxyFix
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from collections import defaultdict

# # --------------------------------------
# # 1) 환경 변수 읽기
# # --------------------------------------
# load_dotenv()  # .env 파일 로딩

# SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)

# IMWEB_SITE_CODE     = os.environ.get("IMWEB_SITE_CODE")
# IMWEB_CLIENT_ID     = os.environ.get("IMWEB_CLIENT_ID")
# IMWEB_CLIENT_SECRET = os.environ.get("IMWEB_CLIENT_SECRET")
# IMWEB_REDIRECT_URI  = os.environ.get("IMWEB_REDIRECT_URI")

# GOOGLE_CRED_PATH    = os.environ.get("GOOGLE_SHEET_CREDENTIAL", "").strip()
# SHEET_ID            = os.environ.get("SHEET_ID", "").strip()

# # --------------------------------------
# # 2) 로거 설정
# # --------------------------------------
# debug_log_path = os.path.join(os.path.dirname(__file__), "debug.log")

# root_logger = logging.getLogger()
# root_logger.setLevel(logging.DEBUG)

# rot_handler = RotatingFileHandler(
#     debug_log_path,
#     maxBytes=10 * 1024 * 1024,
#     backupCount=5,
#     encoding="utf-8"
# )
# rot_handler.setLevel(logging.DEBUG)
# rot_handler.setFormatter(logging.Formatter(
#     "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
# ))
# root_logger.addHandler(rot_handler)

# # --------------------------------------
# # 3) Flask 애플리케이션 설정
# # --------------------------------------
# app = Flask(__name__)
# app.secret_key = SECRET_KEY
# app.config["SESSION_COOKIE_DOMAIN"] = ".prewoos.store"

# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
# app.logger.setLevel(logging.DEBUG)

# # --------------------------------------
# # 토큰 갱신 함수
# # --------------------------------------
# def refresh_access_token():
#     refresh_token = session.get("refresh_token")
#     if not refresh_token:
#         return False

#     token_url = "https://openapi.imweb.me/oauth2/token"
#     data = {
#         "grantType":    "refresh_token",
#         "clientId":     IMWEB_CLIENT_ID,
#         "clientSecret": IMWEB_CLIENT_SECRET,
#         "refreshToken": refresh_token,
#     }
#     try:
#         resp = requests.post(token_url, data=data, timeout=10)
#         resp.raise_for_status()
#         payload = resp.json()
#         if payload.get("statusCode") == 200:
#             session["access_token"]  = payload["data"]["accessToken"]
#             session["refresh_token"] = payload["data"]["refreshToken"]
#             app.logger.info("토큰 갱신 성공: 새 Access Token 발급")
#             return True
#         else:
#             app.logger.error("토큰 갱신 실패: %s", payload)
#     except Exception:
#         app.logger.exception("토큰 갱신 중 오류 발생")

#     return False

# # --------------------------------------
# # 4) 라우트 정의
# # --------------------------------------
# @app.route("/")
# def index():
#     token = session.get("access_token")
#     app.logger.info("[/] Access Token in session: %s", token)
#     if not token:
#         return (
#             "<h1>아임웹 OAuth 데모</h1>"
#             f"<p><a href='{url_for('login')}'>아임웹 로그인하기</a></p>"
#         )
#     return (
#         "<h1>로그인 성공</h1>"
#         f"<p>Access Token: {token}</p>"
#         f"<p><a href='{url_for('orders')}'>주문 목록 가져오기</a></p>"
#         f"<p><a href='{url_for('logout')}'>로그아웃</a></p>"
#     )

# @app.route("/login")
# def login():
#     scope = "order:read site-info:write"
#     url = (
#         "https://openapi.imweb.me/oauth2/authorize"
#         f"?responseType=code"
#         f"&clientId={IMWEB_CLIENT_ID}"
#         f"&redirectUri={IMWEB_REDIRECT_URI}"
#         f"&siteCode={IMWEB_SITE_CODE}"
#         f"&scope={scope}"
#     )
#     app.logger.debug("[/login] Redirecting to authorize: %s", url)
#     return redirect(url)

# @app.route("/callback")
# def callback():
#     code = request.args.get("code")
#     if not code:
#         app.logger.warning("[/callback] code 파라미터 누락")
#         return "인가 코드가 없습니다.", 400

#     token_url = "https://openapi.imweb.me/oauth2/token"
#     headers = {"Content-Type": "application/x-www-form-urlencoded"}
#     data = {
#         "grantType":    "authorization_code",
#         "clientId":     IMWEB_CLIENT_ID,
#         "clientSecret": IMWEB_CLIENT_SECRET,
#         "redirectUri":  IMWEB_REDIRECT_URI,
#         "code":         code
#     }

#     app.logger.debug("[/callback] Token 요청 → URL: %s", token_url)
#     safe_data = {k: v for k, v in data.items() if k != "client_secret"}
#     app.logger.debug("[/callback] 요청 데이터: %s", safe_data)

#     try:
#         resp = requests.post(token_url, headers=headers, data=data, timeout=10)
#         app.logger.debug("[/callback] 응답 상태코드: %s", resp.status_code)
#         app.logger.debug("[/callback] 응답 바디(raw): %s", resp.text)
#         resp.raise_for_status()
#     except requests.exceptions.HTTPError as e:
#         app.logger.error("[/callback] HTTPError: %s", e)
#         return (
#             f"토큰 발급 중 오류 발생.\n"
#             f"Status: {resp.status_code}\n"
#             f"Body: {resp.text}"
#         ), resp.status_code
#     except Exception:
#         app.logger.exception("[/callback] 알 수 없는 예외 발생")
#         return "서버 처리 중 알 수 없는 오류가 발생했습니다.", 500

#     try:
#         payload = resp.json()
#     except ValueError:
#         app.logger.error("[/callback] JSON 디코딩 실패: %s", resp.text)
#         return "토큰 응답을 파싱할 수 없습니다.", 500

#     app.logger.debug("[/callback] 응답 JSON payload: %s", payload)
#     if payload.get("statusCode") != 200:
#         app.logger.error("[/callback] 토큰 발급 실패: %s", payload)
#         return f"토큰 발급 실패: {payload}", 400

#     info = payload["data"]
#     session["access_token"]  = info.get("accessToken")
#     session["refresh_token"] = info.get("refreshToken")
#     app.logger.info("[/callback] 토큰 발급 성공: access_token=%s", info.get("accessToken"))
#     return redirect(url_for("index"))

# @app.route("/orders")
# def orders():
#     """주문 목록 조회 후 상태별로 다른 시트에 업데이트. (D열 기준으로 '빈 행' 찾는 방식)"""
#     token = session.get("access_token")
#     if not token:
#         return redirect(url_for("index"))

#     url = "https://openapi.imweb.me/orders?page=1&limit=100"
#     app.logger.debug("[/orders] GET %s with token=%s", url, token[:6] + "...")

#     # 1) 첫 시도
#     try:
#         resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
#         if resp.status_code in [401, 403]:
#             # 토큰 만료로 가정하여 refresh 시도
#             app.logger.warning("[/orders] 토큰 만료 또는 권한에러 발생. 토큰 재발급 시도합니다.")
#             if refresh_access_token():
#                 token = session.get("access_token")
#                 resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
#             else:
#                 return redirect(url_for("login"))

#         resp.raise_for_status()
#         data = resp.json()
#     except requests.exceptions.HTTPError as e:
#         app.logger.error("[/orders] HTTPError: %s", e)
#         return "주문 조회 실패 (HTTPError)", 400
#     except Exception:
#         app.logger.exception("[/orders] 알 수 없는 예외")
#         return "서버 처리 중 오류가 발생했습니다.", 500

#     if data.get("statusCode") != 200:
#         app.logger.error("[/orders] statusCode != 200: %s", data)
#         return f"주문 조회 실패: {data}", 400

#     orders = data["data"]["list"]
#     app.logger.info("[/orders] 가져온 주문 수: %d", len(orders))

#     if not (GOOGLE_CRED_PATH and SHEET_ID):
#         return "구글 시트 설정이 되어 있지 않습니다.", 500

#     # 2) Google Sheets 클라이언트 준비
#     if os.path.isfile(GOOGLE_CRED_PATH):
#         sa_info = json.load(open(GOOGLE_CRED_PATH, encoding="utf-8"))
#     else:
#         sa_info = json.loads(GOOGLE_CRED_PATH)
#     creds = service_account.Credentials.from_service_account_info(
#         sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
#     )
#     service = build("sheets", "v4", credentials=creds)
#     sheet = service.spreadsheets()

#     # 3) 상태별 시트에 넣기 위해 dict 준비
#     rows_by_sheet = defaultdict(list)

#     for o in orders:
#         status_code = o.get("sections", [{}])[0].get("orderSectionStatus", "")

#         # 상태별로 매핑
#         if status_code == "PRODUCT_PREPARATION":   
#             # 결제대기
#             order_status = "결제대기"
#             target_sheet = "결제전"
#         elif status_code == "PURCHASE_CONFIRMATION":
#             # 결제완료
#             order_status = "결제완료"
#             target_sheet = "통합시트"
#         elif status_code == "CANCEL_COMPLETE":
#             # 취소완료
#             order_status = "취소완료"
#             target_sheet = "취소완료"
#         else:
#             # 기타 상태
#             order_status = status_code
#             target_sheet = "통합시트"

#         order_no = str(o.get("orderNo", ""))
#         prod_name = (
#             o.get("sections", [{}])[0]
#              .get("sectionItems", [{}])[0]
#              .get("productInfo", {})
#              .get("prodName", "")
#         )
#         orderer_name  = o.get("ordererName", "")
#         orderer_email = o.get("ordererEmail", "")
#         orderer_call  = o.get("ordererCall", "")
#         total_price   = o.get("totalPrice", "")

#         # 결제완료면 시작/종료일 계산
#         start_date = ""
#         end_date = ""
#         pay = o.get("payments", [{}])[0].get("paymentCompleteTime")
#         if pay and order_status == "결제완료":
#             dt = datetime.fromisoformat(pay.replace("Z", ""))
#             start_date = dt.strftime("%Y.%m.%d")
#             months = 6 if "6개월" in prod_name else 12 if "12개월" in prod_name else 24 if "24개월" in prod_name else 0
#             if months:
#                 end_date = (dt + relativedelta(months=months) - timedelta(days=1)).strftime("%Y.%m.%d")

#         # 실제로 시트에 들어갈 row 데이터 (A~O 15열)
#         row_data = [
#             None, None, None,
#             order_no,
#             order_status,
#             prod_name,
#             orderer_name,
#             orderer_email,
#             orderer_call,
#             str(total_price),
#             start_date,
#             end_date,
#             None, None, None,
#         ]
#         rows_by_sheet[target_sheet].append(row_data)

#     # 4) 각 시트마다 "D열"을 기준으로 현재 몇 개의 데이터가 있는지 확인하고,
#     #    그 다음 행부터 new_rows를 update
#     for target_sheet, new_rows in rows_by_sheet.items():
#         if not new_rows:
#             continue

#         # (1) 시트에서 D2:D 범위를 읽어, 몇 개의 행이 존재하는지 확인
#         read_range = f"{target_sheet}!D2:D"
#         try:
#             existing_values = sheet.values().get(
#                 spreadsheetId=SHEET_ID,
#                 range=read_range
#             ).execute().get("values", [])
#         except Exception:
#             existing_values = []
#             app.logger.exception(f"시트({target_sheet}) D열 조회 실패")

#         # 이미 사용된(채워진) row 개수
#         used_count = len(existing_values)  # D2부터
#         # next_empty_row = 2 + used_count → 다음에 기록할 행 번호
#         start_row = 2 + used_count
#         # 예: used_count=3이라면 이미 D2, D3, D4가 사용됨 → start_row = 5

#         end_row = start_row + len(new_rows) - 1
#         write_range = f"{target_sheet}!A{start_row}:O{end_row}"  # 15열(A~O)

#         app.logger.info(
#             "[%s] 기존 D열: %d행 사용됨 → 새 데이터 %d건을 %s 범위에 기록",
#             target_sheet, used_count, len(new_rows), write_range
#         )

#         # (2) update 사용
#         body = {"values": new_rows}
#         try:
#             result = sheet.values().update(
#                 spreadsheetId=SHEET_ID,
#                 range=write_range,
#                 valueInputOption="USER_ENTERED",
#                 body=body
#             ).execute()
#             app.logger.info("[%s] update 결과: %s", target_sheet, result)
#         except Exception:
#             app.logger.exception(f"[{target_sheet}] update 중 오류")

#     return (
#         "<h1>주문 목록 & 시트 업데이트 완료</h1>"
#         f"<pre>{json.dumps(orders, ensure_ascii=False, indent=2)}</pre>"
#     )

# @app.route("/logout")
# def logout():
#     session.clear()
#     return redirect(url_for("index"))

# # --------------------------------------
# # 5) 앱 실행 (개발용)
# # --------------------------------------
# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 5001))
#     app.run(host="0.0.0.0", port=port, debug=False)