# infra/google_client.py
import os
import json
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build


def _load_gcp_service_account_info() -> dict:
    """
    Load SA JSON from env (content or base64) or from file path.
    Supported envs (in this order):
      1) GOOGLE_CREDENTIALS_JSON   (content or base64)
      2) GOOGLE_SHEET_CREDENTIAL   (content/base64 OR path)
      3) GOOGLE_APPLICATION_CREDENTIALS (path)
    """
    # 1) JSON 내용(평문/베이스64) 우선
    for var in ("GOOGLE_CREDENTIALS_JSON", "GOOGLE_SHEET_CREDENTIAL"):
        val = os.getenv(var, "").strip()
        if not val:
            continue
        try:
            if val.startswith("{"):
                return json.loads(val)  # 평문 JSON
            # base64일 가능성
            decoded = base64.b64decode(val).decode("utf-8")
            return json.loads(decoded)
        except Exception as e:
            raise RuntimeError(f"{var} parse error: {e}")

    # 2) 파일 경로
    for var in ("GOOGLE_SHEET_CREDENTIAL", "GOOGLE_APPLICATION_CREDENTIALS"):
        path = os.getenv(var, "").strip()
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    raise RuntimeError(
        "No Google credentials found. "
        "Set GOOGLE_CREDENTIALS_JSON (content/base64) "
        "or GOOGLE_SHEET_CREDENTIAL (content/base64 or path) "
        "or GOOGLE_APPLICATION_CREDENTIALS (path)."
    )


# ---- init once at import time ----
_sa_info = _load_gcp_service_account_info()

_scopes = ["https://www.googleapis.com/auth/spreadsheets"]
_creds = service_account.Credentials.from_service_account_info(_sa_info, scopes=_scopes)

# cache_discovery=False만 두면 안전
_SHEETS_SERVICE = build("sheets", "v4", credentials=_creds, cache_discovery=False).spreadsheets()


def get_sheets_service():
    return _SHEETS_SERVICE
