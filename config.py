import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로딩

class Config:
    SECRET_KEY            = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)
    SESSION_COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN", None)

    # IMWEB OAuth
    IMWEB_SITE_CODE       = os.environ.get("IMWEB_SITE_CODE")
    IMWEB_CLIENT_ID       = os.environ.get("IMWEB_CLIENT_ID")
    IMWEB_CLIENT_SECRET   = os.environ.get("IMWEB_CLIENT_SECRET")
    IMWEB_REDIRECT_URI    = os.environ.get("IMWEB_REDIRECT_URI")

    # Google Sheets
    GOOGLE_SHEET_CREDENTIAL = os.environ.get("GOOGLE_SHEET_CREDENTIAL", "").strip()
    SHEET_ID               = os.environ.get("SHEET_ID", "").strip()

    # SENS (알림톡)
    SENS_ACCESS_KEY       = os.environ.get("SENS_ACCESS_KEY")
    SENS_SECRET_KEY       = os.environ.get("SENS_SECRET_KEY")
    SENS_SERVICE_ID       = os.environ.get("SENS_SERVICE_ID")
    PLUS_FRIEND_ID        = os.environ.get("PLUS_FRIEND_ID")
    TEMPLATE_CODE         = os.environ.get("TEMPLATE_CODE")
    SENDER_NO             = os.environ.get("SENDER_NO")
    DS_USERNAME    = os.environ.get("DS_USERNAME")
    DS_API_KEY     = os.environ.get("DS_API_KEY")
    DS_PLUS_ID     = os.environ.get("DS_PLUS_ID")
    DS_TEMPLATE_NO = os.environ.get("DS_TEMPLATE_NO")

    SYNC_TOKEN = os.environ.get("SYNC_TOKEN","d2c0c892-68c3-4726-8553-ebba2c2ae928")
    IMWEB_API_TOKEN = os.environ.get("IMWEB_API_TOKEN")
    IMWEB_REFRESH_TOKEN= os.environ.get("IMWEB_REFRESH_TOKEN")
    IMWEB_ACCESS_TOKEN = os.environ.get("IMWEB_ACCESS_TOKEN")
    # config.py
    CHROME_DRIVER_PATH    = os.environ.get(
        "CHROME_DRIVER_PATH",
        "/absolute/path/to/chromedriver"
    )    
    SHEET_CREDENTIALS_PATH = os.environ.get("GOOGLE_SHEET_CREDENTIAL", "").strip()
    REVIEW_SHEET_ID        = os.environ.get("REVIEW_SHEET_ID", "").strip()
    ALIGO_API_KEY   = os.getenv("ALIGO_API_KEY", "")
    ALIGO_USER_ID   = os.getenv("ALIGO_USER_ID", "")
    ALIGO_SENDERKEY = os.getenv("ALIGO_SENDERKEY", "")
    ALIGO_TPL_CODE  = os.getenv("ALIGO_TPL_CODE", "")
    ALIGO_SENDER    = os.getenv("ALIGO_SENDER", "")
    ALIGO_BUTTON_NAME = os.getenv("ALIGO_BUTTON_NAME", "신청서 작성")
    ALIGO_SUBJECT     = os.getenv("ALIGO_SUBJECT", "")
    ALIGO_EMTITLE     = os.getenv("ALIGO_EMTITLE", "")
