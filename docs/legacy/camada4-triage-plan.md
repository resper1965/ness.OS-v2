# 🛡️ Implementação da Camada 4 — Triage Worker sem LLM (Risk Engine 0–100)

## Goal
Implementar o motor de triagem determinística sem LLM na plataforma `zabbix.ness` para calcular score de risco (0–100) e filtrar ≥95% dos eventos sem consumo de IA.

## Tasks
- [x] Task 1: Criar classe `TriageEngine` em `app/core/triage_engine.py` com cálculo de risco determinístico → Verify: Testes de cálculo de score aprovados
- [x] Task 2: Adicionar controle de deduplicação e janela de agregamento temporal no Redis em `triage_engine.py` → Verify: Eventos repetidos em <5m incrementam o risco sem duplicar requisições
- [x] Task 3: Conectar a pontuação do ativo e consultas ao módulo Threat Intel → Verify: Ativos críticos (Domain Controller/DB) aplicam peso extra no score
- [x] Task 4: Modificar o router de pipeline `app/api/routers/secops.py` para aplicar a porta de decisão (Risco < 75 = Arquiva sem IA) → Verify: Webhook com risco < 75 não consome Gemini API
- [x] Task 5: Expor métricas de % de bypass de IA no router `app/api/routers/secops.py` → Verify: Endpoint GET `/api/secops/triage-stats` retorna contadores e estatísticas de economia
- [x] Task 6: Criar suíte de testes unitários `tests/test_triage_engine.py` e `tests/test_secops_triage_api.py` → Verify: `pytest` passa 100% sem erros

## Done When
- [x] O backend filtra automaticamente alertas com risco < 75 sem acionar o Gemini.
- [x] Alertas com risco >= 75 são encaminhados para a IA com contexto enriquecido.
- [x] Suíte de testes automatizados do `TriageEngine` 100% aprovada.

## Notes
- Limiar de Risco: Risco < 75 (Arquiva), 75–84 (IA Nível 1), >= 85 (IA Nível 2 + Alerta crítico).
- Integrado com Redis para cache de frequência/deduplicação.
