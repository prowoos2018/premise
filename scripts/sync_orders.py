#!/usr/bin/env python3
import os
from app import create_app
from routes.orders import orders  # 뷰 함수 그대로 재사용

# 앱 생성
app = create_app()

if __name__ == "__main__":
    # HTTP 요청 없이 로직만 직접 실행
    with app.app_context():
        # 기존 /orders 엔드포인트 로직 호출
        result = orders()
        # 필요하면 result 객체 확인해서 로그 남기기
