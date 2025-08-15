import os
import time
import requests
import logging
from dotenv import find_dotenv, load_dotenv, set_key

# 이 모듈 전용 로거
logger = logging.getLogger(__name__)

# 프로젝트 루트의 .env 파일 경로
dotenv_path = find_dotenv()
LOAD_ENV_ARGS = {"override": True}

# 토큰 캐시 구조
token_cache = {
    "access_token":  None,
    "refresh_token": None,
    "expires_at":    0,
}


def init_refresh_token():
    """
    앱 시작 시 .env에서 IMWEB_REFRESH_TOKEN을 읽어 캐시에 넣습니다.
    """
    rt = os.environ.get("IMWEB_REFRESH_TOKEN")
    if not rt:
        logger.error("[IMWEB] IMWEB_REFRESH_TOKEN 환경변수 누락")
    else:
        logger.info("[IMWEB] Refresh Token 초기화 완료: %s...", rt[:8])
    token_cache["refresh_token"] = rt


def get_imweb_token():
    """
    - access_token이 유효하면 재사용
    - 아니면 refresh_token으로 새 토큰 발급 및 .env 갱신
    """
    # 0) 매 호출 시 .env 재로딩 (override)하여 최신 환경변수 적용
    try:
        load_dotenv(dotenv_path, **LOAD_ENV_ARGS)
        logger.debug(
            "[IMWEB] .env 재로딩: IMWEB_REFRESH_TOKEN=%s",
            (os.environ.get("IMWEB_REFRESH_TOKEN") or "")[:8] + "..."
        )
    except Exception:
        logger.exception("[IMWEB] .env 재로딩 실패")

    # 1) 최신 env 토큰이 캐시와 다르면 캐시 갱신
    rt_env = os.environ.get("IMWEB_REFRESH_TOKEN")
    if rt_env and rt_env != token_cache.get("refresh_token"):
        old = (token_cache.get("refresh_token") or "")[:8] + "..."
        new = rt_env[:8] + "..."
        logger.info("[IMWEB] env 리프레시 토큰 갱신: %s → %s", old, new)
        token_cache["refresh_token"] = rt_env

    now = time.time()
    # 2) 유효한 access_token 재사용
    if token_cache["access_token"] and now < token_cache["expires_at"] - 60:
        return token_cache["access_token"]

    # 3) refresh_token 준비
    refresh_token = token_cache.get("refresh_token")
    if not refresh_token:
        logger.error("[IMWEB] Refresh token not set")
        raise RuntimeError("Refresh token not set")

    # 4) 환경 설정 로깅
    client_id     = os.environ.get("IMWEB_CLIENT_ID")
    client_secret = os.environ.get("IMWEB_CLIENT_SECRET")
    redirect_uri  = os.environ.get("IMWEB_REDIRECT_URI")
    logger.debug(
        "[IMWEB DEBUG] ENV CLIENT_ID=%s, REDIRECT_URI=%s",
        client_id, redirect_uri
    )

    # 5) 토큰 재발급 요청
    url = "https://openapi.imweb.me/oauth2/token"
    data = {
        "grantType":    "refresh_token",
        "clientId":     client_id,
        "clientSecret": client_secret,
        "redirectUri":  redirect_uri,
        "refreshToken": refresh_token,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    logger.debug("[IMWEB DEBUG] POST data=%s", {k: v[:8]+"..." if k=="refreshToken" else v for k,v in data.items()})

    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        logger.debug("[IMWEB DEBUG] Response code=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        logger.exception("[IMWEB] 토큰 재발급 요청 실패")
        raise

    info       = payload.get("data", {})
    new_at     = info.get("accessToken")
    new_rt     = info.get("refreshToken", refresh_token)
    expires_in = info.get("expiresIn", info.get("expires_in", 3600))
    try:
        expires_in = int(expires_in)
    except Exception:
        expires_in = 3600

    if not new_at:
        logger.error("[IMWEB] accessToken 누락: %s", payload)
        raise RuntimeError("IMWEB accessToken not returned")

    # 7) .env 저장 (실패해도 캐시는 갱신)
    try:
        set_key(dotenv_path, "IMWEB_ACCESS_TOKEN",  new_at)
        set_key(dotenv_path, "IMWEB_REFRESH_TOKEN", new_rt)
        logger.info("[IMWEB] .env에 access/refresh 토큰 동기화 완료: %s..., %s...", new_at[:8], new_rt[:8])
    except Exception:
        logger.exception("[IMWEB] .env 파일에 토큰 저장 실패")

    token_cache.update({
        "access_token":  new_at,
        "refresh_token": new_rt,
        "expires_at":    now + expires_in,
    })
    logger.info("[IMWEB] 토큰 갱신 성공 - expires in %d초", expires_in)
    return new_at
