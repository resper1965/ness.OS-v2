# -------------------------------------------------------
# n.infraops — Utilitário de Chaves VAPID (Web Push)
# -------------------------------------------------------
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

logger = logging.getLogger("nessops.vapid")

KEYS_FILE = (
    Path("/app/vapid_keys.json")
    if Path("/app").exists()
    else Path(__file__).resolve().parent.parent.parent / "vapid_keys.json"
)


def generate_vapid_keys() -> dict[str, str]:
    """Gera um par de chaves VAPID P-256 (ECDSA) compatível com RFC 8292."""
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Chave Privada em formato PEM para o pywebpush
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # Chave Pública uncompressed em Base64 URL-safe (sem padding) para o navegador/frontend
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(public_bytes).decode("utf-8").rstrip("=")

    return {"private_key": private_pem, "public_key": public_b64}


def get_or_create_vapid_keys() -> tuple[str, str]:
    """Retorna as chaves VAPID salvas ou gera novas e as persiste no arquivo."""
    # 1. Tentar ler do ambiente/configurações prioritariamente
    env_public = os.environ.get("NINF_VAPID_PUBLIC_KEY")
    env_private = os.environ.get("NINF_VAPID_PRIVATE_KEY")

    if env_public and env_private:
        logger.info("Chaves VAPID carregadas das variáveis de ambiente.")
        return env_public, env_private

    # 2. Tentar ler do arquivo persistente
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, "r") as f:
                data = json.load(f)
                pub = data.get("public_key")
                priv = data.get("private_key")
                if pub and priv:
                    logger.info(
                        f"Chaves VAPID carregadas do arquivo persistente: {KEYS_FILE}"
                    )
                    return pub, priv
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de chaves VAPID {KEYS_FILE}: {e}")

    # 3. Gerar novas chaves
    logger.info("Chaves VAPID não encontradas. Gerando novo par persistente...")
    try:
        keys = generate_vapid_keys()

        # Tentar salvar no arquivo para persistência
        KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(KEYS_FILE, "w") as f:
            json.dump(keys, f, indent=4)

        logger.info(f"Novas chaves VAPID salvas com sucesso em: {KEYS_FILE}")
        return keys["public_key"], keys["private_key"]
    except Exception as e:
        logger.error(
            f"Falha ao persistir chaves VAPID: {e}. Gerando chaves temporárias em memória."
        )
        temp_keys = generate_vapid_keys()
        return temp_keys["public_key"], temp_keys["private_key"]
