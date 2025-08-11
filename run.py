# run.py
import os
from dotenv import load_dotenv

# 1) .env 로드 (Config import 전에!)
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

from flask import Flask
from logging.handlers import RotatingFileHandler
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

# 1) 환경변수 로드
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)
init_refresh_token()

def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)
    app.config["SESSION_COOKIE_DOMAIN"]     = ".premise.site/"
    SESSION_COOKIE_SECURE=False,  # HTTPS면 True
    app.config["SESSION_COOKIE_HTTPONLY"]   = True
    
    # 2) 시크릿키 설정
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") 

    # 3) 로거 설정 (debug.log 파일로 기록)
    log_path = os.path.join(os.path.dirname(__file__), "debug.log")
    handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    # root logger에도, app.logger에도 붙여두면 좋습니다
    logging.getLogger().addHandler(handler)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG)

    app.logger.propagate = False

    # 4) 블루프린트 등록
    app.register_blueprint(auth_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(automation_bp, url_prefix="/automation")

    return app

app = create_app()


if __name__ == "__main__":
    # 개발용
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
