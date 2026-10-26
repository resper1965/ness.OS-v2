# -------------------------------------------------------
# n.infraops — Configuração centralizada via Pydantic Settings
# -------------------------------------------------------
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração única da aplicação. Lê de variáveis de ambiente ou .env."""

    # --- App ---
    app_name: str = "n.infraops"
    debug: bool = False

    # --- PostgreSQL (TimescaleDB + pgvector) ---
    database_url: str = "postgresql+asyncpg://nessops@localhost:5432/nessops"

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
    zabbix_verify_cert: bool = True

    # --- Gemini API ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- n8n (Orquestração de borda) ---
    n8n_base_url: str = "http://localhost:5678"
    n8n_webhook_incident: str = "/webhook/incident-created"
    n8n_webhook_postmortem: str = "/webhook/postmortem-ready"
    n8n_webhook_soc: str = "/webhook/soc-triage"
    n8n_webhook_api_key: str = ""

    # --- E-mail transacional (Resend HTTP API) ---
    transactional_email_enabled: bool = False
    transactional_email_from: str = "ness.OS Hub <hub@ness.com.br>"
    resend_api_key: str = ""
    resend_api_url: str = "https://api.resend.com"
    email_timeout_seconds: float = 10.0
    email_max_attempts: int = 3

    # --- Webhooks ---
    webhook_api_key: str = ""

    # --- DeskManager (Ticketing) ---
    deskmanager_api_url: str = "https://api.deskmanager.com.br/v2"
    deskmanager_api_token: str = ""
    deskmanager_operator_id: str = ""

    # --- GLPI (Ticketing) ---
    glpi_url: str = "http://ninf-glpi/apirest.php"
    glpi_app_token: str = ""
    glpi_user_token: str = ""
    glpi_infra_category_id: int = 0
    glpi_security_category_id: int = 0

    # --- Evolution API (WhatsApp — Read-Only) ---
    evolution_api_url: str = "http://localhost:8080"
    evolution_instance: str = "noc-alerts"
    evolution_api_key: str = ""
    whatsapp_noc_group_id: str = ""
    # Only controls WhatsApp and Web Push emitted by the v1 alert worker.
    alert_notifications_enabled: bool = False

    # --- RMM Providers (Multi-tenant: default credentials) ---
    datto_api_key: str = ""
    datto_api_secret: str = ""
    datto_api_url: str = "https://pinotage-api.centrastage.net"
    atera_api_key: str = ""
    atera_api_url: str = "https://app.atera.com/api/v3"

    # --- SOC / Security (Wazuh, VirusTotal, AbuseIPDB, MISP) ---
    virustotal_api_key: str = ""
    abuseipdb_api_key: str = ""
    misp_url: str = "https://misp.ness.com.br"
    misp_api_key: str = ""
    misp_verify_cert: bool = False

    # --- Dashboard ---
    dashboard_base_url: str = "https://hub.ness.com.br"

    # --- Grafana Loki (SIEM) ---
    loki_url: str = ""

    # --- JWT Authentication (FASE 4.1) ---
    jwt_secret: str = ""  # NINF_JWT_SECRET — deixe vazio para fallback automático
    jwt_expire_hours: int = 8  # NINF_JWT_EXPIRE_HOURS
    session_cookie_secure: bool = True

    # --- Anomaly Detection ---
    anomaly_zscore_threshold: float = 3.0
    anomaly_min_datapoints: int = 30

    # --- Web Push Notifications (PWA VAPID) ---
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claims_email: str = "ops@ness.com.br"

    # --- Authentik OIDC (SSO) ---
    oidc_enabled: bool = False
    oidc_jwks_url: str = "https://sso.ness.com.br/application/o/nessops/jwks/"
    oidc_token_url: str = "https://sso.ness.com.br/application/o/token/"
    oidc_client_id: str = "nessops-client-id"
    oidc_client_secret: str = ""
    oidc_issuer: str = "https://sso.ness.com.br/application/o/nessops/"

    @model_validator(mode="after")
    def load_vapid_keys(self) -> "Settings":
        if not self.vapid_public_key or not self.vapid_private_key:
            try:
                from app.core.vapid import get_or_create_vapid_keys

                pub, priv = get_or_create_vapid_keys()
                if not self.vapid_public_key:
                    self.vapid_public_key = pub
                if not self.vapid_private_key:
                    self.vapid_private_key = priv
            except Exception:
                pass
        return self

    model_config = SettingsConfigDict(
        env_prefix="NINF_", env_file=".env", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
