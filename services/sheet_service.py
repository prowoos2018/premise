# services/sheet_service.py

from infra.google_client import get_sheets_service
from config import Config

class SheetService:
    def __init__(self):
        self.sheet = get_sheets_service()
        self.spread_id = Config.SHEET_ID

    def fetch_all(self, tab="통합시트"):
        """A2:O 끝까지 읽어서 2차원 리스트 반환"""
        resp = self.sheet.values().get(
            spreadsheetId=self.spread_id,
            range=f"{tab}!A2:O"
        ).execute()
        return resp.get("values", [])

    def batch_update(self, updates, tab="통합시트", col="C"):
        """
        updates: [{'row': int, 'value': str}, ...]
        col: 업데이트할 컬럼 (여기선 발송여부가 C열)
        """
        data = []
        for u in updates:
            data.append({
                "range": f"{tab}!{col}{u['row']}",
                "values": [[u["value"]]]
            })
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": data
        }
        return self.sheet.values().batchUpdate(
            spreadsheetId=self.spread_id,
            body=body
        ).execute()
