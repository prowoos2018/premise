# services/routes/auth.py (updated)

from flask import Blueprint, session, redirect, url_for, request, current_app, render_template
import requests
from urllib.parse import quote_plus
from config import Config

auth_bp = Blueprint("auth", __name__)


def refresh_token():
    """
    세션에 저장된 리프레시 토큰으로 access 토큰 갱신
    """
    data = {
        "grantType":    "refresh_token",
        "clientId":     Config.IMWEB_CLIENT_ID,
        "clientSecret": Config.IMWEB_CLIENT_SECRET,
        "redirectUri":  Config.IMWEB_REDIRECT_URI,
        "refreshToken": session.get("refresh_token"),
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(
        "https://openapi.imweb.me/oauth2/token",
        data=data, headers=headers, timeout=10
    )
    resp.raise_for_status()
    info = resp.json().get("data", {})
    session["access_token"]  = info.get("accessToken")
    session["refresh_token"] = info.get("refreshToken")


@auth_bp.route("/")
def index():
    token = session.get("access_token")
    if not token:
        current_app.logger.debug("Index: 토큰 없음 → login.html 렌더링")
        return render_template("login.html")
    return render_template("index.html")


@auth_bp.route("/login")
def login():
    """
    Imweb OAuth 인가 페이지로 리다이렉트
    """
    scope = "order:read site-info:write"
    authorize_url = (
        "https://openapi.imweb.me/oauth2/authorize"
        f"?responseType=code"
        f"&clientId={Config.IMWEB_CLIENT_ID}"
        f"&redirectUri={Config.IMWEB_REDIRECT_URI}"
        f"&siteCode={Config.IMWEB_SITE_CODE}"
        f"&scope={quote_plus(scope)}"
    )
    return redirect(authorize_url)


@auth_bp.route("/callback")
def callback():
    """
    Imweb이 보내준 code를 받아 세션에 저장 후 토큰 교환 및 .env에 tokens 저장
    """
    # 1) OAuth 에러 처리
    err = request.args.get("errorCode")
    if err:
        msg = request.args.get("message", "")
        current_app.logger.error(f"OAuth 에러: {err} / {msg}")
        return f"로그인 실패: {msg}", 400

    # 2) 인가 코드 획득
    code = request.args.get("code")
    if not code:
        current_app.logger.error("callback 호출 시 code 파라미터 누락")
        return "인가 코드가 없습니다.", 400

    # 3) 세션에 authorization code 저장
    session["authorization_code"] = code
    current_app.logger.debug(f"authorization_code 저장: {code}")

    # 4) 토큰 교환 요청
    token_url = "https://openapi.imweb.me/oauth2/token"
    data = {
        "grantType":    "authorization_code",
        "clientId":     Config.IMWEB_CLIENT_ID,
        "clientSecret": Config.IMWEB_CLIENT_SECRET,
        "redirectUri":  Config.IMWEB_REDIRECT_URI,
        "code":         code,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    current_app.logger.debug("TOKEN REQUEST DATA: %s", data)
    current_app.logger.debug("TOKEN REQUEST HEADERS: %s", headers)

    try:
        resp = requests.post(token_url, data=data, headers=headers, timeout=10)
        current_app.logger.debug("TOKEN RESPONSE STATUS: %s, BODY: %s", resp.status_code, resp.text)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        current_app.logger.exception("토큰 요청 중 예외 발생")
        return "토큰 요청 실패", 500

    # 5) 응답 처리
    if payload.get("statusCode") != 200:
        current_app.logger.error("토큰 발급 실패: %s", payload)
        return f"토큰 발급 실패: {payload.get('error', payload)}", 400

    info = payload["data"]
    access_token  = info.get("accessToken")
    refresh_token = info.get("refreshToken")

    # 6) 세션에 토큰 저장
    session["access_token"]  = access_token
    session["refresh_token"] = refresh_token
    session.permanent = True
    current_app.logger.debug("토큰 발급 성공: access_token 및 refresh_token 저장 완료")

    # 7) .env 파일에 새로운 tokens 영구 저장
    try:
        from dotenv import set_key, find_dotenv
        dotenv_path = find_dotenv()
        # refresh token
        set_key(dotenv_path, "IMWEB_REFRESH_TOKEN", refresh_token)
        current_app.logger.info(".env에 새 IMWEB_REFRESH_TOKEN 저장 완료")
        # access token
        set_key(dotenv_path, "IMWEB_ACCESS_TOKEN", access_token)
        current_app.logger.info(".env에 새 IMWEB_ACCESS_TOKEN 저장 완료")
    except Exception:
        current_app.logger.exception(".env 파일에 토큰 저장 중 예외 발생")

    # 8) 로그인 완료 후 인덱스로 리다이렉트
    return redirect(url_for("auth.index"))


@auth_bp.route("/logout")
def logout():
    """
    세션 초기화 후 로그인 페이지로 이동
    """
    session.clear()
    current_app.logger.debug("세션 로그아웃 완료")
    return redirect(url_for("auth.login"))
