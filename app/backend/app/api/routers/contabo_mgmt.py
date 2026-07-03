"""
n.infraops — Contabo API Router
Endpoints para gerenciamento de Firewall e Instâncias via HITL.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import os

from app.integrations.contabo_firewall import (
    ContaboTokenManager,
    ContaboFirewallClient,
    ContaboInstanceClient,
)

router = APIRouter()


def get_token_manager() -> ContaboTokenManager:
    return ContaboTokenManager(
        client_id=os.getenv("CONTABO_CLIENT_ID", ""),
        client_secret=os.getenv("CONTABO_CLIENT_SECRET", ""),
        username=os.getenv("CONTABO_USERNAME", ""),
        password=os.getenv("CONTABO_PASSWORD", ""),
    )


# -------------------------------------------------------
# FIREWALL ENDPOINTS
# -------------------------------------------------------

@router.get("/firewalls")
async def list_firewalls():
    """Lista todos os firewalls da conta Contabo."""
    try:
        client = ContaboFirewallClient(get_token_manager())
        return await client.list_firewalls()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


@router.get("/firewalls/{firewall_id}")
async def get_firewall(firewall_id: str):
    """Retorna detalhes e regras de um firewall específico."""
    try:
        client = ContaboFirewallClient(get_token_manager())
        return await client.get_firewall(firewall_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


class BlockIpRequest(BaseModel):
    ip_cidr: str          # ex: "192.168.1.1/32"
    approved_by: str      # ID do usuário que autorizou (HITL)


@router.post("/firewalls/{firewall_id}/block-ip")
async def block_ip(firewall_id: str, body: BlockIpRequest):
    """
    [HITL] Adiciona regra de bloqueio de IP no firewall da Contabo.
    Requer aprovação explícita (approved_by).
    """
    if not body.approved_by:
        raise HTTPException(status_code=403, detail="HITL: approved_by é obrigatório.")
    try:
        client = ContaboFirewallClient(get_token_manager())
        return await client.block_ip(firewall_id, body.ip_cidr, body.approved_by)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


class OpenPortRequest(BaseModel):
    port: int
    source_ip: str        # ex: "177.100.200.5/32"
    approved_by: str


@router.post("/firewalls/{firewall_id}/open-port")
async def open_port(firewall_id: str, body: OpenPortRequest):
    """
    [HITL] Abre uma porta temporariamente para um IP específico.
    Útil para janelas de manutenção controladas.
    """
    if not body.approved_by:
        raise HTTPException(status_code=403, detail="HITL: approved_by é obrigatório.")
    try:
        client = ContaboFirewallClient(get_token_manager())
        return await client.open_port_temporarily(firewall_id, body.port, body.source_ip, body.approved_by)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


# -------------------------------------------------------
# INSTANCE ENDPOINTS
# -------------------------------------------------------

@router.get("/instances")
async def list_instances():
    """Lista todas as instâncias VPS/VDS da Contabo."""
    try:
        client = ContaboInstanceClient(get_token_manager())
        return await client.list_instances()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str):
    """Retorna detalhes de uma instância específica."""
    try:
        client = ContaboInstanceClient(get_token_manager())
        return await client.get_instance(instance_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


class ActionRequest(BaseModel):
    approved_by: str


@router.post("/instances/{instance_id}/restart")
async def restart_instance(instance_id: str, body: ActionRequest):
    """[HITL] Reinicia uma instância de VPS. Requer aprovação."""
    if not body.approved_by:
        raise HTTPException(status_code=403, detail="HITL: approved_by é obrigatório.")
    try:
        # Cria snapshot de segurança antes de reiniciar
        ic = ContaboInstanceClient(get_token_manager())
        await ic.create_snapshot(
            instance_id,
            name=f"pre-restart-hitl",
            description=f"Auto-snapshot antes de restart HITL. Aprovado por: {body.approved_by}"
        )
        return await ic.restart_instance(instance_id, body.approved_by)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


@router.post("/instances/{instance_id}/stop")
async def stop_instance(instance_id: str, body: ActionRequest):
    """[HITL] Desliga uma instância. Requer aprovação explícita."""
    if not body.approved_by:
        raise HTTPException(status_code=403, detail="HITL: approved_by é obrigatório.")
    try:
        client = ContaboInstanceClient(get_token_manager())
        return await client.stop_instance(instance_id, body.approved_by)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")


@router.post("/instances/{instance_id}/snapshot")
async def create_snapshot(instance_id: str, name: str, description: str = ""):
    """Cria um snapshot de segurança de uma instância."""
    try:
        client = ContaboInstanceClient(get_token_manager())
        return await client.create_snapshot(instance_id, name, description)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Contabo API Error: {e}")
