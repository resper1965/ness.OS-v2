# Auditoria de conclusão integral — 08/09/2026

Objetivo ativo: executar até que todas as tarefas estejam prontas.
Esta matriz preserva os requisitos do programa F1–F7 e P. A entrega hub/GLPI
não encerra automaticamente o programa. Evidência ausente permanece aberta.

| Requisito | Trabalho original | Estado | Evidência / próxima ação |
| --- | --- | --- | --- |
| F1-1 | concluir a primeira coleta do FortiGate interno `172.29.0.254` e do switch Aruba pelo proxy Cavan | Parcial | FortiGate interno identificado e coletando. Aruba sem SNMP e ICMP com perda total na amostra. cavan-monitoring-recheck-2026-09-08.md. |
| F1-2 | identificar o modelo do Aruba e selecionar template compatível | Aberto | Inspecionar estado atual e provar critério completo. |
| F1-3 | separar o host único do firewall dos testes de conectividade AmericaNet e Vivo, mantendo histórico e rollback | Parcial | Firewall canônico coleta; cada host WAN ainda possui 331 itens habilitados do FortiGate completo. Remodelagem pendente. |
| F1-4 | tratar fila, itens não suportados e idade da última coleta por causa | Aberto | Inspecionar estado atual e provar critério completo. |
| F1-5 | fechar tags, localização, owner, função e criticidade dos 14 ativos Cavan | Parcial | Escopo atual contém 19 hosts; owner/função/tenant/site presentes, criticidade não registrada e localização incompleta. Preservar os ativos novos. cavan-monitoring-recheck-2026-09-08.md. |
| F1-6 | validar dashboard técnico, mapa, disponibilidade e problemas atuais | Aberto | Inspecionar estado atual e provar critério completo. |
| F1-7 | executar alerta sintético sem canais reais e testar recuperação | Aberto | Inspecionar estado atual e provar critério completo. |
| F1-8 | só então preparar reativação controlada de ações e mídias. | Aberto | Inspecionar estado atual e provar critério completo. |
| F2-1 | homologar Authentik em Zabbix, GLPI, hub e ferramentas administrativas | Aberto | Inspecionar estado atual e provar critério completo. |
| F2-2 | testar login, logout, MFA, expiração, revogação, usuário desativado e break-glass por aplicação | Aberto | Inspecionar estado atual e provar critério completo. |
| F2-3 | concluir o Psono funcional: usuários, troca de senha, MFA, recuperação, SMTP, backup e restore | Parcial | Backup remoto, base e aplicação restaurados; recuperação/MFA dos responsáveis pendentes. recovery-verification-2026-09-08.md. |
| F2-4 | definir dois responsáveis de recuperação e guardar códigos de emergência fora do ambiente principal | Parcial | resper/iaraujo já cadastrados; códigos de recuperação/emergência ausentes. |
| F2-5 | migrar segredos por consumidor, validar e revogar o segredo anterior | Aberto | Inspecionar estado atual e provar critério completo. |
| F2-6 | manter RBAC e segregação de tenant no backend, não apenas na interface. | Aberto | Inspecionar estado atual e provar critério completo. |
| F3-1 | tornar a API de máquina do GLPI funcional sem contornar autorização | Aberto | Inspecionar estado atual e provar critério completo. |
| F3-2 | aplicar entidades, perfis, catálogo, SLAs, projetos, tarefas e runbooks | Parcial | 29 categorias existentes; projeto interno 1, oito tarefas e cinco runbooks implantados e isolados por entidade. Oito SLAs sem unidade calculam duração zero; fonte contratual solicitada. glpi-operating-foundation-2026-09-08.md. |
| F3-3 | carregar o inventário Cavan e reconciliar com hosts do Zabbix | Parcial | Três VMs migradas para Computer 105–107, histórico 120–122 preservado; Assets 190–192 mantidos. Replay sem duplicação, API e hub verificados; 255 ativos reconciliados. Restam consolidação do firewall e aceite integral do inventário. cavan-vm-classification-migration-2026-09-08.md. |
| F3-4 | ativar GLPI Agent somente no piloto | Aberto | Inspecionar estado atual e provar critério completo. |
| F3-5 | relacionar ativo, local, serviço, owner, contrato e criticidade | Aberto | Inspecionar estado atual e provar critério completo. |
| F3-6 | provar abertura, atribuição, atualização e encerramento de ticket. | Aberto | Inspecionar estado atual e provar critério completo. |
| F4-1 | validar PostgreSQL, Redis, migrations, API, Celery e frontend | Parcial | Hub restaurado em Docker limpo: PostgreSQL, Redis, API, frontend e dois workers aprovados. Histórico/reprodução integral de migrations ainda exige aceite. recovery-verification-2026-09-08.md. |
| F4-2 | tornar healthchecks fail-closed e medir latência, erros e filas | Parcial | Monitor hub/GLPI valida retorno explícito, mede duração, aplica deadlines e registra histórico diário com resumo p50/p95 e amostras em falha. Saída vazia/antiga não vira sucesso. Falhas GLPI/Redis e timeout verificados. Restam demais healthchecks e observação longitudinal. hub-health-failure-verification-2026-09-08.md; hub-health-history-2026-09-08.md. |
| F4-3 | corrigir credenciais e contratos Zabbix -> hub e GLPI -> hub | Evidência disponível; conferir no aceite final | hub-glpi-work-plan-2026-09-08.md; fluxo, replay, tenant e solução em produção. |
| F4-4 | implementar ingestão, deduplicação, correlação e idempotência | Evidência disponível; conferir no aceite final | hub-glpi-work-plan-2026-09-08.md; fluxo, replay, tenant e solução em produção. |
| F4-5 | executar o fluxo `Zabbix -> incidente -> GLPI -> hub -> encerramento` | Evidência disponível; conferir no aceite final | hub-glpi-work-plan-2026-09-08.md; fluxo, replay, tenant e solução em produção. |
| F4-6 | validar sessão, RBAC, tenant, logout e indisponibilidade de dependências | Aberto | Inspecionar estado atual e provar critério completo. |
| F4-7 | publicar apenas leituras cuja proveniência e atualidade sejam verificáveis. | Aberto | Inspecionar estado atual e provar critério completo. |
| F5-1 | classificar eventos antes de qualquer automação corretiva | Parcial | Triagem v1 preserva piso de severidade mesmo sem Gemini; contrato de urgência validado e fallback manual sem isolamento. 249 testes e prova no worker. Classificação por domínio e demais caminhos ainda pendentes. ai-triage-severity-2026-09-08.md. |
| F5-2 | implementar RCA assistida e sugestão de runbook com aprovação humana | Aberto | Inspecionar estado atual e provar critério completo. |
| F5-3 | migrar n8n para Node-RED fluxo a fluxo, com execução paralela controlada | Aberto | Inspecionar estado atual e provar critério completo. |
| F5-4 | integrar Datto/RMM e outras fontes aprovadas por contratos idempotentes | Aberto | Inspecionar estado atual e provar critério completo. |
| F5-5 | habilitar Evolution/WhatsApp apenas para uma jornada testada e autorizada | Aberto | Inspecionar estado atual e provar critério completo. |
| F5-6 | integrar Gemini e MISP sem enviar segredos ou dados de outro tenant | Parcial | Contexto Gemini com campos explícitos, sanitização aninhada e chave no cabeçalho; pós-incidente exige identidade persistida e consulta vetorial filtrada por cliente, verificada no PostgreSQL. MISP e política completa de dados externos pendentes. ai-context-isolation-2026-09-08.md. |
| F5-7 | medir duplicidade, latência, fila, falha, custo e taxa de intervenção humana. | Aberto | Inspecionar estado atual e provar critério completo. |
| F6-1 | implantar Wazuh em topologia isolada e recuperável | Aberto | Inspecionar estado atual e provar critério completo. |
| F6-2 | pilotar endpoints Cavan com RBAC e retenção definidos | Aberto | Inspecionar estado atual e provar critério completo. |
| F6-3 | integrar Google Workspace em leitura mínima, inicialmente sem Alert Center | Aberto | Inspecionar estado atual e provar critério completo. |
| F6-4 | normalizar eventos no fluxo de incidente já aprovado | Aberto | Inspecionar estado atual e provar critério completo. |
| F6-5 | testar isolamento entre clientes e perda de conectividade | Aberto | Inspecionar estado atual e provar critério completo. |
| F6-6 | medir EPS, filas, armazenamento e custo antes de escalar. | Aberto | Inspecionar estado atual e provar critério completo. |
| F7-1 | reconciliar Git, IaC e configuração efetiva | Aberto | Inspecionar estado atual e provar critério completo. |
| F7-2 | fechar CI com testes, lint, secret scan, SBOM e imagens por digest | Parcial | 226 testes e verificações de tipos/lint locais aprovados; 617 arquivos sem detecções no secret scan; SBOM das quatro imagens do hub gerado. Workflow SBOM preparado, ainda sem execução completa no GitHub. ci-release-verification-2026-09-08.md. |
| F7-3 | comprovar backup, restore, RPO, RTO e DR de cada sistema canônico | Parcial | Bases PostgreSQL/GLPI e Psono restaurados; hub iniciado em Docker limpo usando exclusivamente snapshot remoto de código, seis imagens e banco. Faltam SSO/segredos reais no restore, fila Redis, reconstrução do servidor, DR dos demais sistemas e RPO/RTO. recovery-verification-2026-09-08.md. |
| F7-4 | definir SLO, owner, runbook e alerta para cada serviço crítico | Aberto | Inspecionar estado atual e provar critério completo. |
| F7-5 | testar capacidade, dependência indisponível e rollback de release | Aberto | Inspecionar estado atual e provar critério completo. |
| F7-6 | executar aceite operacional D+1, D+3 e D+7. | Aberto | D+1/D+3/D+7 exigem observação nas datas reais; não antecipar aceite. |
| P-1 | **fundação visual compartilhada:** tokens, Montserrat 500, grid de 8 px, BlueDot `#00ade8`, favicon, iconografia, estados e acessibilidade | Aberto | Inspecionar estado atual e provar critério completo. |
| P-2 | **Authentik:** login, recuperação, MFA, consentimento, erros e catálogo de aplicações | Aberto | Inspecionar estado atual e provar critério completo. |
| P-3 | **Psono:** marca, título do navegador `vault ness.`, login, cofre, MFA e mensagens de recuperação | Aberto | Inspecionar estado atual e provar critério completo. |
| P-4 | **Zabbix:** navegação, dashboards por público, mapas, títulos, densidade, empty states e experiência móvel | Aberto | Inspecionar estado atual e provar critério completo. |
| P-5 | **GLPI:** portal, catálogo, tickets, conhecimento e visão do cliente | Aberto | Inspecionar estado atual e provar critério completo. |
| P-6 | **hub:** visão executiva, operação, incidentes, inventário, projetos e PWA | Aberto | Inspecionar estado atual e provar critério completo. |
| P-7 | **ferramentas operacionais:** Node-RED, observabilidade e consoles internos | Aberto | Inspecionar estado atual e provar critério completo. |
| P-8 | **revisão transversal:** consistência visual, linguagem pt-BR, desempenho, responsividade, contraste e jornada ponta a ponta. | Aberto | Inspecionar estado atual e provar critério completo. |

## Progresso desta continuação

- Typecheck `tsc -b` e build Vite aprovados após correções de tipos/imports; frontend implantado.
- Navegador Chromium operacional no WSL; jornada senha/TOTP/consentimento/tela de incidentes aprovada para Alupar, Cavan e NOC.
- Corrigidos navegação lateral e escopo visual dos clientes; frontend implantado e verificado.
- Logout de aplicação aprovado; logout central aprovado como ação separada.
- Corrigida autorização de entrada do grupo `usuarios` no hub, condicionada a tenant reconhecido.
- MFA global não comprovado: estágio atual permite `skip` quando não configurado.
- Gemini confirmado HTTP 429, cota gratuita de 20 requisições; orçamento solicitado.

O objetivo permanece ativo. Gates não serão marcados concluídos com base apenas
em disponibilidade de processo, testes parciais ou funcionalidades de outra onda.
