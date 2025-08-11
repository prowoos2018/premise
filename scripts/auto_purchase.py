# scripts/auto_purchase.py

import sys
import os
import time
from urllib.parse import urlparse, parse_qs

# 프로젝트 루트를 모듈 검색 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from services.selenium_service import PurchaseAutomator
from infra.sheet_service import SheetService

def main(bot):
    print("[auto_purchase] main() 호출", flush=True)
    sheet_svc = SheetService()
    records   = sheet_svc.fetch_reviews()
    print(f"[auto_purchase] 시트에서 {len(records)}건 로드", flush=True)
    print("[auto_purchase] PurchaseAutomator 초기화 완료", flush=True)

    for i, row in enumerate(records):
        print(f"[auto_purchase] row {i+2} 검사: 완료={row.get('완료')}", flush=True)
        row_num = i + 2  # 시트 상 1-based 인덱스, 헤더 다음이 2번째 행

        # 이미 완료된 항목은 건너뜀
        if row.get("완료"):
            print(f"[{row_num}행] 이미 완료: 스킵")
            continue

        # 첫 번째 비완료 항목만 처리
        name   = row["이름"]
        review = row["리뷰내용"]
        email  = row.get("이메일", "prewoos2018@gmail.com")
        phone  = row.get("연락처", "010-5003-6206")

        # 1) 구매 요청 및 order_no 추출
        order_no = bot.purchase(name=name, phone=phone, email=email)
        print(f"[{row_num}행] 주문완료 → order_no={order_no}")

        # 2) 스프레드시트에 order_no 업데이트
        sheet_svc.update_order_no(row_index=row_num, order_no=order_no)
        # 3) 완료 표시
        sheet_svc.mark_complete(row_index=row_num, value="Y")
        print(f"[{row_num}행] 완료 표시 및 스크립트 종료")

        # 첫 건 처리 후 루프 탈출
        return order_no
    
    return None


if __name__ == "__main__":
    main()
