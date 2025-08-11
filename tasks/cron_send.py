"""
터미널 또는 cron 스케줄러에서 직접 실행용 스크립트
$ python tasks/cron_send.py
"""
from app import create_app
from services.sheet_service import SheetService
from services.alimtalk_service import AlimtalkService

app = create_app()
app.app_context().push()

def main():
    sheet_svc = SheetService()
    alim_svc  = AlimtalkService()

    rows = sheet_svc.fetch_all()
    send_list, updates = [], []
    for idx, row in enumerate(rows, start=2):
        # routes/alerts.py와 동일한 로직
        # …
        pass

    if send_list:
        result = alim_svc.send(send_list)
        # 업데이트 및 로깅
        sheet_svc.batch_update(updates)
        print(f"Sent {len(send_list)} messages:", result)
    else:
        print("No targets to send.")

if __name__ == "__main__":
    main()
