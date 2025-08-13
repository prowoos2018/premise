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

# # --------------------------------------
# # 1) 환경 변수 읽기
# # --------------------------------------
# load_dotenv()  # .env 파일 로딩

# # Flask Secret Key
# SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)

# # IMWEB OAuth 설정
# IMWEB_SITE_CODE     = os.environ.get("IMWEB_SITE_CODE")
# IMWEB_CLIENT_ID     = os.environ.get("IMWEB_CLIENT_ID")
# IMWEB_CLIENT_SECRET = os.environ.get("IMWEB_CLIENT_SECRET")
# IMWEB_REDIRECT_URI  = os.environ.get("IMWEB_REDIRECT_URI")

# # Google Sheets 설정
# GOOGLE_CRED_PATH    = os.environ.get("GOOGLE_SHEET_CREDENTIAL", "").strip()
# SHEET_ID            = os.environ.get("SHEET_ID", "").strip()

# # --------------------------------------
# # 2) 로거 설정: ~/prewoos/debug.log
# # --------------------------------------
# debug_log_path = os.path.join(os.path.dirname(__file__), "debug.log")
# # 혹은 절대 경로를 쓰고 싶다면:
# # debug_log_path = "/home/prewoos2018/prewoos/debug.log"

# # 최상위(root) 로거를 DEBUG 레벨로
# root_logger = logging.getLogger()
# root_logger.setLevel(logging.DEBUG)

# # 로테이팅 핸들러 (파일 용량이 10MB 넘어가면 회전)
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

# # Reverse proxy 설정 (Nginx/Gunicorn 뒤에 있을 경우)
# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# # Flask 자체 로그 레벨도 DEBUG로
# app.logger.setLevel(logging.DEBUG)


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
#     # 아임웹 문서 상 CamelCase 파라미터
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
#         "code":          code
#     }

#     app.logger.debug("[/callback] Token 요청 → URL: %s", token_url)
#     # client_secret 는 민감정보라 빼고 로깅
#     safe_data = {k: v for k, v in data.items() if k != "client_secret"}
#     app.logger.debug("[/callback] 요청 데이터: %s", safe_data)

#     try:
#         resp = requests.post(token_url, headers=headers, data=data, timeout=10)
#         app.logger.debug("[/callback] 응답 상태코드: %s", resp.status_code)
#         app.logger.debug("[/callback] 응답 바디(raw): %s", resp.text)
#         resp.raise_for_status()
#     except requests.exceptions.HTTPError as e:
#         # 4xx, 5xx가 발생한 경우
#         app.logger.error("[/callback] HTTPError: %s", e)
#         return (
#             f"토큰 발급 중 오류 발생.\n"
#             f"Status: {resp.status_code}\n"
#             f"Body: {resp.text}"
#         ), resp.status_code
#     except Exception as ex:
#         # 그 외 알 수 없는 예외
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
#     token = session.get("access_token")
#     if not token:
#         return redirect(url_for("index"))

#     # 1) 주문 목록 API 호출
#     url = "https://openapi.imweb.me/orders?page=1&limit=100"
#     app.logger.debug("[/orders] GET %s with token=%s", url, token[:6]+"...")

#     try:
#         resp = requests.get(
#             url,
#             headers={"Authorization": f"Bearer {token}"},
#             timeout=10
#         )
#         resp.raise_for_status()
#         data = resp.json()
#     except requests.exceptions.HTTPError as e:
#         app.logger.error("[/orders] HTTPError: %s", e)
#         return "주문 조회 실패 (HTTPError)", 400
#     except Exception as ex:
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

#     # 3) 기존 시트에서 주문번호(D열)만 불러와서 set으로 저장
#     sheet = service.spreadsheets()
#     existing_values = sheet.values().get(
#         spreadsheetId=SHEET_ID,
#         range="통합시트!D2:D"
#     ).execute().get("values", [])
#     # [['123'], ['456'], ...] 형태이므로
#     existing_order_nos = {row[0] for row in existing_values if row}

#     app.logger.debug("[/orders] 기존 시트 주문번호: %s", existing_order_nos)

#     # 4) 새로운 주문 중에서 중복되지 않은 것만 rows에 추가
#     rows = []
#     for o in orders:
#         order_no = str(o.get("orderNo", ""))
#         if order_no in existing_order_nos:
#             app.logger.debug("[/orders] 스킵된 주문번호(중복): %s", order_no)
#             continue

#         status = o.get("sections", [{}])[0].get("orderSectionStatus", "")
#         order_status = {
#             "PRODUCT_PREPARATION": "결제대기",
#             "PURCHASE_CONFIRMATION": "결제완료"
#         }.get(status, "")
#         prod_name = (
#             o.get("sections", [{}])[0]
#             .get("sectionItems", [{}])[0]
#             .get("productInfo", {})
#             .get("prodName", "")
#         )
#         orderer_name  = o.get("ordererName", "")
#         orderer_email = o.get("ordererEmail", "")
#         orderer_call  = o.get("ordererCall", "")
#         total_price   = o.get("totalPrice", "")

#         # 결제완료 시 시작/종료일 계산
#         start_date = ""
#         end_date = ""
#         dt = None
#         pay = o.get("payments", [{}])[0].get("paymentCompleteTime")
#         if pay and order_status == "결제완료":
#             dt = datetime.fromisoformat(pay.replace("Z", ""))
#             start_date = dt.strftime("%Y.%m.%d")
#             months = 6 if "6개월" in prod_name else 12 if "12개월" in prod_name else 24 if "24개월" in prod_name else 0
#             if months:
#                 end_date = (dt + relativedelta(months=months) - timedelta(days=1)).strftime("%Y.%m.%d")

#         # None으로 채워야 기존 기본값(수식)이 유지됩니다
#         rows.append([
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

#         ])

#     # 5) 중복 제거 후 남은 row가 있으면 시트에 append
#     if rows:
#         body = {"values": rows}
#         result = sheet.values().append(
#             spreadsheetId=SHEET_ID,
#             range="통합시트!A2",
#             valueInputOption="USER_ENTERED",
#             body=body
#         ).execute()
#         app.logger.info("[/orders] Sheet updated: %s", result)
#     else:
#         app.logger.info("[/orders] 추가할 신규 주문이 없습니다.")

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
