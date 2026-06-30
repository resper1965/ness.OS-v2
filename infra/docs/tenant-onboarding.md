# Runbook: Integração e Onboarding de Tenants (Multi-Tenant RMM)

Este documento detalha o processo de provisionamento, gerenciamento e isolamento de credenciais de RMM (Datto e Atera) para clientes (tenants) da plataforma **n.infraops**.

---

## 1. Arquitetura de Multi-Tenancy

O isolamento lógico de clientes na plataforma se baseia em duas tabelas principais no PostgreSQL:
1. **`n_infraops_assets`**: Cada ativo (servidor, VM, firewall) cadastrado possui uma coluna `customer_id` (que identifica o cliente) e o `rmm_provider` ('datto', 'atera', ou 'none').
2. **`n_infraops_customer_credentials`**: Armazena as credenciais de acesso da API do RMM indexadas por `customer_id` e `provider`.

Quando um alerta do Zabbix chega, a plataforma:
- Localiza o ativo por `zabbix_host_id`.
- Obtém o `customer_id` e `rmm_provider` do ativo.
- Carrega as credenciais correspondentes de `n_infraops_customer_credentials`.
- Instancia o driver específico (Datto ou Atera) para executar a automação de resposta (runbook).

---

## 2. Gerenciamento de Tenants via CLI (Recomendado)

O n.infraops fornece uma interface de linha de comando (CLI) utilitária para gerenciar as credenciais sem a necessidade de comandos SQL manuais.

### Configurando o ambiente
No servidor de aplicação (dentro da pasta `app/backend/`):
```bash
# Ative o ambiente virtual
source .venv/bin/activate  # Linux
# ou
.venv\Scripts\activate     # Windows
```

### Comandos de Operação

#### A. Listar todos os tenants cadastrados
Exibe uma tabela contendo os clientes cadastrados e a URL do provedor. Por segurança, a chave da API é automaticamente mascarada.
```bash
python -m app.manage_tenants list
```

#### B. Adicionar ou atualizar credenciais de um cliente
Para cadastrar ou atualizar chaves de API:

- **Para Atera RMM** (requer apenas `--api-key`):
  ```bash
  python -m app.manage_tenants add \
      --customer-id "cliente_exemplo_atera" \
      --provider atera \
      --api-key "AT_API_KEY_XXXXXXXXXXXX"
  ```

- **Para Datto RMM** (requer `--api-key` e `--api-secret`):
  ```bash
  python -m app.manage_tenants add \
      --customer-id "cliente_exemplo_datto" \
      --provider datto \
      --api-key "DT_API_KEY_YYYYYYYYYYYY" \
      --api-secret "DT_API_SECRET_ZZZZZZZZZZZZ"
  ```

- **Parâmetros opcionais:**
  - `--api-url`: URL customizada para o endpoint da API se o cliente usar um shard geográfico diferente. Exemplo para Datto: `https://zinfandel-api.centrastage.net`. Se omitido, a plataforma usa fallbacks padrões globais.

#### C. Deletar credenciais de um cliente
Remove as chaves de API do banco de dados (o cliente deixará de ter remediações automáticas via RMM ativas):
```bash
python -m app.manage_tenants delete \
    --customer-id "cliente_exemplo_atera" \
    --provider atera
```

---

## 3. Gerenciamento manual via Banco de Dados (SQL)

Caso necessite inserir as credenciais via queries diretas no banco de dados:

### Inserir/Atualizar Credenciais
```sql
INSERT INTO n_infraops_customer_credentials (customer_id, provider, api_key, api_secret, api_url)
VALUES (
    'cliente_corp_a', 
    'datto', 
    'sua_api_key_aqui', 
    'seu_api_secret_aqui', 
    'https://pinotage-api.centrastage.net'
)
ON CONFLICT (customer_id, provider) DO UPDATE 
SET api_key = EXCLUDED.api_key,
    api_secret = EXCLUDED.api_secret,
    api_url = EXCLUDED.api_url,
    updated_at = NOW();
```

### Consultar Credenciais de um Cliente
```sql
SELECT customer_id, provider, api_url, created_at, updated_at 
FROM n_infraops_customer_credentials 
WHERE customer_id = 'cliente_corp_a';
```

---

## 4. Associação de Ativos ao Tenant

Após cadastrar as credenciais do cliente, certifique-se de que os ativos monitorados estão devidamente associados para que a automação utilize as credenciais corretas.

Ao cadastrar um ativo na tabela `n_infraops_assets`, configure:
- `customer_id` com o mesmo identificador cadastrado em `n_infraops_customer_credentials`.
- `rmm_provider` com o valor `'datto'` ou `'atera'`.
- `rmm_device_id` com o ID do dispositivo na respectiva console do RMM.

Exemplo de query de associação:
```sql
UPDATE n_infraops_assets 
SET customer_id = 'cliente_corp_a',
    rmm_provider = 'datto',
    rmm_device_id = 'DT_DEVICE_ID_12345'
WHERE hostname = 'srv-db-prod-cliente-a';
```
