# run.py
import os
from dotenv import load_dotenv

# 1) .env 로드 (Config import 전에!)
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

from flask import Flask, request, session
from logging.handlers import RotatingFileHandler
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from datetime import timedelta

# Config import
from config import Config

# 블루프린트 import
from routes.auth import auth_bp
from routes.orders import orders_bp
from routes.alerts import alerts_bp
from routes.automation import automation_bp  # 추가: 자동화 블루프린트
from services.imweb_service import init_refresh_token


# 최초 기동 시 refresh_token 초기화 시도 (필요 시)
init_refresh_token()


def create_app():
    app = Flask(__name__)

    # 기본 설정 로드
    app.config.from_object(Config)

    # ★ 세션/쿠키 설정 (중요)
    # - 단일 도메인이면 "premise.site" 로 지정 (".premise.site/" ❌, 슬래시 금지)
    app.config["SESSION_COOKIE_DOMAIN"]   = "premise.site"
    app.config["SESSION_COOKIE_SECURE"]   = False          # HTTPS 환경이면 True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)

    # 시크릿키 고정 (재기동 시 세션 무효화 방지)
    # FLASK_SECRET_KEY 가 있으면 우선 사용, 없으면 Config.SECRET_KEY 사용
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or getattr(Config, "SECRET_KEY", None)

    # 리버스 프록시(Nginx 등) 뒤에 있을 때 스킴/호스트 보정
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # 로깅 설정 (debug.log 파일로 기록)
    log_path = os.path.join(os.path.dirname(__file__), "debug.log")
    handler = RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    # root & app logger에 연결
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG)
    app.logger.propagate = False

    # 요청/응답 디버그 훅
    @app.before_request
    def _dbg_before():
        app.logger.debug(">>> %s %s", request.method, request.url)
        app.logger.debug(">>> Headers: %s", dict(request.headers))
        app.logger.debug(">>> Cookies: %s", request.cookies)
        try:
            # 세션은 lazy-load이므로 접근해서 키 확인
            app.logger.debug(">>> Session(keys): %s", list(session.keys()))
        except Exception as e:
            app.logger.exception("Session access failed: %s", e)

    @app.after_request
    def _dbg_after(resp):
        app.logger.debug("<<< Status: %s", resp.status)
        # Set-Cookie 확인 (세션이 실제로 구워지는지)
        app.logger.debug("<<< Set-Cookie: %s", resp.headers.get("Set-Cookie"))
        return resp

    # 블루프린트 등록
    app.register_blueprint(auth_bp)  # /login, /callback, /
    app.register_blueprint(orders_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(automation_bp, url_prefix="/automation")

    return app


app = create_app()

if __name__ == "__main__":
    # 개발용 실행
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
