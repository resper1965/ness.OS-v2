# Guia de Implantação — n.infraops (Stack Completa)

Este documento descreve os passos para implantar a stack completa do **n.infraops** (API, PostgreSQL, Redis, Celery Workers e n8n) em produção na VPS Contabo dedicada utilizando o Docker Compose.

---

## Pré-requisitos no Servidor Alvo

Antes de iniciar, garanta que o servidor possui os seguintes requisitos instalados (isso pode ser provisionado via Ansible no playbook `site.yml`):
- **Docker Engine** (v24.0.0 ou superior)
- **Docker Compose Plugin** (v2.20.0 ou superior)
- **Git** (para clonar o repositório ou transferir o código)

---

## Passo 1: Preparar o Diretório da Aplicação

1. Crie o diretório base para a plataforma no servidor:
   ```bash
   sudo mkdir -p /opt/n-infraops
   sudo chown -R ness_admin:ness_admin /opt/n-infraops
   cd /opt/n-infraops
   ```

2. Transfira a pasta `app/` do monorepo para este diretório. Você pode clonar o repositório diretamente se configuradas as chaves de deploy do GitHub:
   ```bash
   git clone git@github.com:resper1965/n-infraops.git .
   cd app/
   ```

---

## Passo 2: Configurar as Variáveis de Ambiente

1. Copie o arquivo `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edite o `.env` e configure todas as credenciais necessárias:
   ```bash
   nano .env
   ```

   **Configurações Importantes:**
   - `NINF_DB_PASSWORD`: Defina uma senha forte para o PostgreSQL.
   - `NINF_ZABBIX_API_TOKEN`: Token de API gerado no Zabbix 7.0 LTS.
   - `NINF_GEMINI_API_KEY`: Sua chave de acesso para a API do Gemini.
   - `NINF_N8N_PASSWORD`: Defina uma senha segura para o acesso ao n8n.
   - `NINF_DESKMANAGER_API_TOKEN` e `NINF_DESKMANAGER_OPERATOR_ID`: Credenciais de ticketing.
   - `NINF_EVOLUTION_API_KEY` e `NINF_WHATSAPP_NOC_GROUP_ID`: Credenciais do WhatsApp.

---

## Passo 3: Inicialização e Build da Stack

1. Execute o comando para construir as imagens customizadas (API Backend e Celery Workers) e iniciar todos os serviços em segundo plano:
   ```bash
   docker compose up -d --build
   ```

2. Verifique se todos os containers subiram com sucesso e estão rodando:
   ```bash
   docker compose ps
   ```

   Você deve ver 6 containers ativos:
   - `ninf-postgres` (PostgreSQL + TimescaleDB + pgvector)
   - `ninf-redis` (Cache e filas de processamento)
   - `ninf-api` (API FastAPI)
   - `ninf-worker-alerts` (Fila Celery de alertas rápidos)
   - `ninf-worker-ml` (Fila Celery de ML e Post-Mortem)
   - `ninf-n8n` (Workflow Engine)

---

## Passo 4: Verificação da API e Saúde

1. Faça uma requisição para o endpoint de health check da API:
   ```bash
   curl -f http://localhost:8000/webhook/health
   ```
   A resposta deve ser:
   `{"status": "healthy", "service": "webhook-receiver"}`

2. Acesse a documentação Swagger interativa:
   Abra no seu navegador: `http://<IP_DA_VPS_CONTABO>:8000/docs`

---

## Passo 5: Gerenciamento dos Containers

### Parar a Stack
```bash
docker compose down
```

### Reiniciar Serviços Específicos
Caso faça uma alteração de código ou configuração:
```bash
docker compose restart api worker-alerts worker-ml
```

### Visualizar Logs em Tempo Real
```bash
# Todos os logs
docker compose logs -f

# Logs apenas do processamento de alertas
docker compose logs -f worker-alerts
```

---

## Passo 6: Configuração de Backup das Implantações (Volumes)

Os dados estão persistidos nos seguintes volumes Docker gerenciados:
- `pg-data`: Armazena o banco de dados PostgreSQL.
- `redis-data`: Dados em cache do Redis.
- `n8n-data`: Bancos e fluxos do n8n.

Para realizar backups dos volumes, consulte a seção de backups no runbook operacional do Zabbix ou utilize ferramentas como o Restic/Duplicity apontando para `/var/lib/docker/volumes/`.
