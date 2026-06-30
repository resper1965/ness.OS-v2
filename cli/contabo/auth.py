import os
import json
import httpx
from pathlib import Path
from .schemas import TokenResponse

CREDENTIALS_FILE = Path.home() / ".contabo_credentials.json"
TOKEN_FILE = Path.home() / ".contabo_token.json"
AUTH_URL = "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"

def save_credentials(client_id: str, client_secret: str, user: str, password: str):
    CREDENTIALS_FILE.write_text(json.dumps({
        "client_id": client_id,
        "client_secret": client_secret,
        "user": user,
        "password": password
    }))

def get_credentials() -> dict:
    if not CREDENTIALS_FILE.exists():
        raise Exception("Credentials not found. Please run 'contabo auth login' first.")
    return json.loads(CREDENTIALS_FILE.read_text())

def fetch_token() -> TokenResponse:
    creds = get_credentials()
    data = {
        "grant_type": "password",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "username": creds["user"],
        "password": creds["password"]
    }
    with httpx.Client() as client:
        response = client.post(AUTH_URL, data=data)
        response.raise_for_status()
        token_data = response.json()
        TOKEN_FILE.write_text(json.dumps(token_data))
        return TokenResponse(**token_data)

def get_access_token() -> str:
    # Minimal version: re-fetch if not exists. Ideally should check expiration.
    if not TOKEN_FILE.exists():
        token = fetch_token()
        return token.access_token
    else:
        token_data = json.loads(TOKEN_FILE.read_text())
        # For simplicity, we just return it. In prod, check expiry and refresh if needed.
        return token_data.get("access_token")
