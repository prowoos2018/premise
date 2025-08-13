#!/usr/bin/env python3
# scripts/auto_return.py

import sys
import logging
from services.imweb_service import get_imweb_token
from scripts.auto_admin import get_order_section_info, run_for as admin_run_for
import requests

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://openapi.imweb.me"


def request_return(order_no: str, section_code: str, token: str):
    """
    반품접수: retrieveType ETC, returnReason 구매 의사 취소
    retrieveMemo 필수 포함
    오류 시 상태 코드와 응답 본문을 로깅
    """
    url = f"{BASE_URL}/orders/{order_no}/order-section/{section_code}/return-request"
    payload = {
        "retrieveType": "ETC",
        "returnReason": "구매 의사 취소",
        "returnReasonDetail": "구매 의사 취소",
        "retrieveMemo": "구매 의사 취소"
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"✔ 반품접수 완료: {resp.status_code}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"반품접수 실패: status={e.response.status_code}, body={e.response.text}")
        raise


def complete_retrieve(order_no: str, section_code: str, token: str):
    """
    수거완료 처리
    오류 시 상태 코드와 응답 본문을 로깅
    """
    url = f"{BASE_URL}/orders/{order_no}/order-section/{section_code}/retrieve-complete"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.patch(url, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f"✔ 수거완료 처리: {resp.status_code}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"수거완료 실패: status={e.response.status_code}, body={e.response.text}")
        raise


def approve_return(order_no: str, section_code: str, token: str):
    """
    반품승인: excludeRefundAmount, excludeRefundPoint 기본 0
    오류 시 상태 코드와 응답 본문을 로깅
    """
    url = f"{BASE_URL}/orders/{order_no}/order-section/{section_code}/return-approve"
    payload = {
        "returnedCoupons": [],
        "excludeRefundAmount": 0,
        "excludeRefundPoint": 0
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"✔ 반품승인 완료: {resp.status_code}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"반품승인 실패: status={e.response.status_code}, body={e.response.text}")
        raise


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m scripts.auto_return <order_no>")
        sys.exit(1)

    order_no = sys.argv[1]
    token = get_imweb_token()

    # 섹션 코드 및 현재 상태 조회
    try:
        section_code, section_status = get_order_section_info(order_no, token)
        logger.info(f"▶ 섹션코드: {section_code}, 현재 상태: {section_status}")
    except Exception as e:
        logger.error(f"섹션코드 조회 실패: {e}")
        sys.exit(1)

    # 상태에 따른 처리
    try:
        if section_status == "SHIPPING_COMPLETE":
            # 반품접수 → 수거완료 → 반품승인
            logger.info("▶ 반품접수 시작")
            request_return(order_no, section_code, token)

            logger.info("▶ 수거완료 처리 시작")
            complete_retrieve(order_no, section_code, token)

            logger.info("▶ 반품승인 시작")
            approve_return(order_no, section_code, token)

        elif section_status == "RETURN_REQUEST":
            # 이미 반품접수 된 상태이므로 반품승인만 수행
            logger.info("▶ 반품승인 시작 (이미 RETURN_REQUEST)")
            approve_return(order_no, section_code, token)

        else:
            logger.error(f"지원하지 않는 상태: {section_status}. SHIPPING_COMPLETE 혹은 RETURN_REQUEST이어야 합니다.")
            sys.exit(1)

        logger.info("🎉 모든 반품 처리 단계 완료 🎉")

    except Exception:
        logger.error("반품 처리 중 오류 발생, 자동화 종료")
        sys.exit(1)


if __name__ == '__main__':
    main()
