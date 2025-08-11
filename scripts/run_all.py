#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()


import scripts.auto_purchase as ap
import scripts.auto_admin    as aa
import scripts.export_review as ar
from services.selenium_service import PurchaseAutomator

def main():
    headless = os.getenv("CHROME_HEADLESS", "false").lower() == "true"
    bot = PurchaseAutomator(headless=headless)
    print("[RunAll] ▶ 시작: 사용자측 구매 자동화", flush=True)
    order_no = ap.main(bot)
    print(f"[RunAll] ✔ 완료: 사용자측 구매 자동화 → order_no={order_no}", flush=True)

    print("[RunAll] ▶ 시작: 관리자 API 자동화", flush=True)
    aa.main()
    print("[RunAll] ✔ 완료: 관리자 API 자동화", flush=True)

    print("[RunAll] ▶ 시작: 리뷰 작성 자동화", flush=True)
    ar.main(bot, order_no)
    print("[RunAll] ✔ 완료: 리뷰 작성 자동화", flush=True)

    print("[RunAll] ▶ WebDriver 종료", flush=True)
    bot.close()
    print("[RunAll] 🎉 모든 자동화 단계 완료", flush=True)

if __name__ == "__main__":
    main()
