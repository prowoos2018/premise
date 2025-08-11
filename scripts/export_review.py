#!/usr/bin/env python3
import os
import sys
# 프로젝트 루트를 모듈 검색 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infra.sheet_service import SheetService
from services.selenium_service import PurchaseAutomator


def main(bot, target_order=None):
    print("[export_review] ▶ main() 시작", flush=True)
    sheet_svc = SheetService()
    records = sheet_svc.fetch_reviews()
    print(f"[export_review] 시트에서 총 {len(records)}건 로드", flush=True)

    if not target_order:
        print("[export_review] ❌ 대상 주문번호가 지정되지 않았습니다.", flush=True)
        return

    print(f"[export_review] ▶ 주문번호 검색: {target_order}", flush=True)
    for idx, row in enumerate(records, start=2):
        print(f"[export_review] {idx}행: order_no={row.get('order_no')}, 완료={row.get('완료')}", flush=True)
        if row.get('완료') and row.get('order_no') == target_order:
            print(f"[export_review] ▶ {idx}행 매칭, 리뷰작성 시작", flush=True)
            # 일치하는 행의 이름과 연락처 사용
            bot.submit_review(
                order_no=target_order,
                phone=row.get('연락처', '01050036206'),
                name=row.get('이름'),
                review=row.get('리뷰내용')
            )
            sheet_svc.mark_review_complete(row_index=idx)
            print(f"[export_review] ✔ {idx}행 리뷰작성 완료", flush=True)
            return

    print(f"[export_review] ❌ 주문번호 {target_order}를 찾지 못했거나 아직 완료되지 않았습니다.", flush=True)


if __name__ == "__main__":
    # standalone 모드: CLI 인자 처리
    target = sys.argv[1] if len(sys.argv) > 1 else None
    bot = PurchaseAutomator(headless=False)
    main(bot, target)
    bot.close()
