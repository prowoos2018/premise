# app.py

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config

# blueprint들
from routes.auth import auth_bp
from routes.orders import orders_bp
from routes.alerts import alerts_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ProxyFix 설정 (필요시)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # 블루프린트 등록
    app.register_blueprint(auth_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(alerts_bp)

    return app
