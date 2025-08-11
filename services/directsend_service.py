# services/directsend_service.py

from infra.directsend_client import send_kakao_notice

class DirectSendService:
    def send_messages(self, targets):
        """
        targets: [
          {'name':str,'mobile':str,'note1':...,'note2':...},
          ...
        ]
        """
        # 최대 100건씩 배치 처리
        results = []
        for i in range(0, len(targets), 100):
            batch = targets[i:i+100]
            result = send_kakao_notice(batch)
            results.append(result)
        return results
