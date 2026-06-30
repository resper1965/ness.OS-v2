# -------------------------------------------------------
# n.infraops — Celery App (configuração do broker)
# -------------------------------------------------------
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "n.infraops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
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
