# Planejamento do Fluxo do SOC (Wazuh SOC Workflow)

## Goal
Implementar o fluxo de triagem automatizada de alertas de segurança do Wazuh diretamente no AIOps Hub (sem Shuffle SOAR), integrando com enriquecimento de APIs, tomada de decisão por IA (Gemini), notificações no WhatsApp (Evolution API) e abertura de chamados no GLPI.

## Tasks
- [x] Task 1: Decidir sobre o uso do Shuffle SOAR → Verify: Decidido seguir sem Shuffle, integrando diretamente no FastAPI
- [/] Task 2: Implementar a lógica de enriquecimento automático de alertas (VirusTotal / AbuseIPDB) no backend → Verify: Dados buscados em background
- [ ] Task 3: Integrar a tomada de decisão estruturada por IA (Gemini) a partir do alerta enriquecido → Verify: Retorno da triagem formatado
- [ ] Task 4: Criar funções de notificação para WhatsApp (Evolution API) para alertas HIGH/CRIT → Verify: Mensagens de texto enviadas com sucesso
- [ ] Task 5: Implementar abertura automática de chamados de segurança no GLPI → Verify: Chamado aberto na fila do SOC

## Done When
- [ ] O fluxo Wazuh -> FastAPI -> Enriquecimento -> Gemini -> WhatsApp/GLPI funciona fim-a-fim.
- [ ] Verificação de sintaxe e testes do backend aprovados.
