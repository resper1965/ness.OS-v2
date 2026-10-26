from fastapi import APIRouter, Depends

from app.core.dependencies import require_noc
from app.integrations.pipeline_health import pipeline_health

router = APIRouter()


@router.get(
    "/api/dashboard/pipeline-status",
    tags=["dashboard"],
    dependencies=[Depends(require_noc)],
)
async def get_pipeline_status():
    result = await pipeline_health()
    # Existing portal label remains compatible while the provider is GLPI.
    result["deskmanager"] = dict(result["glpi"])
    if result["glpi"]["status"] == "ok":
        result["deskmanager"]["detail"] = "GLPI: leitura autenticada verificada"
    result["whatsapp"] = {"status": "disabled", "detail": "Notificações desativadas"}
    return result
