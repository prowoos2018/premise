# infra/sheet_service.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import Config

class SheetService:
    def __init__(self):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            Config.SHEET_CREDENTIALS_PATH, scope
        )
        self.client = gspread.authorize(creds)
        self.sheet  = self.client.open_by_key(Config.REVIEW_SHEET_ID).sheet1
        self.headers = self.sheet.row_values(1)

    def fetch_reviews(self):
        # 전체 데이터를 가져와 헤더 기준으로 dict 목록 생성
        all_values = self.sheet.get_all_values()
        if not all_values or len(all_values) < 2:
            return []
        headers = all_values[0]
        data_rows = all_values[1:]
        records = []
        for row in data_rows:
            item = {}
            for idx, header in enumerate(headers):
                if header:
                    item[header] = row[idx] if idx < len(row) else ""
            records.append(item)
        return records

    def update_order_no(self, row_index: int, order_no: str):
        col = self.headers.index("order_no") + 1
        self.sheet.update_cell(row_index, col, order_no)

    def mark_complete(self, row_index: int, value: str = "Y"):
        col = self.headers.index("완료") + 1
        self.sheet.update_cell(row_index, col, value)

    def mark_admin_complete(self, row_index: int, value: str = "Y"):
        col = self.headers.index("관리자완료") + 1
        self.sheet.update_cell(row_index, col, value)

    def mark_review_complete(self, row_index: int, value: str = "Y"):
        col = self.headers.index("리뷰완료") + 1
        self.sheet.update_cell(row_index, col, value)