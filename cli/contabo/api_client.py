import uuid

import httpx

from .auth import get_access_token

BASE_URL = "https://api.contabo.com/v1"


class ContaboAPIClient:
    def __init__(self):
        self.access_token = get_access_token()
        self.client = httpx.Client(base_url=BASE_URL)

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "x-request-id": str(uuid.uuid4()),
        }

    def get(self, endpoint: str, params: dict | None = None):
        response = self.client.get(endpoint, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, json_data: dict | None = None):
        response = self.client.post(
            endpoint, headers=self._get_headers(), json=json_data
        )
        response.raise_for_status()
        return response.json()

    def patch(self, endpoint: str, json_data: dict | None = None):
        response = self.client.patch(
            endpoint, headers=self._get_headers(), json=json_data
        )
        response.raise_for_status()
        return response.json()

    def delete(self, endpoint: str):
        response = self.client.delete(endpoint, headers=self._get_headers())
        response.raise_for_status()
        return True  # Delete returns 204 mostly
