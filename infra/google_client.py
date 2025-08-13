# infra/google_client.py
import os
import json
import base64
import logging
from functools import lru_cache
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

ENV_RAW_OR_B64 = ("GOOGLE_CREDENTIALS_JSON", "GOOGLE_SHEET_CREDENTIAL")
ENV_PATH_ONLY  = ("GOOGLE_SHEET_CREDENTIAL", "GOOGLE_APPLICATION_CREDENTIALS")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _b64decode_with_padding(s: str) -> bytes:
    t = s.strip().replace("\n", "").replace(" ", "")
    missing = (-len(t)) % 4
    if missing:
        t += "=" * missing
    return base64.b64decode(t)

def _looks_like_path(val: str) -> bool:
    return val.endswith(".json") or (os.sep in val)

def _load_gcp_service_account_info() -> dict:
    """
    SA JSON 로드 우선순위:
      1) ENV(raw JSON)
      2) ENV(파일 경로)  ←★ 경로로 보이면 먼저 파일 시도
      3) ENV(base64 JSON)
      4) PATH 전용 ENV(파일 경로)
    """
    for var in ENV_RAW_OR_B64:
        val = os.getenv(var, "").strip()
        if not val:
            continue

        # 1) raw JSON
        if val.startswith("{"):
            try:
                info = json.loads(val)
                logger.debug("Loaded SA info from %s (raw JSON)", var)
                return info
            except Exception as e:
                raise RuntimeError(f"{var} raw json parse error: {e}")

        # 2) 파일 경로로 보이면 우선 파일 시도
        if _looks_like_path(val) and os.path.exists(val):
            try:
                with open(val, "r", encoding="utf-8") as f:
                    info = json.load(f)
                logger.debug("Loaded SA info from %s (file: %s)", var, val)
                return info
            except Exception as e:
                raise RuntimeError(f"{var} file read error: {e}")

        # 3) base64(JSON) 시도 (실패해도 다른 경로로 폴백)
        try:
            decoded = _b64decode_with_padding(val).decode("utf-8")
            info = json.loads(decoded)
            logger.debug("Loaded SA info from %s (base64)", var)
            return info
        except Exception:
            # 여기서 바로 예외 던지지 말고 다음 케이스로 폴백
            logger.debug("%s is not valid base64 JSON, will try other sources.", var)

    # 4) 경로 전용 ENV들
    for var in ENV_PATH_ONLY:
        path = os.getenv(var, "").strip()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                logger.debug("Loaded SA info from %s (file: %s)", var, path)
                return info
            except Exception as e:
                raise RuntimeError(f"{var} file read error: {e}")

    raise RuntimeError(
        "No Google credentials found. "
        "Set GOOGLE_CREDENTIALS_JSON (raw/base64) "
        "or GOOGLE_SHEET_CREDENTIAL (raw/base64 or path) "
        "or GOOGLE_APPLICATION_CREDENTIALS (path)."
    )

@lru_cache(maxsize=1)
def _get_credentials() -> service_account.Credentials:
    info = _load_gcp_service_account_info()
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

@lru_cache(maxsize=1)
def _get_sheets_resource():
    creds = _get_credentials()
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return svc.spreadsheets()

def get_sheets_service():
    return _get_sheets_resource()
