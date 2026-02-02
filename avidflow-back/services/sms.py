import requests
from typing import Optional
from config import settings


class KavenegarSMS:
    def __init__(self):
        self.api_key = settings.KAVENEGAR_API_KEY
        self.base_url = "https://api.kavenegar.com/v1"

    def send_verification(self, receptor: str, code: str) -> Optional[dict]:
        try:
            url = f"{self.base_url}/{self.api_key}/verify/lookup.json"
            data = {"receptor": receptor, "token": code, "template": "avid-register"}
            response = requests.post(url, data=data)
            return response.json()
        except Exception as e:
            # Log error
            return None
