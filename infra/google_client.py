# infra/google_client.py
import os
import json
import base64
import logging
from functools import lru_cache
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# 우선순위:
# 1) GOOGLE_CREDENTIALS_JSON  (raw JSON 또는 base64)
# 2) GOOGLE_SHEET_CREDENTIAL  (raw JSON / base64 / 파일경로)
# 3) GOOGLE_APPLICATION_CREDENTIALS (파일경로)
ENV_RAW_OR_B64 = ("GOOGLE_CREDENTIALS_JSON", "GOOGLE_SHEET_CREDENTIAL")
ENV_PATH_ONLY  = ("GOOGLE_SHEET_CREDENTIAL", "GOOGLE_APPLICATION_CREDENTIALS")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _b64decode_with_padding(s: str) -> bytes:
    """
    base64 문자열의 공백/개행 제거 후 필요한 '=' 패딩을 보정해서 디코딩.
    """
    t = s.strip().replace("\n", "").replace(" ", "")
    missing = (-len(t)) % 4
    if missing:
        t += "=" * missing
    return base64.b64decode(t)

def _load_gcp_service_account_info() -> dict:
    """
    SA JSON 로드:
      - ENV(raw JSON 또는 base64) → GOOGLE_CREDENTIALS_JSON, GOOGLE_SHEET_CREDENTIAL
      - 파일 경로 → GOOGLE_SHEET_CREDENTIAL, GOOGLE_APPLICATION_CREDENTIALS
    """
    # 1) raw JSON / base64
    for var in ENV_RAW_OR_B64:
        val = os.getenv(var, "").strip()
        if not val:
            continue

        # raw JSON
        if val.startswith("{"):
            try:
                info = json.loads(val)
                logger.debug("Loaded SA info from %s (raw JSON)", var)
                return info
            except Exception as e:
                raise RuntimeError(f"{var} raw json parse error: {e}")

        # base64(JSON)
        try:
            decoded = _b64decode_with_padding(val).decode("utf-8")
            info = json.loads(decoded)
            logger.debug("Loaded SA info from %s (base64)", var)
            return info
        except Exception as e:
            raise RuntimeError(f"{var} base64 parse error: {e}")

    # 2) 파일 경로
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
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return creds

@lru_cache(maxsize=1)
def _get_sheets_resource():
    """
    lazy-load로 Google Sheets 클라이언트 생성.
    기존 코드 호환을 위해 .spreadsheets() 리소스를 반환.
    """
    creds = _get_credentials()
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return svc.spreadsheets()

def get_sheets_service():
    """
    사용처에서는 그대로 호출해서 쓰면 됩니다.
    예) sheets = get_sheets_service()
        sheets.values().get(...).execute()
    """
    return _get_sheets_resource()
