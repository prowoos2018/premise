# infra/directsend_client.py

import os
import requests
import json
import logging
from config import Config

# 모듈 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def send_kakao_notice(receivers, *,
                      address_books=None,
                      duplicate_yn=None,
                      kakao_faild_type=None,
                      title=None,
                      message=None,
                      sender=None,
                      reserve_type=None,
                      start_reserve_time=None,
                      end_reserve_time=None,
                      remained_count=None,
                      return_url_yn=None,
                      return_url=None,
                      attaches=None):
    """
    receivers: [
      {'name':str, 'mobile':str, 'note1':str, … 'note5':str},
      ...
    ]
    메시지를 발송하고, 발송 ID를 포함한 응답(json)을 반환합니다.
    """
    url = "https://directsend.co.kr/index.php/api_v2/kakao_notice"
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json; charset=utf-8"
    }

    # 기본 payload 구성
    payload = {
        "username":         Config.DS_USERNAME,
        "key":              Config.DS_API_KEY,
        "kakao_plus_id":    Config.DS_PLUS_ID,
        "user_template_no": Config.DS_TEMPLATE_NO,
        "receiver":         receivers
    }

    # 옵션 파라미터는 값이 있을 때만 추가
    if address_books:           payload["address_books"]       = address_books
    if duplicate_yn is not None:payload["duplicate_yn"]        = duplicate_yn
    if kakao_faild_type:        payload["kakao_faild_type"]    = kakao_faild_type
    if title:                   payload["title"]               = title
    if message:                 payload["message"]             = message
    if sender:                  payload["sender"]              = sender
    if reserve_type:            payload["reserve_type"]         = reserve_type
    if start_reserve_time:      payload["start_reserve_time"]   = start_reserve_time
    if end_reserve_time:        payload["end_reserve_time"]     = end_reserve_time
    if remained_count:          payload["remained_count"]       = remained_count
    if return_url_yn is not None:payload["return_url_yn"]       = return_url_yn
    if return_url is not None:   payload["return_url"]           = return_url
    if attaches:                payload["attaches"]            = attaches

    # payload 로깅
    logger.debug(f"[DS DEBUG] send_kakao_notice payload: {json.dumps(payload, ensure_ascii=False)}")

    # 발송 요청
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.exception(f"[DS ERROR] send_kakao_notice API 호출 실패: {e}")
        raise

    result = resp.json()
    logger.debug(f"[DS DEBUG] send_kakao_notice result: {result}")

    # 발송 ID 추출
    notice_id = None
    data = result.get("data")
    if isinstance(data, dict):
        notice_id = data.get("notice_id") or data.get("message_id")
    elif isinstance(data, list) and data:
        notice_id = data[0].get("notice_id") or data[0].get("message_id")

    if not notice_id:
        logger.error(f"[DS ERROR] 발송 ID 추출 실패, result: {result}")
        return result

    logger.debug(f"[DS DEBUG] 발송 ID: {notice_id}")

    # 상세 결과 조회 및 로깅
    try:
        detail = get_kakao_notice_result(notice_id)
        logger.debug(f"[DS DEBUG] 상세조회(detail): {detail}")
    except Exception as e:
        logger.exception(f"[DS ERROR] 상세조회 API 호출 실패: {e}")

    return result


def get_kakao_notice_result(notice_id):
    """
    발송 결과 상세조회 API 호출
    notice_id: send_kakao_notice에서 반환된 발송 ID
    """
    url = "https://directsend.co.kr/index.php/api_v2/kakao_notice/get_send_result"
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "username":         Config.DS_USERNAME,
        "key":              Config.DS_API_KEY,
        "user_template_no": Config.DS_TEMPLATE_NO,
        "notice_id":        notice_id
    }

    logger.debug(f"[DS DEBUG] get_kakao_notice_result payload: {payload}")

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    detail = resp.json()
    return detail