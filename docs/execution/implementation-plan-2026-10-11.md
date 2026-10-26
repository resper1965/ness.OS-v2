# Plano de implementação — ness.OS

> **Atualização de execução — 12/10/2026 (BRT):** a promoção real do
> Hub/AIOps foi feita a partir do commit `144317f`, com API, workers e frontend
> em imagens GHCR imutáveis, backup anterior e rollback/re-promoção ensaiados.
> A evidência está em
> [`evidence/hub-immutable-release-2026-10-12.md`](evidence/hub-immutable-release-2026-10-12.md).
> G0 global segue **PARCIAL**: o workflow de publicação ainda precisa da
> revisão e dos checks exigidos no PR #65. O PR de entrega atual, #64, também
> está bloqueado porque os jobs de Actions não receberam runner (`runner_id=0`),
> por falha de pagamento ou limite de gastos da conta, conforme a annotation
> oficial do job `114826066735`. A regularização de Billing & plans é a ação
> necessária para executar os checks. G1-Hub/AIOps foi renovado com restore
> externo; o trabalho ativo é G2 (identidade e cofre), documentado nas
> evidências de 12/10.

Data: 2026-10-11 (BRT)  
Objetivo: transformar evidências dispersas em uma sequência de entrega
operacional, recuperável e mensurável.

## Critério de avanço

Trilha ativa: `dynamic-delivery-track-2026-10-12.md`. Prioridade exclusiva
Zabbix, cartões Z1–Z8 com entregas visíveis e testes proporcionais. Z1 está
ativo; backup e dependências humanas seguem fora do caminho das tarefas
independentes. A trilha substitui a ordem de execução, não os gates produtivos.

Atualização autorizada em 12/10: G2 permanece aberto em issues #43, #45, #48,
#51 e #66; GitHub/Actions em #67, índice em #68. Implementação e ensaios
isolados das etapas seguintes continuam. Toda dependência humana gera issue
e e-mail de instrução. Ver `human-actions-and-independent-delivery-2026-10-12.md`.

Cada fase só avança quando a evidência indicada existe, foi colhida no ambiente
correto e não contém segredos. Falha ou ausência de evidência mantém o gate
aberto; não se compensa com documentação, mock, processo `running` ou teste
local isolado.

## Fase 0 — repositório, release e recuperação

**Resultado:** um baseline de release reconstruível e sem material temporário.

1. Manter `main`/branch de entrega sincronizados e separar commits por domínio.
2. Remover do checkout temporários, dumps e credenciais; manter somente
   quarentena externa controlada e inventariada.
3. Executar CI completo: backend, frontend, lint, tipos, secret scan, SBOM,
   Compose e scripts operacionais.
4. Revalidar Restic de Zabbix, AIOps e Psono: último `COMPLETED`, checksum,
   `restic check`, restore isolado e RPO de até 24 horas.
5. Registrar rollback de release e dos bancos antes de qualquer deploy.

**Aceite:** árvore limpa, commit/tag reproduzível, CI verde, digests conhecidos,
backup e restore datados.  
**Bloqueia:** deploy, corte Zabbix e escritas de integração.

## Fase 1 — identidade, cofre e acesso privilegiado

**Resultado:** identidade centralizada e segredos controlados.

1. Revisar cada aplicação no Authentik: Hub, GLPI, Zabbix, Psono, Grafana,
   Node-RED e futuras ferramentas.
2. Homologar login, logout, expiração, revogação, usuário desativado,
   break-glass e teste negativo de tenant por aplicação.
3. Fechar Psono Community: Ricardo e Ismael como custodians, MFA, códigos de
   recuperação fora das VPS, SMTP/recuperação e restore independente.
4. Migrar segredos consumidor a consumidor para o cofre; validar, revogar o
   segredo anterior e registrar somente o identificador da rotação.
5. Mover automação para SOPS/age com ao menos dois responsáveis de recuperação.

**Aceite:** dois custodians recuperam o cofre, MFA comprovado e nenhum segredo
válido em Git ou arquivos de projeto.  
**Bloqueia:** automação produtiva e acessos administrativos ampliados.

**Estado em 12/10:** `platform_admin` contém exclusivamente Ismael, Rogerio e
Ricardo. O fluxo padrão do Authentik já valida MFA, mas usa `skip` para quem
ainda não cadastrou fator. No Psono, Ismael já tem MFA e Ricardo ainda não;
ambos acessaram o cofre, mas não há recovery/emergency codes. A VPS dedicada
continua pendente. A recuperação por senha e SMTP estão ativos no runtime,
divergência registrada que deve ser decidida antes de promoção.

## Fase 2 — Zabbix: migração, qualidade e operação

**Resultado:** Zabbix definitivo ativo com dados corretos e sem dupla coleta.

1. Revalidar, somente leitura, a origem e `zbx-prd-01`: versão, backup,
   listeners, banco, proxies, itens, ações, mídias e conectores.
2. Confirmar restore isolado mais recente no destino e backup reversível do
   estado atual; manter a origem intacta como rollback por 7–14 dias.
3. Homologar HTTPS e SAML com contas nominais e perfis mínimos.
4. Executar piloto Cavan — Matriz: FortiGate/links, switches, VMs, tags,
   owner, serviço, criticidade, localização e templates compatíveis.
5. Corrigir por causa os itens não suportados, disponibilidade de agente/SNMP,
   VMware/storage e backlog de triggers; nunca por SQL ou desativação em massa.
6. Validar alerta sintético sem canais reais, dependências e recuperação.
7. Fazer corte DNS em janela aprovada, smoke test e observação D+1/D+3/D+7.
8. Só após dados confiáveis: mapas, painéis por público e branding reversível.

**Aceite:** coleta, APIs, SSO, backup, rollback, alertas controlados e piloto
aprovados; origem preservada durante observação.  
**Rollback:** DNS/origem, sem apagar banco ou histórico do destino.

## Fase 3 — GLPI e catálogo de serviços

**Resultado:** ITSM utilizável como sistema de registro.

1. Resolver a API de máquina por rota suportada, sem contornar SSO.
2. Validar entidades, perfis, catálogo, SLAs com unidade contratual, projetos,
   tarefas e runbooks.
3. Reconciliar ativos Cavan com Zabbix e habilitar GLPI Agent apenas no piloto.
4. Provar criação, atribuição, atualização e encerramento de ticket por API e
   interface, com trilha auditável.

**Aceite:** ticket do piloto relaciona tenant, ativo, local, serviço, owner e
criticidade.  
**Bloqueia:** automação Hub → GLPI em produção.

## Fase 4 — Hub ness.OS e MVP integrado

**Resultado:** incidente real rastreável, isolado e útil ao operador.

1. Promover somente release que tenha Fase 0 aprovada.
2. Executar UAT Authentik para `operator`, `viewer`, NOC/SOC e
`platform_admin`, incluindo SSE, logout e tenant cruzado negativo.
3. Exercitar Compose real: PostgreSQL, Redis, API, Celery, frontend, health,
fila, reinício e dependência indisponível.
4. Homologar Zabbix → Hub → GLPI com evento sintético autorizado: deduplicação,
replay, ticket, ACK, encerramento e auditoria.
5. Publicar apenas fonte com proveniência/frescor; fontes indisponíveis devem
mostrar estado indisponível, não contagem fictícia.
6. Entregar PWA técnico para NOC/SOC depois do fluxo ponta a ponta aceito.

**Aceite:** um incidente do piloto percorre o fluxo completo, sem vazamento de
tenant ou duplicação.  
**Rollback:** desabilitar ingestão/integração e manter fontes originais.

## Fase 5 — AIOps e automação assistida

**Resultado:** assistência operacional sem ação autônoma insegura.

1. Definir contrato de alerta, incidente e pós-incidente.
2. Classificar eventos por severidade e tenant, com fallback humano.
3. Implementar sugestão de RCA/runbook com aprovação explícita.
4. Migrar n8n para Node-RED fluxo a fluxo, mantendo execução paralela e
rollback por fluxo.
5. Integrar Atera/Datto e Evolution apenas quando houver contrato idempotente e
jornada aprovada.
6. Medir duplicidade, latência, falhas, fila, custo e intervenção humana.

**Aceite:** automação só atua em jornada autorizada, é auditável e reversível.

## Fase 6 — Wazuh, Google Workspace e escala

**Resultado:** SecOps hub-spoke isolado e dimensionado por dados reais.

1. Aprovar BOM de VPS e topologia hub-spoke antes de provisionar.
2. Pilotar 50–100 endpoints Cavan, definir retenção e medir EPS/APS, filas,
CPU, memória e custo.
3. Integrar Google Workspace em leitura mínima, sem Alert Center inicialmente.
4. Normalizar eventos no fluxo de incidentes já aprovado e testar falha de rede
e isolamento entre tenants.
5. Escalar progressivamente: 100 → 500 → 1.000 → 5.000 endpoints, promovendo
apenas após estabilidade da faixa anterior.

**Aceite:** RPO/RTO, RBAC, isolamento, capacidade e custo comprovados no piloto.

## Fase 7 — experiência, governança e operação contínua

**Resultado:** serviços operados, não apenas implantados.

1. Aplicar branding ness. de forma suportada e reversível em cada aplicação.
2. Consolidar dashboards executivo, NOC/SOC, sustentação, governança e cliente
somente depois de validar dados fonte.
3. Versionar runbooks por serviço/tenant e vincular mudanças a GLPI.
4. Definir owner, SLO, alertas, capacidade, backup, DR e calendário de revisão
para cada serviço crítico.
5. Concluir aceite operacional D+1, D+3 e D+7 antes de encerrar cada promoção.

## Ordem prática de execução

```text
Fase 0 -> Fase 1 -> Fase 2 -> Fase 3 -> Fase 4
                             -> Fase 5
                             -> Fase 6
Fase 7 acompanha cada promoção, mas não antecede a estabilidade funcional.
```

## Atualização obrigatória

Ao fim de cada mudança, atualizar `docs/execution/project-stage-YYYY-MM-DD.md`
com: decisão, evidência, estado do gate, rollback, owner e próximo passo.
Este plano é a ordem de trabalho; os documentos de evidência continuam sendo a
prova de execução.
