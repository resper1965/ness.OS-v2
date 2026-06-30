# Tasks Checklist — n.infraops

Status e progresso da implementação da plataforma n.infraops.

---

## 🏗️ Fase 1: Reorganização do Monorepo
*   [x] Mover diretórios de infraestrutura (`terraform`, `ansible`, `scripts`, `docs`) para a pasta `infra/`.
*   [x] Mover o backend (`nessops/backend`) para `app/backend/`.
*   [x] Criar arquivo de orquestração `app/docker-compose.yml` e `app/Dockerfile`.
*   [x] Criar arquivo `.env.example` unificado na pasta `app/`.
*   [x] Atualizar o `README.md` principal do monorepo e configurar o `.gitignore` unificado.

## 💾 Fase 2: Configuração e Modelos de Banco de Dados
*   [x] Adicionar dependência `pgvector` ao `requirements.txt`.
*   [x] Atualizar o schema DDL (`001_schema.sql`) para incluir a tabela `n_infraops_metrics` (TimescaleDB) e índices.
*   [x] Criar a classe `Base` e configuração de engine/session assíncronas em `database.py`.
*   [x] Mapear modelos SQLAlchemy em `models.py` para as tabelas de ativos, incidentes, relatórios pós-incidente, execuções de playbooks e métricas.
*   [x] Exportar os modelos no pacote de inicialização do módulo `models/__init__.py`.

## ⚙️ Fase 3: Integração nos Celery Workers
*   [x] Substituir stubs em `workers/tasks.py` por operações de banco reais usando SQLAlchemy assíncrono envelopado em `asyncio.run()`.
*   [x] Atualizar a task de post-mortem (`workers/postmortem.py`) para buscar métricas e incidentes similares do banco, persistindo o relatório final gerado no PostgreSQL.

## 🧪 Fase 4: Suíte de Testes Unitários
*   [x] Adicionar `pytest` e `pytest-asyncio` ao `requirements.txt`.
*   [x] Criar arquivo de testes do Sanitizer para validar o mascaramento de PII.
*   [x] Criar testes do Fingerprint para verificar o determinismo.
*   [x] Criar testes do Anomaly Detection para verificar Robust Z-Score com MAD.
*   [x] Criar testes de integração da API FastAPI mockando dependências do Redis.

## 🚀 Fase 5: Implantação e Execução de Testes
*   [x] Criar ambiente virtual local (.venv) e instalar as dependências.
*   [x] Executar `pytest tests/` no backend para validação das regras implementadas.
*   [x] Realizar push do monorepo completo para o GitHub remoto `https://github.com/resper1965/n-infraops.git`.
