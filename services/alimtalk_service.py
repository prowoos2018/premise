from infra.sens_client import send_alimtalk_batch

class AlimtalkService:
    def send(self, targets):
        """
        targets: [{'to': str, 'vars': dict}, ...]
        """
        # SENS는 한 번에 최대 100건
        result = send_alimtalk_batch(targets[:100])
        return result
