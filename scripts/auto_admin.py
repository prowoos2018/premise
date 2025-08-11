#!/usr/bin/env python3
# scripts/auto_admin.py

import sys
import os
import time
import logging
import requests

# 프로젝트 루트를 모듈 검색 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.imweb_service import get_imweb_token
from infra.sheet_service import SheetService
from requests.exceptions import HTTPError

# 로거 설정 (INFO 레벨)
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")


def get_order_section_info(order_no: str, token: str):
    """
    /orders/{orderNo} 호출 후, 첫 섹션의 코드와 현재 상태 반환
    """
    url = f"https://openapi.imweb.me/orders/{order_no}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    sections = data.get("sections", [])
    if not sections:
        raise RuntimeError(f"Order {order_no} has no sections")
    sec = sections[0]
    return sec.get("orderSectionCode"), sec.get("orderSectionStatus")


def confirm_bank_transfer(order_no: str, token: str):
    """
    수동 입금 확인 호출 (bank-transfer)
    403 또는 400은 이미 처리되었거나 정보 없음으로 간주
    """
    method = "bank-transfer"
    url = f"https://openapi.imweb.me/payments/{order_no}/{method}/confirm"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.patch(url, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f"{order_no} 입금 확인 완료")
    except HTTPError as e:
        if e.response.status_code not in (403, 400):
            raise


def run_for(order_no: str, token: str):
    """
    주어진 주문번호에 대해 섹션 상태에 따라:
    - PRODUCT_PREPARATION: 입금 확인 후 배송 준비→배송중→배송완료
    - SHIPPING_READY: 배송중→배송완료
    - SHIPPING: 배송완료
    - 기타 상태: 작업 없음
    """
    sec_code, sec_status = get_order_section_info(order_no, token)
    logger.info(f"현재 상태={sec_status} for order={order_no}")

    if sec_status == "PRODUCT_PREPARATION":
        confirm_bank_transfer(order_no, token)
        time.sleep(1)
        statuses = ["SHIPPING_READY", "SHIPPING", "SHIPPING_COMPLETE"]
    elif sec_status == "SHIPPING_READY":
        statuses = ["SHIPPING", "SHIPPING_COMPLETE"]
    elif sec_status == "SHIPPING":
        statuses = ["SHIPPING_COMPLETE"]
    else:
        logger.info(f"처리할 단계 없음 (상태: {sec_status})")
        return

    endpoint = f"https://openapi.imweb.me/orders/{order_no}/order-section/{sec_code}/shipping-operation"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for status in statuses:
        payload = {"orderSectionStatus": status, "orderSectionCodeList": [sec_code]}
        resp = requests.patch(endpoint, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"{order_no} → {status} 완료")
        time.sleep(1)


def main():
    token = get_imweb_token()
    sheet = SheetService()

    # 커맨드라인 인자 사용 시 단일 처리
    if len(sys.argv) > 1:
        order_no = sys.argv[1]
        logger.info(f"CLI 주문번호 사용: {order_no}")
        try:
            run_for(order_no, token)
        except Exception as e:
            logger.error(f"처리 중 오류: {e}")
        return

    # 시트에서 최근 완료건 처리
    records = sheet.fetch_reviews()
    for i in range(len(records)-1, -1, -1):
        row = records[i]
        row_idx = i + 2
        if not row.get("완료") or row.get("관리자완료"):
            continue
        order_no = row["order_no"]
        logger.info(f"처리 시작: 주문번호={order_no} (행 {row_idx})")
        try:
            run_for(order_no, token)
            sheet.mark_admin_complete(row_index=row_idx, value='Y')
            logger.info(f"관리자완료 표시: 행 {row_idx}")
        except Exception as e:
            logger.error(f"오류 발생: {e}")
        break


if __name__ == '__main__':
    main()
