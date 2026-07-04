# -------------------------------------------------------
# n.infraops — Configuração centralizada via Pydantic Settings
# -------------------------------------------------------
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuração única da aplicação. Lê de variáveis de ambiente ou .env."""

    # --- App ---
    app_name: str = "n.infraops"
    debug: bool = False

    # --- PostgreSQL (TimescaleDB + pgvector) ---
    database_url: str = "postgresql+asyncpg://nessops:changeme@localhost:5432/nessops"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    lock_ttl_seconds: int = 10
    lock_retry_delay_seconds: int = 2

    # --- Celery ---
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Zabbix API ---
    zabbix_url: str = "https://zabbix.ness.com.br/api_jsonrpc.php"
    zabbix_api_token: str = ""

    # --- Gemini API ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- n8n (Orquestração de borda) ---
    n8n_base_url: str = "http://localhost:5678"
    n8n_webhook_incident: str = "/webhook/incident-created"
    n8n_webhook_postmortem: str = "/webhook/postmortem-ready"

    # --- DeskManager (Ticketing) ---
    deskmanager_api_url: str = "https://api.deskmanager.com.br/v2"
    deskmanager_api_token: str = ""
    deskmanager_operator_id: str = ""

    # --- Evolution API (WhatsApp — Read-Only) ---
    evolution_api_url: str = "http://localhost:8080"
    evolution_instance: str = "noc-alerts"
    evolution_api_key: str = ""
    whatsapp_noc_group_id: str = ""

    # --- RMM Providers (Multi-tenant: default credentials) ---
    datto_api_key: str = ""
    datto_api_secret: str = ""
    datto_api_url: str = "https://pinotage-api.centrastage.net"
    atera_api_key: str = ""
    atera_api_url: str = "https://app.atera.com/api/v3"

    # --- SOC / Security (RocketCyber) ---
    rocketcyber_api_key: str = ""
    rocketcyber_api_url: str = "https://api-us.rocketcyber.com"

    # --- Dashboard ---
    dashboard_base_url: str = "https://infraops.ness.com.br"

    # --- Anomaly Detection ---
    anomaly_zscore_threshold: float = 3.0
    anomaly_min_datapoints: int = 30

    model_config = {"env_prefix": "NINF_", "env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
