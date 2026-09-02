# Guia de Implantação — n.infraops (Stack Completa)

Este documento descreve os passos para implantar a stack completa do **n.infraops** (API, PostgreSQL, Redis, Celery Workers e n8n) em produção na VPS Contabo dedicada utilizando o Docker Compose.

---

## Pré-requisitos no Servidor Alvo

Antes de iniciar, garanta que o servidor possui os seguintes requisitos instalados:
- **Docker Engine** (v24.0.0 ou superior)
- **Docker Compose Plugin** (v2.20.0 ou superior)
- **Git** (para clonar o repositório ou transferir o código)

> O playbook `infra/ansible/playbooks/site.yml` é exclusivo da VPS Zabbix e não instala Docker no Hub. O script `app/setup_hub.sh` faz o hardening básico e cria `/opt/n-infraops`, mas a instalação do Docker deve ser realizada separadamente e validada com `docker version` e `docker compose version`.

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
   - `NINF_AUTHENTIK_SECRET_KEY`: Segredo criptograficamente aleatório do Authentik.
   - `NINF_GLPI_DB_ROOT_PASSWORD` e `NINF_GLPI_DB_PASSWORD`: Credenciais exclusivas do MariaDB/GLPI.
   - `NINF_DASHBOARD_BASE_URL=https://hub.ness.com.br`: origem autorizada para mutações da sessão do Hub.
   - `NINF_SESSION_COOKIE_SECURE=true`: obrigatório em produção; use `false` somente no desenvolvimento local sem HTTPS.

   Não dependa de valores padrão presentes nos arquivos Compose. Em produção, todas as variáveis de segredo devem estar explicitamente definidas e armazenadas fora do Git.

---

## Passo 3: Inicialização e Build da Stack

1. Execute o comando para construir as imagens customizadas (API Backend e Celery Workers) e iniciar todos os serviços em segundo plano:
   ```bash
   docker compose \
     -f docker-compose.yml \
     -f docker-compose.tickets.yml \
     up -d --build
   ```

2. Verifique se todos os containers subiram com sucesso e estão rodando:
   ```bash
   docker compose \
     -f docker-compose.yml \
     -f docker-compose.tickets.yml \
     ps
   ```

   Você deve ver 14 contêineres ativos:
   - `ninf-postgres` (PostgreSQL + TimescaleDB + pgvector)
   - `ninf-redis` (Cache e filas de processamento)
   - `ninf-api` (API FastAPI)
   - `ninf-worker-alerts` (Fila Celery de alertas rápidos)
   - `ninf-worker-ml` (Fila Celery de ML e Post-Mortem)
   - `ninf-n8n` (Workflow Engine)
   - `ninf-frontend` (Dashboard React/Vite)
   - `ninf-caddy` (Proxy reverso e TLS)
   - `ninf-authentik-server` (SSO/IdP)
   - `ninf-authentik-worker` (Worker do Authentik)
   - `ninf-evolution` (Evolution API/WhatsApp)
   - `ninf-evolution-manager` (Gerenciador da Evolution API)
   - `ninf-glpi` (GLPI/Service Desk)
   - `ninf-glpi-db` (MariaDB exclusivo do GLPI)

---

## Passo 4: Verificação da API e Saúde

Antes do deploy, execute o gate estático, que não abre conexões de rede:

```bash
bash infra/scripts/hub-session-readiness.sh
```

Após o deploy, o facilitador pode executar a prova contida com uma conta UAT
descartável. As variáveis devem ser injetadas pelo cofre/runner, com `set +x`; não
digite a senha na linha de comando e não preserve o diretório temporário do script:

```bash
HUB_SESSION_EXECUTE=1 \
  bash infra/scripts/hub-session-readiness.sh --execute-contained
```

O gate confirma login por cookie, atributos seguros, `/me`, SSE sem token na URL,
logout e rejeição da sessão encerrada. Ele não cria objetos operacionais nem acessa
Zabbix, GLPI ou KVM8.

1. Faça uma requisição para o endpoint de health check da API:
   ```bash
   docker exec ninf-api python -c \
     "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/webhook/health').read().decode())"
   ```
   A resposta deve ser:
   `{"status": "healthy", "service": "webhook-receiver"}`

2. Acesse a documentação Swagger interativa pelo domínio protegido:
   `https://api.ness.com.br/docs`. Um retorno `401` sem autenticação é esperado quando a proteção do Caddy está habilitada.

---

## Passo 5: Gerenciamento dos Containers

### Parar a Stack
```bash
docker compose -f docker-compose.yml -f docker-compose.tickets.yml down
```

### Reiniciar Serviços Específicos
Caso faça uma alteração de código ou configuração:
```bash
docker compose -f docker-compose.yml -f docker-compose.tickets.yml restart api worker-alerts worker-ml
```

### Visualizar Logs em Tempo Real
```bash
# Todos os logs
docker compose -f docker-compose.yml -f docker-compose.tickets.yml logs -f

# Logs apenas do processamento de alertas
docker compose -f docker-compose.yml -f docker-compose.tickets.yml logs -f worker-alerts
```

---

## Passo 6: Configuração de Backup das Implantações (Volumes)

Os dados estão persistidos nos seguintes volumes Docker gerenciados:
- `pg-data`: Armazena o banco de dados PostgreSQL.
- `redis-data`: Dados em cache do Redis.
- `n8n-data`: Bancos e fluxos do n8n.
- `authentik-media`, `authentik-templates` e `authentik-certs`: Dados do Authentik.
- `evolution-instances` e `evolution-store`: Instâncias e estado da Evolution API.
- `glpi-data` e `glpi-db-data`: Aplicação e banco do GLPI.

O backup do Hub deve ser tratado separadamente do runbook do Zabbix. É obrigatório incluir dumps consistentes do PostgreSQL e MariaDB, além dos volumes persistentes, armazená-los fora da VPS e testar periodicamente a restauração. Copiar `/var/lib/docker/volumes` enquanto os bancos estão gravando não constitui, sozinho, um backup consistente.

O estado real observado das duas VPS está registrado em [`as-built-vps.md`](as-built-vps.md).
