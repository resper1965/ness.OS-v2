import logging
import httpx
from typing import Any, Dict, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)

class WhatsAppClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        instance: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.evolution_api_url).rstrip("/")
        self.instance = instance or settings.evolution_instance
        self.api_key = api_key or settings.evolution_api_key

    async def send_text_message(self, recipient: str, text: str) -> Dict[str, Any]:
        """Dispara uma mensagem de texto simples via Evolution API.
        
        `recipient` pode ser um número de telefone com DDI (ex: '5511999999999')
        ou um ID de grupo do WhatsApp (ex: '120363298457293847@g.us').
        """
        url = f"{self.base_url}/message/sendText/{self.instance}"
        headers = {
            "Content-Type": "application/json",
            "apikey": self.api_key
        }
        payload = {
            "number": recipient,
            "text": text,
            "delay": 1200,
            "linkPreview": True
        }
        
        logger.info("Enviando mensagem de WhatsApp para %s via Evolution API...", recipient)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                logger.info("Mensagem de WhatsApp enviada com sucesso para %s.", recipient)
                return data
        except Exception as e:
            logger.error("Erro ao enviar mensagem de WhatsApp via Evolution API: %s", str(e))
            raise RuntimeError(f"Erro ao enviar WhatsApp: {e}") from e
