# Contabo CLI Spec

## Arquitetura
O CLI para gerenciamento da infraestrutura na Contabo é parte integrante do projeto `n.infraops`, localizado em `cli/contabo/`. 
Foi construído utilizando **Typer**, **HTTPX**, **Pydantic**, e **Rich**.

## Estrutura de Comandos
```bash
# Autenticação e Configuração
python -m cli.contabo.main login --client-id XXX --client-secret YYY --user admin

# Gerenciamento de Instâncias (VPS)
python -m cli.contabo.main compute list
python -m cli.contabo.main compute restart <instance_id>

# Gerenciamento de Object Storage
python -m cli.contabo.main storage list

# Gerenciamento de Tags
python -m cli.contabo.main tags list
python -m cli.contabo.main tags create "Nome" --color "#HEX"
```

## Credenciais
As credenciais são guardadas localmente via OAuth2 Password Grant. O `auth.py` gerencia o ciclo de vida do token, garantindo que o `api_client.py` injete o `Bearer Token` em todas as requisições.
