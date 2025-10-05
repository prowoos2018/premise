from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import urllib.parse, sys, json

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
cred_in = "/home/prewoos2018/premise/secrets/credentials.json"
tok_out = "/home/prewoos2018/premise/secrets/gmail_token.json"

# 클라이언트 로드
flow = InstalledAppFlow.from_client_secrets_file(cred_in, SCOPES)

# credentials.json 안의 첫 번째 redirect_uri 사용 (네 파일엔 http://localhost)
with open(cred_in) as f:
    cfg = json.load(f)
redirect_uri = cfg["installed"]["redirect_uris"][0]
flow.redirect_uri = redirect_uri  # ← 중요!

# 동의 URL 생성
auth_url, _ = flow.authorization_url(
    prompt="consent",
    access_type="offline",
    include_granted_scopes="true",
)

print("\n1) 이 URL을 브라우저에서 열어 로그인/동의하세요:\n", auth_url, "\n")
redir = input("2) 동의 후 'http://localhost/?code=...' 로 리다이렉트되면, 주소창 **전체 URL**을 복사해서 여기에 붙여넣으세요:\n").strip()

qs = urllib.parse.urlparse(redir).query
code = urllib.parse.parse_qs(qs).get("code", [None])[0]
if not code:
    sys.exit("URL에 code= 파라미터가 없습니다. 주소창 '전체 URL'을 그대로 붙여넣었는지 확인하세요.")

# 토큰 교환
flow.fetch_token(code=code)
creds = flow.credentials
Path(tok_out).parent.mkdir(parents=True, exist_ok=True)
Path(tok_out).write_text(creds.to_json())
print("Saved:", tok_out)
