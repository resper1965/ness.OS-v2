# -------------------------------------------------------
# n.infraops — Celery App (configuração do broker)
# -------------------------------------------------------
from celery import Celery
from celery.signals import worker_process_init

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "n.infraops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks",
        "app.workers.alerts",
        "app.workers.postmortem",
        "app.workers.telemetry",
    ],
)

celery_app.conf.update(
    # Serialização segura (JSON, não pickle)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="America/Sao_Paulo",
    enable_utc=True,
    # Filas
    task_routes={
        "app.workers.tasks.process_alert": {"queue": "alerts.primary"},
        "app.workers.tasks.process_deferred_alert": {"queue": "alerts.deferred"},
        "app.workers.alerts.process_alert_v1": {"queue": "alerts.primary"},
        "app.workers.tasks.process_ticket_resolution": {"queue": "alerts.primary"},
        "app.workers.tasks.run_anomaly_check": {"queue": "ml"},
        "app.workers.postmortem.generate_postmortem_report": {"queue": "ml"},
    },
    # Prefetch 1 task por worker (evita starvation em alertas massivos)
    worker_prefetch_multiplier=1,
    # Retry com backoff exponencial
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Limites
    task_soft_time_limit=60,
    task_time_limit=120,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.workers"])

# Garantir que o módulo de postmortem seja importado para registrar a task


# Evitar conflito de conexão com o banco de dados (TimescaleDB) após fork de workers Celery
@worker_process_init.connect
def configure_workers(sender, **kwargs):
    from app.database import engine

    try:
        engine.sync_engine.dispose()
    except Exception:
        pass
