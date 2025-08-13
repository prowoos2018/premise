# tests/test_directsend.py

from services.directsend_service import DirectSendService

if __name__ == "__main__":
    svc = DirectSendService()
    targets = [{
        "name":   "테스트",
        "mobile": "01058417894",
        "note1":  "첫번째 노트",
        "note2":  "두번째 노트"
    }]
    resp = svc.send_messages(targets)
    print(resp)
