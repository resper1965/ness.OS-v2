# Plan-001: Backend Core, Database, and Testing — n.infraops

## 1. Objetivo
Este plano descreve a implementação da persistência de dados no PostgreSQL (estendido com TimescaleDB e pgvector), a remoção de stubs temporários nos workers do Celery (alert processing e post-mortem generation), e a criação do ecossistema de testes unitários e de integração.

---

## 2. Mudanças Propostas

### 2.1. Camada de Persistência (SQLAlchemy Async)
*   **Database Config:** Criação de [database.py](file:///w:/home/resper/zabbix.ness/app/backend/app/database.py) para gerenciar o engine assíncrono e a injeção de dependência `get_db`.
*   **Models:** Definição em [models.py](file:///w:/home/resper/zabbix.ness/app/backend/app/models/models.py) contendo as tabelas:
    *   `n_infraops_assets` (Ativos multi-RMM/SSH)
    *   `n_infraops_incidents` (Incidentes agregados)
    *   `n_infraops_incident_reports` (Post-mortems gerados por IA com campo `embedding vector(768)`)
    *   `n_infraops_playbook_executions` (Logs de auditoria e execuções de playbooks)
    *   `n_infraops_metrics` (Série temporal para métricas de hosts)

### 2.2. Integração nos Celery Workers
*   **Tasks (Alert Processing):** Substituição de stubs `_upsert_incident` e `_increment_incident` por queries SQLAlchemy executadas de forma assíncrona usando `asyncio.run()` dentro das tasks síncronas do Celery.
*   **Post-Mortem Worker:**
    *   Busca de métricas agregadas no TimescaleDB via raw SQL `time_bucket`.
    *   Busca semântica de incidentes similares via pgvector ordenando por distância de cosseno (`<=>`).
    *   Gravação real do relatório gerado na tabela `n_infraops_incident_reports`.

### 2.3. Ecossistema de Testes (Pytest)
Criação de um diretório de testes [tests/](file:///w:/home/resper/zabbix.ness/app/backend/tests/) mockando o Redis e o banco de dados para garantir portabilidade e isolamento:
*   [test_sanitizer.py](file:///w:/home/resper/zabbix.ness/app/backend/tests/test_sanitizer.py): Valida as expressões regulares de limpeza de dados sensíveis (IPs, chaves de AWS, senhas).
*   [test_fingerprint.py](file:///w:/home/resper/zabbix.ness/app/backend/tests/test_fingerprint.py): Valida a geração determinística de hashes SHA-256 de alertas.
*   [test_anomaly.py](file:///w:/home/resper/zabbix.ness/app/backend/tests/test_anomaly.py): Valida o cálculo matemático do Robust Z-Score com MAD.
*   [test_api.py](file:///w:/home/resper/zabbix.ness/app/backend/tests/test_api.py): Valida os endpoints FastAPI de recepção de webhooks utilizando `FastAPI TestClient` e mocks do Celery/Redis.

---

## 3. Plano de Validação
*   **Testes Automatizados:** Instalação das dependências de teste e execução com `pytest tests/`.
*   **Verificação de Lint & Tipagem:** Execução do Ruff e MyPy via GitHub Actions configurado em `.github/workflows/lint.yml`.
