# Plano mestre executável de implantação e conclusão do ness.OS

> Versão canônica: 2.1 — 23/08/2026
> Escopo: ativos existentes, infraestrutura Contabo escalonada, aplicações especializadas e produto ness.OS
> Horizonte: 18 semanas para a primeira operação integrada; crescimento até 5.000 endpoints acionado por métricas
> Estado: aprovado por Ricardo Esper; Gate 0 em andamento
> Fonte visual: [`docs/presentations/ness-os-infrastructure-5000-endpoints.html`](presentations/ness-os-infrastructure-5000-endpoints.html)

## 1. Objetivo

Concluir o ecossistema existente antes de ampliar o portfólio. “Concluído” significa que cada componente:

1. tem função e proprietário definidos;
2. pode ser reinstalado a partir do repositório;
3. não depende de segredos versionados ou mudanças manuais desconhecidas;
4. possui teste, monitoramento, backup e procedimento de recuperação proporcionais ao risco;
5. atende critérios mensuráveis de segurança, disponibilidade e isolamento de clientes;
6. possui documentação operacional compatível com o estado real.

### 1.1 North Star do produto

O **ness.OS é a camada unificada de experiência, contexto e inteligência da TI**. Ele disponibilizará a stakeholders, clientes e equipes internas painéis orientados a persona e tenant sobre saúde, projetos, Governança, Infraestrutura, Sustentação e Segurança. GLPI, Zabbix, Wazuh e as demais ferramentas permanecem fontes especializadas; o ness.OS normaliza, relaciona, qualifica e apresenta os fatos sem criar registros canônicos concorrentes.

A coleta de indicadores, sua qualidade e a evolução do painel executivo são metas permanentes desde a baseline até a operação. A decisão e o contrato inicial estão no [`ADR 0011`](adr/0011-ness-os-product-and-executive-indicators.md) e em [`docs/specs/executive-indicators-contract.md`](specs/executive-indicators-contract.md).

### 1.2 Escopo end-to-end do projeto

O projeto começa na instalação e configuração dos ativos e termina quando o portal, as APIs, os processos e a operação puderem ser recuperados, medidos e administrados. O teto de 5.000 endpoints é capacidade evolutiva, não requisito do primeiro go-live.

| Frente | Resultado entregue |
|---|---|
| Fundação e ativos | VPS, rede privada/VPN, DNS, TLS, contas nominais, IaC, inventário GLPI e monitoração Zabbix |
| Recuperação e segredos | Psono Community, SOPS/age, Contabo Object Storage S3, checksums, restore e RPO/RTO comprovados |
| Disponibilidade | Zabbix reconstruído, saneado, com proxies, templates, localização, mapas, dashboards e alertas úteis |
| Governança e serviço | GLPI como ITSM/CMDB, catálogo, inventário, projetos, conhecimento e runbooks multi-tenant |
| Segurança | Wazuh hub-spoke implantado por ondas, começando em até 1.000 e crescendo por gatilhos até 5.000 endpoints |
| Identidade | Authentik homologado por aplicação, MFA, break-glass e `platform_admin` global restrito |
| Inteligência AIOps | ingestão, normalização, correlação, deduplicação, qualificação de incidente, RCA e automação controlada |
| Portal ness.OS | PWA multi-tenant por persona, painel executivo, saúde, projetos, incidentes e drill-down às fontes |
| Plano de controle Contabo | API read-only para VPS, snapshots, firewalls, redes privadas e Object Storage, reconciliada com GLPI/Zabbix |
| Operação | CI/CD, observabilidade, SLO, hardening, runbooks, UAT, treinamento, suporte e melhoria contínua |

### 1.3 Fontes canônicas do projeto

- arquitetura: [`architecture/ness-os-official-architecture.md`](architecture/ness-os-official-architecture.md);
- capacidade e compras: [`vps-capacity-and-sequencing-plan.md`](vps-capacity-and-sequencing-plan.md);
- decisões: [`adr/README.md`](adr/README.md);
- execução atual: [`execution/gate-0-status.md`](execution/gate-0-status.md);
- estágio executivo: [`execution/project-stage-2026-08-23.md`](execution/project-stage-2026-08-23.md);
- API Contabo: [`specs/contabo-control-plane-integration.md`](specs/contabo-control-plane-integration.md);
- indicadores: [`specs/executive-indicators-contract.md`](specs/executive-indicators-contract.md);
- projetos: [`specs/ti-project-portfolio.md`](specs/ti-project-portfolio.md);
- runbooks: [`specs/operational-runbook-library.md`](specs/operational-runbook-library.md).

Este documento controla sequência, dependências e aceite. Os documentos especializados controlam o detalhe técnico; informações não devem ser copiadas entre eles sem necessidade.

## 2. Princípios de execução

- Segurança e recuperação vêm antes de novas funcionalidades.
- O Git será a fonte única de código, configuração não secreta e documentação.
- Produção não será atualizada por scripts avulsos ou cópias manuais sem registro.
- Toda mudança terá verificação, rollback e evidência.
- Integrações sem dono, contrato ou teste serão classificadas como experimentais e ficarão desabilitadas.
- A solução mais simples que cumpra o SLO será preferida; não há necessidade de Kubernetes para duas VPS.
- Componentes novos devem ser open source, com licença OSI compatível e código-fonte auditável. Serviço comercial só é admissível quando operar uma solução open source sem transformar dados ou configuração em dependência proprietária.
- Serviços externos fechados só podem entrar por adaptadores substituíveis e nunca serão o registro canônico. A política, o tratamento do legado e a proibição de tags flutuantes estão formalizados no [`ADR 0010`](adr/0010-open-source-license-boundary.md).
- Wazuh Hub/Spokes, novos provedores e expansão comercial ficam bloqueados até o núcleo passar pelo Gate 4 deste plano.

## 3. Diagnóstico executivo

### Pontos fortes

- Zabbix 7.0 LTS está ativo, com banco local, TLS, UFW e Fail2ban.
- Hub AIOps possui 14 contêineres ativos, persistência definida e recursos limitados por serviço.
- Backend já implementa ingestão, fingerprint, locks Redis, Celery, incidentes, RCA, SSO, RBAC e integrações relevantes.
- Frontend já apresenta visão NOC/SOC, incidentes, nuvem e multi-tenant.
- Há testes backend, CI inicial, Terraform, Ansible, runbooks e documentação arquitetural.
- O componente Keep foi removido do estado atual, reduzindo sobreposição e superfície de ataque.

### Críticas principais

1. **A ambição funcional avançou mais rápido que a maturidade operacional.** Há muitas integrações simultâneas, mas backup, restauração, deploy e gestão de segredos ainda não estão fechados.
2. **Produção e Git não formam hoje uma cadeia reproduzível.** O deploy configurado usa caminhos diferentes dos caminhos reais e a VPS não é um checkout controlado.
3. **Há credenciais reais ou aparentes versionadas.** Também existe senha administrativa compartilhada entre VPS. Isso é um incidente de segurança, não apenas dívida técnica.
4. **A documentação mistura estado desejado, histórico e realidade.** Terraform descreve quatro VPS; o ambiente confirmado possui duas no escopo atual.
5. **Não existe evidência de backup restaurável dos bancos.** Backups não testados devem ser considerados inexistentes.
6. **Autenticação está fragmentada e o Authentik está apenas parcialmente funcional.** Caddy Basic Auth, JWT local, OIDC/Auth­entik, API keys e logins locais coexistem sem uma política única; cada solução precisa de revisão e homologação direta, sem presumir que a presença de configuração represente SSO operacional.
7. **O multi-tenancy está modelado, mas não comprovado.** Há colunas de tenant/cliente, porém não foram encontradas políticas PostgreSQL RLS nem uma suíte completa de testes de isolamento.
8. **A qualidade ainda não fecha em ambiente limpo e reproduzível.** A validação mais recente executou 35 testes backend e build frontend com sucesso, mas `package.json` e `package-lock.json` permanecem dessincronizados; o build exigiu recomposição local de dependência opcional e ainda há warnings de lint. A release precisa ser repetível a partir de checkout limpo.
9. **O CI/CD atual é inseguro e incompatível com produção.** Há credencial de teste explícita, `StrictHostKeyChecking=no`, deploy como usuário privilegiado e destino `/root/app`, enquanto produção usa `/opt/n-infraops/app`.
10. **A observabilidade é parcial.** Existe integração de envio ao Loki, mas não há stack ou contrato operacional documentado para métricas, logs, tracing, SLOs e alerta externo do próprio Hub.

## 4. Decisões que precisam de resposta

| ID | Pergunta | Recomendação inicial | Impacto se não decidido |
|---|---|---|---|
| D1 | O escopo inclui apenas as duas VPS atuais ou também Wazuh/MISP? | **Decidido:** o projeto completo inclui Wazuh hub-spoke após estabilizar o núcleo; MISP permanece em avaliação posterior. | Wazuh integra o roadmap, mas não bloqueia a recuperação do núcleo. |
| D2 | Qual ITSM e inventário/CMDB serão canônicos? | **Decidido:** GLPI, já instalado; o GLPI Agent fará a coleta de inventário. DeskManager deve ser retirado após confirmar ausência de obrigação contratual. | Evita tickets, IDs e cadastros de ativos duplicados. |
| D3 | Qual RMM é primário? | **Direção aprovada:** SuperOps é o candidato-alvo; Atera e Datto permanecem durante a transição. O RMM já instalado em cada ativo distribuirá o GLPI Agent. | Homologar API, segurança, licenciamento e migração antes de declarar SuperOps canônico. |
| D4 | Authentik será a identidade obrigatória? | **Decidido:** sim como estado-alvo; a instalação atual é apenas parcialmente funcional e deve ser revisada diretamente em cada solução. OIDC/SAML para usuários, MFA para privilegiados e contas locais break-glass auditadas. | Authentik passa a serviço crítico e precisa de homologação por aplicação e recuperação comprovada. |
| D5 | Quais RPO/RTO são exigidos? | **Decidido:** RPO 24 h e RTO 4 h na primeira versão. | Define backup diário e recuperação em até quatro horas. |
| D6 | Onde ficarão os backups? | **Decidido:** Contabo Object Storage S3 será a cópia externa primária, com credencial exclusiva, criptografia, retenção e futura segunda cópia independente. A contratação e as credenciais ainda são bloqueio do Gate 0. | Backup local não encerra o requisito de recuperação. |
| D7 | Existe janela de manutenção aceita? | **Decidido:** 22:00–00:00 em `America/Sao_Paulo` para mudanças que possam afetar Zabbix, proxies, banco, ingestão ou disponibilidade do monitoramento. Ativos sem vínculo direto com essa operação podem ser tratados fora da janela, com mudança registrada e rollback. | Protege a operação crítica sem impor janela desnecessária aos demais ativos. |
| D8 | Quem aprova produção e quem administra a plataforma? | **Decidido:** Ricardo Esper é owner/aprovador. O papel global `platform_admin` fica restrito a Ricardo Esper, Rogério Salerno e Ismael Araujo. Agnaldo Silva permanece operador em observação, sem administração global. | Separar privilégios por domínio e impedir contas compartilhadas/superadmin cotidiano. |
| D9 | Qual será o canal técnico mobile? | **Decidido:** PWA instalável para Android/iOS, majoritariamente BYOD; Evolution/WhatsApp apenas fallback. | Exige política de sessão, revogação e dados locais para BYOD. |
| D10 | Qual é o SLO comercial? | **Decidido:** 99,5% mensal para portal/API e 99,9% para ingestão Zabbix. | Passa a orientar alertas, erro budget e capacidade. |
| D11 | O domínio e a marca oficiais serão `zabbix.ness`, `n.infraops` ou `ness.OS`? | **Decidido:** o produto é **ness.OS**; `n.infraops`, `n.secops` e os demais domínios são módulos. Domínios técnicos legados serão alinhados gradualmente, sem renomeação arriscada durante a estabilização. | A marca e a arquitetura de produto passam a ter uma referência única. |
| D12 | Qual é o teto operacional? | **Decidido:** até EUR 2.000/mês para a operação do ecossistema; manter cenários mínimo, recomendado e ideal dentro desse limite. | Permite cotar resiliência, RMM e observabilidade com limite explícito. |
| D13 | Onde serão guardadas senhas, chaves e segredos de automação? | **Decidido:** Psono Community será o cofre humano; SOPS/age atenderá automação. O cofre ficará em terceira VPS independente e passará por PoC antes de receber segredos reais. Passbolt Community é apenas contingência. | Nenhum requisito poderá depender de edição Business/Enterprise. SSO e auditoria granular permanecem lacunas conhecidas e aceitas com controles compensatórios. |
| D14 | O cofre Community pode compartilhar VPS com a plataforma de phishing? | **Decidido:** não. O laboratório de phishing será segregado e preferencialmente efêmero; Psono/Passbolt Community permanecerá em VPS pequena dedicada. | Evita unir o cofre de recuperação a uma aplicação de maior exposição e risco. |
| D15 | Quando entram Wazuh e a reconstrução Zabbix? | **Revisado:** polimento lógico e baseline GLPI primeiro; a transmutação isolada pode ocorrer em paralelo, mas o cutover do Zabbix aguarda esses critérios. A Hostinger KVM8 é fábrica/ponte curta e o destino Zabbix é uma Contabo limpa. A Onda 1 é piloto com oito VPS totais (sete Wazuh + uma Psono), sem HA/SLA e sem retirar a Hostinger; a Onda 2 chega a dez VPS totais, adiciona edge/worker, assume SLA somente após estabilidade e então retira a Hostinger. O teto de 11 VPS atende ao crescimento medido até 5.000 endpoints. | Hostinger e KVM8 são transitórias e valem zero na capacidade permanente; a saída da Hostinger é critério da Onda 2, não da Onda 1. |
| D16 | Checkmk Community deve substituir ou complementar o Zabbix? | **Decidido:** não será componente canônico nem substituto. A edição Community será apenas referência; eventual laboratório descartável de 20–30 ativos não abrirá alertas ou tickets de produção. | O alvo de 5.000 ativos e a operação MSP excedem o papel definido para a avaliação lateral. Veja a [avaliação](evaluations/checkmk-community-lateral-assessment.md). |
| D17 | Qual será a fonte canônica do portfólio e status dos projetos? | **Direção provisória:** usar Projetos nativos do GLPI Community para governança, portfólio, tarefas, equipes, prazos, custos e vínculos ITIL/ativos; o ness.OS será a visão executiva. Validar versão, permissões, API e piloto antes de tornar a decisão definitiva. Ferramentas técnicas de execução poderão ser ligadas por URL/adaptador, sem duplicar o portfólio. | Evita nova VPS e aproveita relações com serviços, tickets, mudanças e CMDB. Até a homologação, indicadores de projetos permanecem `provisional`/`unavailable`. Veja a [especificação do módulo](specs/ti-project-portfolio.md). |
| D18 | Onde ficam políticas, procedimentos e runbooks operacionais? | **Decidido:** o ness.OS não será o repositório oficial de políticas. Ele manterá uma biblioteca operacional multi-tenant de runbooks, checklists e orientações derivadas, usando GLPI Knowledge Base para autoria/publicação operacional e o portal ness.OS para contexto, busca e indicadores. A política oficial da Ness ou do cliente permanece em seu sistema documental de origem e é apenas referenciada por ID, versão, owner e URL. Runbooks acoplados ao código permanecem no repositório do serviço. | Evita transformar o produto em GED/GRC, mantém o conteúdo acionável e preserva a autoridade documental de cada organização. Veja a [especificação da biblioteca operacional](specs/operational-runbook-library.md). |

### 4.1 Baseline confirmada em 20/08/2026

- ITSM e inventário/CMDB canônicos: GLPI; o GLPI Agent fará a coleta de inventário dos endpoints.
- RMM: SuperOps é o candidato-alvo; Datto/Atera permanecem durante a transição. Cada ativo receberá o GLPI Agent pelo RMM que já tiver instalado.
- Wazuh e MISP: segunda etapa, após aquisição de máquinas.
- Capacidade-alvo evolutiva: **5.000 endpoints** e cinco operadores simultâneos; primeira onda até aproximadamente 1.000.
- Perfil de carga: a plataforma anterior é fechada e não fornecerá a série histórica necessária; a baseline será capturada por 30 dias no Zabbix/Hub com telemetria própria.
- Recuperação: RPO 24 h e RTO 4 h.
- Owner atual: Ricardo Esper.
- Estado operacional: Zabbix em produção; Hub AIOps em pré-produção.
- Backup: Contabo Object Storage escolhido, mas ainda não contratado/configurado; bloqueio externo explícito do Gate 0.
- Mensageria: Evolution é contingência, não canal primário.
- Canal primário futuro: aplicativo mobile SOC/NOC; começar pela PWA existente.
- Dispositivos: Android e iOS, majoritariamente BYOD; distribuição inicial sem dependência de app stores.
- Identidade: Authentik obrigatório como estado-alvo, porém atualmente apenas parcialmente funcional; nenhuma integração será considerada pronta sem teste direto na respectiva solução.
- SLO: 99,5% portal/API e 99,9% ingestão Zabbix.
- Manutenção relacionada ao Zabbix: 22:00–00:00 em `America/Sao_Paulo`, em qualquer dia, sempre agendada. A janela pode ser dispensada para ativos sem vínculo direto com a operação Zabbix, após avaliação de impacto.
- Administração global: somente Ricardo Esper, Rogério Salerno e Ismael Araujo integram `platform_admin`; Agnaldo Silva permanece operador em observação.
- Regulação: sem obrigação específica atual, mas arquitetura deve permanecer preparada para LGPD e controles auditáveis.
- Fonte oficial: GitHub atual, com proteção de branch e environments.
- Retenção inicial: alertas brutos por até 90 dias para refinamento; incidentes confirmados por 12 meses. Métricas agregadas não devem conservar payload sensível.
- Orçamento operacional: teto de EUR 2.000/mês.

### 4.2 Consequências práticas

- O Zabbix só recebe mudança após backup emergencial, janela e rollback.
- Mudanças em ativos fora da operação Zabbix não dependem da janela 22:00–00:00, mas continuam exigindo responsável, registro, avaliação de impacto, validação e rollback proporcionais ao risco.
- A VPS AIOps pode ser reorganizada e reconstruída antes do go-live, reduzindo o custo de preservar drift atual.
- DeskManager passa a ser dívida de remoção, não integração a concluir.
- Automações específicas do SuperOps devem ser limitadas até concluir a homologação. O GLPI será a fonte mestra do inventário; SuperOps, Datto e Atera serão reconciliados com os ativos do GLPI, sem substituir a CMDB.
- A ausência de exportação da plataforma anterior será tratada como lacuna de baseline: as ondas de capacidade usam 30 dias de métricas próprias e previsão de 90 dias.
- A solução mobile não deve começar como novo aplicativo nativo. A PWA atual deve provar jornadas, autenticação, push e adoção; app nativo será reavaliado depois.
- O acúmulo de todos os papéis em uma pessoa torna automação, documentação e acesso break-glass requisitos de go-live.

## 5. Arquitetura-alvo para o escopo atual

```text
Internet / Agentes
        |
        +--> VPS Zabbix/NOC
        |      Zabbix Server + Agent 2 + Apache/PHP + MariaDB
        |      backup externo + monitoramento externo
        |
        +--> VPS AIOps
               Caddy (única borda pública)
                 |-- ness.OS Web/PWA por persona e tenant
                 |-- FastAPI API/webhooks
                 |-- Authentik
                 |-- GLPI
                 |-- n8n
                 `-- Evolution API

               Rede interna Docker
                 |-- Celery alerts / ML
                 |-- PostgreSQL/TimescaleDB
                 |-- Redis
                 `-- MariaDB GLPI

               Serviços externos aprovados
                 |-- Gemini
                 |-- RMM primário
                 |-- MISP (se confirmado)
                 |-- Object Storage de backup
                 `-- monitoramento/heartbeat externo
```

O Hub correlacionará um modelo comum de cliente, serviço, ativo, projeto, risco, controle, incidente, SLA e responsável. Todo indicador deverá informar fonte, período, atualização e qualidade; ausência ou falha de coleta nunca será convertida silenciosamente em zero.

Portas de serviços internos não devem ser publicadas diretamente. Caddy será a única entrada web; SSH será restrito a chaves e origens administrativas.

## 6. Frentes de trabalho por componente

### 6.1 Governança, Git e gestão de mudanças

**Problema atual:** worktree com muitos scripts e artefatos avulsos, documentação não versionada, branches de deploy múltiplas e ausência de release formal.

**Ações:**

- Congelar novas features até o Gate 2.
- Classificar cada arquivo avulso como código permanente, migração única, evidência ou descarte.
- Organizar scripts de manutenção em `tools/` ou `infra/scripts/`, sem credenciais.
- Adotar `main` protegida, PR obrigatório, revisão e commits assinados quando possível.
- Criar releases versionadas e `CHANGELOG.md`.
- Usar ADRs para decisões D1–D12.
- Definir matriz RACI e calendário de mudanças.

**Critério de aceite:** repositório limpo, sem artefatos de execução na raiz, branch protegida, owners definidos e release inicial marcada.

### 6.2 Segredos, identidade administrativa e hardening

**Problema atual:** segredos em arquivos/CI, senha de root compartilhada, defaults inseguros, acesso root direto e TLS desabilitado para MISP.

**Ações imediatas:**

- Inventariar e rotacionar senhas de root, bancos, GLPI, OIDC, Authentik, JWT, webhooks, n8n, Evolution e APIs externas.
- Remover segredos do estado atual e, após rotação, reescrever o histórico Git com procedimento coordenado.
- Revogar chaves/tokens antigos e renovar GitHub Actions Secrets.
- Criar usuários nominais de administração e deploy; bloquear SSH por senha e login root remoto após validar break-glass.
- Remover segredos padrão dos Compose; falhar o startup quando variáveis obrigatórias estiverem ausentes.
- Habilitar MFA para administradores no Authentik.
- Habilitar validação TLS do MISP com CA correta.
- Implantar duas camadas open source complementares: cofre Community autohospedado para credenciais humanas/break-glass e SOPS/age para segredos de automação versionáveis.
- Hospedar o cofre em terceira VPS dedicada; não criar dependência circular entre falha do ecossistema e acesso às credenciais de recuperação.
- Implantar Psono Community após PoC aprovado; manter Passbolt Community apenas como contingência. Não projetar SSO, LDAP, auditoria granular ou políticas que dependam de Business/Enterprise.
- Dimensionar a nova VPS com Debian 13, 2 vCPU, 4 GB RAM e pelo menos 40 GB, expondo apenas 80/443 e SSH restrito; manter MariaDB, TLS, NTP, SMTP, atualização, hardening, monitoramento externo e backup criptografado fora dela.
- Criar grupos/cofres separados para infraestrutura, aplicações, integrações, clientes e break-glass; nenhum administrador recebe acesso universal por padrão.
- Migrar os arquivos temporários `root-only` das VPS para o cofre, validar acesso por dois responsáveis e então removê-los por procedimento registrado.

**Critério de aceite:** scanner não encontra segredo válido, root não autentica por senha, deploy usa conta restrita, o cofre é acessível por pelo menos dois responsáveis e todos os segredos possuem owner/data de rotação.

### 6.3 VPS Zabbix/NOC

**Problema atual:** operação funcional, mas sem backup comprovado; porta 10051 ampla; inventário de proxies incompleto; renovação Certbot duplicada.

**Ações:**

- Ativar playbook de backup com dump consistente e cópia externa.
- Executar restauração integral em ambiente descartável.
- Restringir 10051 aos proxies/redes aprovados.
- Completar inventário dos 15 proxies ou remover entradas não contratadas.
- Consolidar renovação TLS em um único mecanismo.
- Revisar housekeeping, crescimento de history/trends, índices e retenções.
- Remover plugins Agent 2 que não sejam utilizados.
- Criar monitoramento externo para HTTP, trapper, banco, fila de valores e idade do último backup.
- Definir política de patches Zabbix 7.0 LTS/MariaDB/Debian.

**Critério de aceite:** restore testado, proxies documentados, firewall restrito, sem serviço falho e capacidade projetada por 12 meses.

### 6.4 VPS AIOps e sistema operacional

**Problema atual:** Fail2ban falha após boot, acesso root direto, sem swap, portas 8082/8085 publicadas e Docker pode contornar UFW.

**Ações:**

- Corrigir jail SSH para backend `systemd` e criar teste de banimento seguro.
- Criar usuário nominal e conta de deploy; restringir root.
- Fechar 8082 e 8085 externamente; acessar Manager/GLPI apenas por Caddy/VPN.
- Implementar regras `DOCKER-USER` ou firewall equivalente, testadas de fora da VPS.
- Configurar zram ou swap pequeno com parâmetros apropriados.
- Ativar atualizações de segurança, política de reboot e manutenção.
- Configurar rotação de logs Docker e limites de disco.
- Monitorar temperatura não aplicável, CPU steal, memória, I/O, inode e disco Docker.

**Critério de aceite:** nenhum serviço systemd falho, somente portas aprovadas expostas, acesso privilegiado auditável e alerta antes de saturação.

### 6.5 Docker Compose e cadeia de imagens

**Problema atual:** tags `latest`, defaults de senha, rede única, bind mount de código e healthchecks incompletos.

**Ações:**

- Fixar todas as imagens por versão e digest.
- Construir imagens imutáveis no CI; produção não deve montar o código-fonte gravável.
- Separar redes `edge`, `app` e `data`; bancos não participam da rede de borda.
- Adicionar healthcheck útil a cada serviço e dependência.
- Definir CPU, memória, PIDs, `no-new-privileges`, capabilities e usuário não-root onde suportado.
- Tornar filesystem read-only quando possível e montar apenas diretórios necessários.
- Validar Compose e variáveis antes do deploy.
- Eliminar o Compose alternativo da raiz ou torná-lo explicitamente exemplo de desenvolvimento.

**Critério de aceite:** reinstalação produz os mesmos digests, nenhum segredo default, nenhum banco publicado e rollback de imagem demonstrado.

### 6.6 Backend FastAPI, Celery e pipeline de alertas

**Problema atual:** erro de sintaxe em módulo, CI duplicado, rotas e fluxos parcialmente protegidos, métricas em memória e integração externa sem contratos completos.

**Ações:**

- Corrigir `contabo_firewall.py` e fazer todo o pacote compilar em Python 3.12.
- Consolidar Ruff, format, MyPy e pytest em um único pipeline obrigatório.
- Auditar todas as rotas por autenticação, autorização e tenant.
- Remover registro duplicado de routers e endpoints obsoletos.
- Tornar ingestão idempotente por `event_id`/fingerprint e testar retries.
- Padronizar timeouts, retries com backoff, circuit breaker simples e erros de integrações.
- Persistir métricas de triagem; não mantê-las apenas na memória do processo.
- Proteger webhooks com HMAC/segredo rotacionável, replay window e rate limit.
- Substituir token SSE em query string por cookie seguro ou ticket efêmero.
- Adotar Alembic como única trilha de migração.
- Criar testes de contrato para Zabbix, GLPI, n8n, Authentik, RMM, Gemini e MISP.
- Garantir que ações de remediação sejam deny-by-default e exijam aprovação humana auditada.

**Critério de aceite:** lint/type/test/compile verdes, cobertura mínima acordada, nenhuma rota sensível sem política e pipeline idempotente sob retry.

### 6.7 PostgreSQL, TimescaleDB, Redis e MariaDB GLPI

**Problema atual:** schemas por SQL solto, ausência de RLS, backups inexistentes e bancos de produtos diferentes compartilham credenciais/instância PostgreSQL.

**Ações:**

- Criar migrations versionadas e baseline do schema real.
- Separar roles e privilégios por aplicação/banco.
- Implementar RLS ou camada obrigatória equivalente para dados de tenants.
- Testar isolamento com usuários de tenants diferentes e usuário MSP.
- Reter alertas brutos por no máximo 90 dias durante o refinamento inicial; depois reduzir conforme a capacidade de promoção para incidente e a necessidade operacional comprovada.
- Reter incidentes confirmados por 12 meses. Preservar por mais tempo somente métricas agregadas sem payload sensível, se úteis para capacidade/SLO.
- Definir compressão Timescale e limpeza automatizada por classe de dado, evitando tratar alerta bruto como registro permanente.
- Definir política Redis: dados descartáveis versus persistentes; testar recuperação de filas.
- Criar dumps consistentes de PostgreSQL e MariaDB, backup de volumes e restore automatizado.
- Avaliar WAL archiving somente se o RPO aprovado exigir.
- Criar monitoramento de conexões, locks, bloat, queries lentas e crescimento.

**Critério de aceite:** restore validado, migrations reversíveis/forward-only documentadas, tenant isolation testada e alarmes de capacidade ativos.

### 6.8 Frontend React

**Problema atual:** dependências locais incompletas, ausência de testes frontend observada, componente principal grande e chamadas HTTP dispersas.

**Ações:**

- Garantir `npm ci`, lint e build reproduzíveis em Node LTS definido.
- Corrigir hooks com dependências incompletas e estados potencialmente obsoletos.
- Criar cliente API tipado e tratamento uniforme de 401/403/429/5xx.
- Adicionar testes de componentes críticos e E2E para login, troca de tenant, dashboard e incidente.
- Auditar acessibilidade, responsividade e navegação por teclado.
- Separar módulos por rota/lazy loading sem reescrita total.
- Implementar telemetria de erros sem enviar dados de clientes indevidamente.
- Tratar a PWA como primeira versão do aplicativo técnico SOC/NOC.
- Priorizar no mobile: push, fila de incidentes, detalhe, reconhecimento, atribuição, comentário e aprovação humana de ação.
- Validar segurança em dispositivos corporativos/BYOD, expiração de sessão, perda do aparelho e revogação.
- Medir adoção antes de decidir por React Native ou aplicativo nativo dedicado.

#### Matriz proposta de capacidades mobile

| Nível | Capacidades | Controles obrigatórios |
|---|---|---|
| MVP | receber push mínimo, listar/filtrar incidentes, consultar detalhe sanitizado, reconhecer, assumir para si, comentar e abrir ticket GLPI | OIDC/Auth­entik, MFA por risco, auditoria, nenhuma credencial no dispositivo e revalidação após revogação |
| Controlado | reatribuir técnico, alterar prioridade/status, registrar resolução, escalar e aprovar playbook pré-cadastrado de baixo risco | RBAC, justificativa, reautenticação, idempotência e trilha completa |
| Alto impacto | isolar host, reiniciar serviço, bloquear IP ou executar ação RMM aprovada | aprovação humana em duas etapas, allowlist, timeout, rollback e notificação imediata |
| Proibido inicialmente | shell arbitrário, script livre, acesso a segredo, ação em massa, apagar evidência ou desativar controle de segurança | fora do produto até revisão formal de risco |

O MVP e as capacidades controladas estão aprovados como direção funcional. Nenhuma ação de alto impacto está habilitada; cada ação deverá ser nomeada, modelada e aprovada separadamente antes de entrar em produção.

Para BYOD, o service worker não deve armazenar payload sensível; a notificação mostra apenas metadados mínimos e exige login para abrir o incidente. Tokens não devem ficar em `localStorage`, sessões precisam ser revogáveis e a perda do aparelho deve permitir encerramento remoto.

**Critério de aceite:** lint/build/test/E2E verdes em CI e quatro jornadas principais validadas em produção controlada.

### 6.9 Authentik, OIDC, SAML e RBAC

**Problema atual:** Authentik está apenas parcialmente funcional. Há múltiplos mecanismos de auth, segredo default no código, versões/configurações com histórico de ajustes manuais e deprovisionamento não fechado. A existência de provider/client não comprova login, logout, mapeamento de grupos ou revogação funcional.

**Baseline direta:** a inspeção de 20/08/2026 está registrada em [`infra/docs/authentik-integration-audit.md`](../infra/docs/authentik-integration-audit.md). O Hub está bloqueado por divergência de callback; GLPI, n8n e Zabbix permanecem parciais até os testes com identidades descartáveis.

**Ações:**

- Levantar o estado real diretamente em Authentik e em cada solução, registrando provider, protocolo, redirect/logout URIs, claims, grupos, segredo/certificado, sessão, fallback local e owner.
- Tornar Authentik a fonte de identidade e grupos somente após a homologação individual.
- Remover client secret default do código.
- Definir matriz de roles `admin`, `noc`, `soc`, `helpdesk`, `gestao` e tenant scope.
- Configurar MFA, duração de sessão, revogação e política de senha.
- Documentar JIT e implementar deprovisionamento/disable.
- Escolher OIDC nativo ou forward auth por aplicação; nunca ambos sem justificativa.
- Revisar e testar diretamente Hub, GLPI, n8n e Zabbix, um por vez, incluindo login, logout, expiração, revogação, desativação do usuário, mapeamento de grupos/roles e tentativa de acesso negativo.
- Classificar cada integração como `não configurada`, `parcial`, `homologada` ou `bloqueada`, anexando evidência e pendências.
- Manter uma conta break-glass local, protegida e testada trimestralmente.
- Tratar Authentik como Tier 1: backup, restore, healthcheck, alerta e runbook de indisponibilidade.

**Critério de aceite:** todas as quatro soluções estão homologadas individualmente, a matriz RBAC foi aprovada, testes de acesso negativos passam, logout é efetivo e desligar um usuário no Authentik revoga acesso dentro do SLA.

### 6.10 GLPI e ITSM

**Problema atual:** GLPI está ativo, mas DeskManager permanece no código; plugins e SSO foram alterados por scripts avulsos; porta 8085 está publicada; a coleta pelo GLPI Agent e a qualidade/conciliação do inventário ainda precisam ser comprovadas para a escala-alvo.

**Ações:**

- Remover DeskManager do fluxo, configuração e modelos após mapear tickets/dados ainda dependentes.
- Inventariar plugins, versões, licenças e necessidade real.
- Fixar imagem/versão GLPI e estabelecer processo de upgrade.
- Fechar porta 8085 e usar somente Caddy.
- Consolidar SSO, perfis, entidades, grupos, categorias e SLAs.
- Implantar o GLPI Agent por ondas, começando por um piloto representativo antes da base completa. A distribuição será feita pelo RMM já instalado em cada ativo: SuperOps, Atera ou Datto.
- Publicar a ingestão de inventário em endpoint/subdomínio técnico separado do login humano, com TLS, credencial própria, rate limit e controles de rede quando praticável.
- Definir campos mínimos do ativo: cliente/entidade, hostname, identificador estável, SO, serial, IP, usuário associado, criticidade, localização, origem e última coleta.
- Definir regra de identidade e deduplicação para reinstalação, mudança de hostname, múltiplas interfaces e ativos já presentes em Atera/Datto.
- Medir cobertura, atualização, duplicidade e falhas da coleta; reconciliar RMM e Zabbix contra a CMDB do GLPI.
- Assinar/autenticar webhooks de resolução.
- Padronizar correlação `incident_id` ↔ `ticket_id` e evitar duplicidade.
- Incluir banco, documentos e plugins no backup/restauração.

**Critério de aceite:** ticket nasce, atualiza e fecha uma única vez; permissões por entidade passam nos testes; restore GLPI completo é demonstrado; inventário atinge cobertura acordada, sem duplicidade material e com última coleta dentro do SLA.

### 6.11 n8n

**Problema atual:** workflows existem, mas não há processo formal contra drift, backup, erro global, retenção e idempotência.

**Ações:**

- Exportar workflows e credenciais por referência; nunca versionar valores secretos.
- Definir workflow global de erro e alertas de falha.
- Adicionar idempotency key aos fluxos de ticket/notificação.
- Definir retenção e limpeza de executions.
- Integrar OIDC/Auth­entik conforme D4.
- Fazer backup do volume e teste de importação dos workflows.
- Impedir edição direta sem export/PR ou registrar mudança imediatamente.

**Critério de aceite:** workflows versionados reproduzem produção, falhas alertam e retries não duplicam tickets/mensagens.

### 6.12 Evolution API e WhatsApp

**Problema atual:** imagens `latest`, Manager publicado, continuidade depende de uma integração não oficial e política de retenção não documentada.

**Ações:**

- Fechar acesso público do Manager e limitar a rede administrativa.
- Rotacionar API key e remover fallback `changeme` dos workflows.
- Fixar versão/digest e testar upgrade controlado.
- Definir retenção, backup mínimo e descarte de sessões.
- Manter como fallback somente de saída, sem dados excessivos e sem depender dele para reconhecer incidentes.
- Fazer da PWA mobile o canal técnico primário e definir fallback adicional para incidentes críticos.

**Critério de aceite:** Manager não é público, envio é auditado sem dados excessivos e existe fallback de notificação.

### 6.13 Integrações externas, IA e RMM

**Problema atual:** Atera, Datto, RocketCyber, Contabo, Gemini, MISP, Loki e outros conectores possuem níveis diferentes de maturidade.

**Ações:**

- Criar catálogo: owner, finalidade, dado enviado, credencial, SLA, rate limit, custo e status (`prod`, `piloto`, `desativado`).
- Homologar SuperOps como RMM-alvo; Datto/Atera atendem a base ainda não migrada e cada RMM distribui o GLPI Agent nos ativos sob seu controle.
- Usar o inventário coletado pelo GLPI Agent como cadastro mestre no crescimento até 5.000 endpoints; reconciliar provedor/RMM, cliente, criticidade, sistema operacional e última comunicação.
- Aplicar sanitização antes de qualquer LLM e criar testes contra vazamento.
- Registrar modelo/prompt/custo sem guardar segredo ou PII.
- Exigir TLS e timeout em todas as integrações.
- Implementar mocks e testes de contrato sem chamar produção no CI.
- Definir comportamento degradado: ingestão não pode parar porque Gemini, MISP, n8n ou WhatsApp falharam.
- Decidir se Loki é serviço real; se não, remover a integração até existir destino operacional.

**Critério de aceite:** cada conector tem owner e contrato; falha externa não perde alerta; custos e taxa de erro são observáveis.

### 6.14 Infraestrutura como código

**Problema atual:** Terraform descreve recursos além do ambiente confirmado e Ansible contém inventário, senhas e placeholders.

**Ações:**

- Separar `actual` de `future`; não planejar quatro VPS no mesmo ambiente de produção atual.
- Importar recursos existentes para state ou documentar por que ficam fora do Terraform.
- Usar backend remoto criptografado para state.
- Remover segredos de `group_vars`; usar Ansible Vault/SOPS.
- Completar ou retirar proxies placeholder.
- Criar `terraform fmt/validate/plan` e `ansible-lint/syntax-check` no CI.
- Executar Ansible em `--check` controlado e tratar drift antes de aplicar.
- Manter runbook para bootstrap de máquina vazia.

**Critério de aceite:** uma VPS descartável pode ser reconstruída sem passos secretos manuais e sem criar recursos extras inesperados.

### 6.15 CI/CD e releases

**Problema atual:** deploy inseguro, caminho errado, credencial explícita em smoke test, `rsync --delete`, sem migrations/rollback e sem aprovação de ambiente.

**Ações:**

- Revogar imediatamente a credencial exposta no workflow.
- Trocar deploy root por usuário restrito e caminho `/opt/n-infraops/app`.
- Remover `StrictHostKeyChecking=no`; fixar host key.
- Unificar CI backend duplicado.
- Pipeline: lint → type → test → security scan → build → SBOM → push por digest → deploy staging → smoke → aprovação → produção.
- Aplicar migrations com etapa explícita e backup pré-deploy.
- Implementar rollback para imagem anterior, sem `git pull` em produção.
- Proteger environment `production` no GitHub com approval.
- Adicionar smoke tests sem credenciais hardcoded.

**Critério de aceite:** deploy de uma tag é reproduzível, auditado e reversível em menos de 15 minutos.

### 6.16 Observabilidade, SLO e resposta a incidentes

**Problema atual:** healthchecks técnicos existem, mas não há SLO, métricas persistentes completas nem monitor externo do próprio monitoramento.

**Ações:**

- Definir SLIs: ingestão/min, atraso Celery, falha de webhook, criação de ticket, envio de notificação, login, latência e erro API.
- Expor métricas Prometheus ou formato compatível; manter cardinalidade controlada por tenant.
- Centralizar logs JSON, redigir segredos e definir retenção.
- Criar dashboard operacional e alertas com runbook linkado.
- Monitorar de fora das duas VPS: DNS, TLS, HTTP, webhook sintético e SSH indisponível.
- Criar severidades, escalação, post-mortem sem culpa e revisão mensal de SLO.
- Não adicionar tracing distribuído até métricas e logs básicos estarem confiáveis.

**Critério de aceite:** uma falha crítica gera alerta externo em até 5 minutos e o operador encontra causa provável/runbook em até 15 minutos.

### 6.17 Backup, DR e continuidade

**Problema atual:** não há evidência de backup operacional nas VPS.

**Ações:**

- Classificar dados por criticidade e owner.
- Criar dumps consistentes de MariaDB Zabbix, PostgreSQL e MariaDB GLPI.
- Copiar volumes necessários de Authentik, n8n, Evolution, Caddy e GLPI.
- Criptografar antes do envio; credenciais de backup não ficam na VPS monitorada quando evitável.
- Retenção sugerida: 7 diários, 5 semanais, 12 mensais; ajustar após D5.
- Testar restore mensal de amostra e trimestral completo.
- Criar runbook de perda total de cada VPS e de perda de credenciais.
- Medir RPO/RTO real em exercício.

**Critério de aceite:** restauração completa em máquina vazia dentro do RTO, com relatório e checksum.

### 6.18 Documentação e operação

**Ações:**

- Manter `as-built`, mapa arquitetural, ADRs, inventário de serviços, matriz de portas e catálogo de integrações.
- Criar runbooks: deploy, rollback, backup, restore, segredo comprometido, banco cheio, fila parada, SSO indisponível, Zabbix indisponível e provedor externo fora.
- Separar claramente “produção atual”, “roadmap” e “histórico”.
- Criar checklist de onboarding/offboarding de cliente e operador.
- Registrar evidências de testes de restore, DR, acesso e release.
- Revisão documental mensal e obrigatória após mudança de arquitetura.

**Critério de aceite:** um operador que não participou da implantação consegue executar os dez procedimentos críticos sem depender de conhecimento oral.

### 6.19 Hardening e polimento pós-implantação por aplicação

**Direção aprovada:** toda aplicação implantada terá uma rodada de hardening, estabilização e polimento imediatamente após entrar no ar, usando o checklist versionado em [`docs/execution/application-post-go-live-hardening.md`](execution/application-post-go-live-hardening.md). O trabalho inclui segurança e também qualidade funcional/operacional: coleta, cadastros, integrações, mapas, dashboards, experiência do operador, alertas e documentação. O go-live controlado não autoriza deixar falhas críticas conhecidas expostas.

**Controles mínimos antes do go-live:** TLS válido, credenciais únicas fora do Git, MFA administrativo quando suportado, portas mínimas, backup inicial, logs, healthcheck, rollback e ausência de vulnerabilidade crítica conhecida na versão implantada.

**Hardening e polimento pós-go-live:** inicia em até 24 horas e termina em até 5 dias úteis por aplicação. Abrange configuração segura, menor privilégio, headers/cookies/sessão, rate limit, isolamento de contêiner, permissões de banco, auditoria, retenção, atualização, SBOM/scan de imagem, testes negativos, revisão de exposição, qualidade dos dados, ergonomia operacional e eliminação de ruído.

**Critério de aceite:** checklist assinado, evidências anexadas, nenhum achado crítico/alto sem correção ou exceção formal com prazo, owner e controle compensatório; smoke tests, backup e rollback repetidos após o endurecimento.

### 6.20 Wazuh hub-spoke e migração dos endpoints

**Resultado:** retirar a dependência permanente da Hostinger e operar segurança em cluster Contabo escalável.

1. provisionar a Onda 1 piloto com oito VPS totais: sete Wazuh — três indexers VPS 30, um master VPS 20, dois workers VPS 30 e um edge VPS 10 — mais uma Psono VPS 10;
2. aplicar rede privada/VPN, TLS, contas nominais, firewall, versões/digests fixos, backup e observabilidade;
3. formar cluster, testar quórum, fila, ingestão, consulta e falha de nó sem agentes reais;
4. pilotar 50–100 endpoints na Onda 1, com rollback por grupo; manter a Hostinger operacional como origem/fallback e não declarar HA ou SLA;
5. aprovar o Gate Financeiro e provisionar a Onda 2 com mais um edge e um terceiro worker, chegando a dez VPS totais;
6. migrar os 624 endpoints em lotes 25 → 100 → 25% → 50% → 100%, reconciliando cada agente com CI GLPI, tenant, cliente, site e owner;
7. só classificar evento como incidente após triagem/deduplicação; alertas brutos não viram tickets automaticamente;
8. assumir SLA e retirar a Hostinger somente após edge redundante, N−1 e estabilidade de 7–14 dias na Onda 2;
9. adicionar quarto worker e substituir indexers em rolling apenas pelos gatilhos do plano de capacidade.

**Aceite Onda 1:** cluster `green`, piloto de 50–100 endpoints, zero cross-tenant, incidentes qualificados chegando ao ness.OS/GLPI e rollback demonstrado; edge único, sem HA/SLA e com Hostinger preservada. **Aceite Onda 2:** dez VPS totais, edge redundante, terceiro worker, N−1 aprovado, 98% dos 624 agentes comunicando, estabilidade de 7–14 dias e Hostinger removível sem perda operacional.

### 6.21 API Contabo e gestão do plano de controle

**Resultado:** apresentar no ness.OS a infraestrutura contratada e suas divergências, sem expor um console irrestrito do provedor.

- criar usuário/API de menor privilégio e manter credenciais somente no cofre;
- implementar adaptador backend read-only começando por `GET /v1/compute/instances`, com paginação e reconciliação; ampliar somente para os recursos oficialmente disponíveis e necessários, como snapshots, firewalls, redes privadas, Object Storage e auditoria;
- aplicar as roles/RBAC da Contabo em conjunto com a autorização server-side do ness.OS; permissão no provedor não substitui `platform_admin`, MFA ou auditoria interna;
- persistir IDs, estado e auditoria normalizados, nunca access/secret keys do S3;
- reconciliar `provider_resource` ↔ CI GLPI ↔ host Zabbix;
- produzir findings de recurso órfão, sem monitoramento, sem CI, backup vencido, firewall divergente e capacidade fora do plano;
- mostrar inventário, estado, capacidade contratada, uso observado pelo Zabbix, idade de backup, crescimento S3 e aderência às ondas;
- manter start/stop/restart/resize fora do MVP; qualquer mutação futura exigirá mudança aprovada, dupla confirmação e `platform_admin`.

**Aceite:** 100% das VPS Contabo reconciliadas ou justificadas, coleta idempotente e paginada, falha da API degradada sem apagar dados anteriores, nenhum segredo entregue ao navegador e testes negativos de autorização aprovados.

**Limites confirmados:** o Object Storage pode ser criado e redimensionado, existe no máximo um recurso por região e as regiões documentadas são Europa, US-central e Singapura. Escolher uma região primária compatível com residência, latência e custo de saída; uma segunda cópia futura precisa estar em outro domínio de falha. A API não deve retornar `secretKey` nem qualquer credencial S3 ao frontend. Não foi identificado produto/endpoint CDN na API oficial; CDN continua avaliação externa opcional e não dependência Contabo.

### 6.22 Produto AIOps, portal e painel executivo

**Resultado:** transformar dados especializados em contexto operacional e executivo sem criar outra fonte canônica.

- construir contratos de ingestão para Zabbix, Wazuh, GLPI e Contabo;
- normalizar tenant, cliente, serviço, ativo, projeto, risco, incidente, SLA e owner;
- implementar fingerprint, deduplicação, correlação temporal/topológica, enriquecimento, severidade e RCA explicável;
- manter aprovação humana para remediação; nenhuma ação destrutiva/autônoma entra no MVP;
- expor APIs versionadas, paginação, idempotência, rate limit, auditoria e estados explícitos de qualidade;
- entregar PWA por persona: executivo, cliente, Governança, Infraestrutura, Sustentação e Segurança;
- apresentar saúde, incidentes, disponibilidade, backups, projetos, catálogo, cobertura e qualidade de dados com drill-down à fonte;
- implementar jornadas BYOD, logout/revogação, push, estados offline controlados e nenhum dado sensível persistente sem necessidade;
- aplicar a baseline de marca em [`brand/ness-brand-baseline.md`](brand/ness-brand-baseline.md).

**Aceite:** nenhuma métrica demonstrativa, todos os cards com fonte/fórmula/período/atualização/qualidade, isolamento por tenant aprovado, jornadas críticas desktop/mobile E2E e incidente rastreável do sinal original ao ticket GLPI.

## 7. Roadmap faseado

### Fase 0 — Contenção e congelamento (0–48 horas)

- [ ] Congelar features e deploy automático.
- [ ] Rotacionar todas as credenciais expostas/compartilhadas.
- [ ] Remover credencial explícita do CI e bloquear workflow de produção atual.
- [ ] Criar backup emergencial consistente dos três bancos.
- [ ] Fechar portas 8082/8085 e corrigir Fail2ban.
- [ ] Nomear responsáveis e aprovar janela de manutenção.

**Gate 0:** nenhum segredo conhecido permanece válido; existe cópia emergencial verificável; borda pública mínima.

### Fase 1 — Fonte única e baseline (dias 3–10)

- [ ] Limpar/organizar repositório e resolver alterações não versionadas.
- [ ] Corrigir compilação backend e bootstrap frontend.
- [ ] Consolidar Compose e Caddy reais.
- [ ] Priorizar GLPI com Governança: criar catálogo inicial de 10–20 serviços, owners, SLA/OLA, grupos resolvedores e modelos de incidente/requisição/problema/mudança.
- [ ] Validar o módulo Projetos do GLPI Community e pilotar o portfólio com até cinco projetos reais, usando a taxonomia e os critérios de aceite de [`docs/specs/ti-project-portfolio.md`](specs/ti-project-portfolio.md).
- [ ] Configurar a biblioteca operacional no GLPI, definir taxonomia/metadados e publicar um piloto de runbooks Ness/cliente conforme [`docs/specs/operational-runbook-library.md`](specs/operational-runbook-library.md).
- [ ] Criar catálogo de integrações e segredos.
- [ ] Consolidar decisões D1–D18 e ADRs aplicáveis.
- [ ] Marcar release baseline.
- [ ] Pilotar o GLPI Agent distribuído por SuperOps/Atera/Datto, definir identidade/deduplicação e preparar a matriz mestra para crescimento até 5.000 endpoints.
- [ ] Antes do Geomap Zabbix, sanear entidades/localizações GLPI: a baseline encontrou 239 ativos sem localização/serial/inventário e sete agentes sem contato recente ou vínculo.
- [ ] Instrumentar Zabbix/Hub e coletar 30 dias próprios de volume médio/pico e severidade; a plataforma anterior não oferece exportação utilizável.
- [ ] Inventariar os indicadores existentes, retirar números demonstrativos e iniciar a baseline de qualidade/proveniência conforme o contrato executivo.
- [ ] Entregar o primeiro painel executivo de baseline, ainda que contenha estados explícitos `unavailable`, sem scores ou metas não homologados.
- [ ] Iniciar polimento lógico pré-migração do Zabbix: itens não suportados, triggers desconhecidos, objetos obsoletos, grupos, templates, macros, localização e ruído.
- [ ] Permitir a transmutação Zabbix isolada em paralelo, mas bloquear o cutover até a baseline GLPI de serviços/owners/localizações e o polimento lógico pré-migração terem evidência aprovada.

**Gate 1:** checkout limpo reproduz validações e descreve exatamente produção; a baseline GLPI e os critérios de polimento que liberam o cutover Zabbix estão aprovados.

### Fase 2 — Recuperação e infraestrutura (semanas 2–3)

- [ ] Backup automatizado externo e restore testado.
- [ ] Hardening das duas VPS.
- [ ] Imagens fixadas, redes segmentadas e portas fechadas.
- [ ] Terraform/Ansible alinhados ao real.
- [ ] Monitor externo mínimo.
- [ ] Provisionar VPS dedicada para o cofre Community e executar PoC Psono; não compartilhar com phishing ou aplicações operacionais.
- [ ] Usar a Hostinger KVM8 já preparada somente para testar restauração/transmutação saneada e produzir pacote reproduzível; provisionar uma nova VPS Contabo permanente como Zabbix definitivo e executar um único cutover produtivo, preservando a origem por 7–14 dias. Depois do aceite, reinstalar e reutilizar a VPS antiga no piloto Wazuh. Capacidade e sequência em [`vps-capacity-and-sequencing-plan.md`](vps-capacity-and-sequencing-plan.md) e roteiro em [`execution/zabbix-transmutation-kvm8-plan.md`](execution/zabbix-transmutation-kvm8-plan.md).

**Gate 2:** cada VPS pode ser perdida e recuperada dentro do RTO aprovado.

### Fase 3 — Plataforma e segurança de aplicação (semanas 3–5)

- [ ] Authentik/RBAC revisados e homologados diretamente em Hub, GLPI, n8n e Zabbix.
- [ ] Tenant isolation implementado e testado.
- [ ] Migrations Alembic e roles de banco.
- [ ] Webhooks, SSE e APIs endurecidos.
- [ ] Pipeline idempotente e comportamento degradado testado.
- [ ] Migrar Zabbix para a VPS limpa e observar por 7–14 dias; preservar a antiga até aceite.

**Gate 3:** testes negativos de acesso/tenant passam e nenhuma dependência externa bloqueia ingestão.

### Fase 4 — Fechamento funcional (semanas 5–7)

- [ ] ITSM e RMM canônicos definidos.
- [ ] Fluxo incidente → ticket → notificação → resolução → post-mortem validado ponta a ponta.
- [ ] Frontend com jornadas E2E.
- [ ] PWA mobile com jornadas técnicas e push validados nos dispositivos-alvo.
- [ ] n8n versionado e sem duplicidade.
- [ ] Integrações experimentais desabilitadas.
- [ ] Painel executivo por persona/tenant com dados reais de Governança, Infraestrutura e Sustentação, fonte/atualização/qualidade e drill-down.
- [ ] Visão de portfólio com projetos on-track, em risco, atrasados, bloqueados, marcos próximos/vencidos e atualização pendente, sem confundir projeto com tarefas técnicas.

**Gate 4:** operação NOC completa funciona em teste controlado e possui rollback/runbook.

### Fase 4.1 — Hardening e polimento pós-go-live por aplicação

- [ ] Abrir uma mudança de hardening e polimento para cada aplicação promovida.
- [ ] Executar o checklist em até 24 horas do go-live e concluir em até 5 dias úteis.
- [ ] Priorizar Authentik, Psono, Hub/API, GLPI, Zabbix, Node-RED e o fallback de mensageria pela superfície e privilégio.
- [ ] Repetir scan, testes negativos, backup, restore mínimo, smoke e rollback após as alterações.
- [ ] Bloquear novas funcionalidades na aplicação enquanto houver achado crítico/alto sem tratamento aprovado.

**Gate 4.1:** todas as aplicações em produção têm baseline endurecida, coleta/cadastros/experiência operacional revisados, evidências e backlog residual com owner e prazo.

### Fase 5 — Observabilidade e otimização (semanas 7–9)

- [ ] SLOs, indicadores executivos, dashboards e alertas refinados com tendência e metas homologadas.
- [ ] Retenção/tuning de bancos e filas.
- [ ] Teste de carga baseado no volume real.
- [ ] Otimização de custos de IA e armazenamento.
- [ ] Exercício de incidente e DR.

**Gate 5:** SLO medido por duas semanas, sem alerta crítico sem runbook.

### Fase 6 — Release integrada do núcleo (semanas 9–12)

- [ ] Entregar adaptadores Zabbix e GLPI, modelo comum e primeiro painel executivo real.
- [ ] Entregar portfólio de projetos, catálogo e runbooks no GLPI com visibilidade no ness.OS.
- [ ] Implementar coletor read-only da API Contabo e reconciliação VPS ↔ GLPI ↔ Zabbix.
- [ ] Homologar PWA desktop/mobile com as seis personas e `platform_admin` restrito.
- [ ] Executar pentest/revisão do escopo web e API exposto.
- [ ] UAT com NOC, Sustentação, Governança e gestão.

**Gate 6:** produto núcleo rastreia dados reais até a fonte, passa isolamento por tenant e pode ser recuperado dentro do RTO.

### Fase 7A — Wazuh Onda 1 piloto (semanas 12–14)

- [ ] Autorizar e provisionar oito VPS totais: sete Wazuh e uma Psono Community dedicada.
- [ ] Implantar cluster, rede privada, edge único, backup, observabilidade e hardening.
- [ ] Pilotar 50–100 endpoints com rollback e reconciliação GLPI.
- [ ] Integrar incidentes qualificados ao AIOps/GLPI e publicar visão de Segurança.
- [ ] Manter a Hostinger operacional; não declarar HA nem SLA nesta onda.

**Gate 7A:** cluster piloto `green`, isolamento por tenant, ingestão/incidente/rollback aprovados e Hostinger preservada como fallback.

### Fase 7B — Wazuh Onda 2 e saída da Hostinger (semanas 14–16)

- [ ] Aprovar a BOM consolidada no Gate Financeiro e provisionar segundo edge e terceiro worker, chegando a dez VPS totais.
- [ ] Migrar os 624 endpoints por lotes 25 → 100 → 25% → 50% → 100%, com rollback e reconciliação GLPI.
- [ ] Validar edge redundante, N−1, cobertura mínima de 98%, capacidade e SLO.
- [ ] Observar por 7–14 dias e somente então retirar a Hostinger.

**Gate 7B:** dez VPS totais, HA/N−1 aprovados, 98% dos 624 agentes comunicando, zero cross-tenant e Hostinger removível sem perda operacional.

### Fase 8 — Aceite e transição operacional (semanas 16–18)

- [ ] Treinamento, escalação, plantão e exercícios de incidente/DR.
- [ ] Release de produção, freeze de estabilização e hardening/polimento final.
- [ ] Aprovar dashboards executivos, catálogo, projetos, runbooks e relatórios de saúde.
- [ ] Demonstrar restore, rollback, revogação de acesso e operação sem o executor original.
- [ ] Registrar backlog residual, riscos aceitos, custos reais e plano de melhoria trimestral.

**Gate final:** aceite assinado, SLO medido, responsáveis em plantão, documentação publicada e nenhuma dependência crítica sem owner/recuperação.

### Fase 9 — Escala acionada por demanda

Não possui data fixa depois da Onda 2 de produção. A Onda 3 adiciona o quarto worker até aproximadamente 3.750 endpoints; a Onda 4 mantém 11 VPS e troca indexers em rolling somente se necessário para chegar a 5.000. Os gatilhos são 70% da faixa, previsão de 80% em 90 dias, p95 sustentado, fila/backpressure, SLO do indexer ou falha no teste N−1.

## 8. Ordem de prioridade do backlog

### P0 — iniciar imediatamente

1. Rotação/remoção de segredos e senha root compartilhada.
2. Backup emergencial e teste de leitura do dump.
3. Desativação do deploy inseguro.
4. Fail2ban, portas 8082/8085 e SSH administrativo.
5. GLPI prioritário: estabilização, catálogo de serviços com Governança e piloto do GLPI Agent.
6. Polimento lógico pré-migração do Zabbix.

### P1 — concluir antes de novas features

1. Repositório limpo e release baseline.
2. CI/CD reproduzível e rollback.
3. Build/lint/type/test completos.
4. Alembic, backup automático e restore.
5. RBAC/tenant isolation.
6. Imagens fixadas e redes segmentadas.

### P2 — estabilização operacional

1. SLOs e observabilidade.
2. E2E e testes de contrato.
3. Catálogo de integrações e comportamento degradado.
4. Tuning baseado em métricas reais.
5. DR e treinamento.

### P3 — somente após Gate 4

1. Wazuh Hub/Spokes.
2. Alta disponibilidade multi-VPS.
3. Novos RMMs/provedores.
4. SOAR/remediação automática ampliada.
5. Novas experiências de IA.

## 9. Indicadores de conclusão

| Dimensão | Meta mínima |
|---|---|
| Segredos | zero segredo válido no Git/scans; 100% com owner e rotação |
| Build | backend e frontend verdes a partir de checkout limpo |
| Testes | 100% das jornadas críticas E2E; tenant negative tests obrigatórios |
| Deploy | rollback comprovado em até 15 min |
| Backup | 100% dos bancos com backup diário; restore trimestral completo |
| Disponibilidade | SLO D10 medido e publicado |
| Incidentes | alerta crítico externo em até 5 min; runbook vinculado |
| Segurança | zero porta não aprovada; zero root SSH por senha |
| Documentação | 100% dos serviços com owner, runbook e dependências |
| Integrações | 100% classificadas como prod/piloto/desativado |
| Capacidade | primeira onda validada até aproximadamente 1.000 endpoints; plano e gatilhos aprovados para crescimento até 5.000 e cinco operadores |
| Indicadores | 100% dos cards executivos com fonte, fórmula, período, atualização, qualidade, owner e drill-down; zero valor demonstrativo tratado como real |
| Cobertura de gestão | ao menos Governança, Infraestrutura e Sustentação com indicador homologado na primeira versão; Projetos e Segurança nunca simulados enquanto a fonte estiver pendente |
| Projetos | 100% dos projetos ativos com sponsor, gerente, tenant/entidade, serviço relacionado, prazo, estado, saúde justificada, próximo marco e atualização dentro da cadência |
| Conhecimento operacional | 100% dos serviços críticos e alertas críticos com runbook vigente, owner, última validação e vínculo à política oficial quando aplicável; zero runbook vencido apresentado como válido |

## 10. Equipe mínima sugerida

| Papel | Responsabilidade |
|---|---|
| Sponsor/PO | decisões D1–D18, orçamento, aceite e prioridades |
| Platform/SRE | VPS, Docker, CI/CD, backup, observabilidade e DR |
| Backend | API, Celery, dados, migrations e integrações |
| Frontend | jornadas, OIDC, qualidade e E2E |
| Segurança | segredos, hardening, RBAC, tenant isolation e pentest |
| Operações NOC/Helpdesk | regras Zabbix, GLPI, UAT, runbooks e plantão |

Uma pessoa pode acumular papéis, mas cada responsabilidade precisa de um nome e substituto.

### Grupo nominal inicial

| Pessoa | Papel inicial | Próxima definição necessária |
|---|---|---|
| Ricardo Esper | owner, aprovador e administrador principal | separar conta diária de conta break-glass |
| Rogério Salerno | administrador nominal | definir os domínios administrativos e retirar superadmin do uso cotidiano |
| Ismael Araujo | administrador nominal | definir os domínios administrativos e retirar superadmin do uso cotidiano |
| Agnaldo Silva | operador em observação | manter sem `platform_admin`; definir domínio operacional depois da observação |

`platform_admin` não significa conta compartilhada nem superadmin cotidiano. Ricardo, Rogério e Ismael terão contas nominais, MFA e privilégios por domínio; pelo menos dois serão treinados e autorizados para restore e resposta de emergência. Agnaldo não integra esse grupo.

Identidade confirmada em 20/08/2026: Agnaldo usa `agsilva` / `agsilva@ness.com.br`. A conta `asilva` pertence a André Silva e não deve ser alterada como parte do provisionamento de Agnaldo. Durante a observação, `agsilva` permanece sem privilégio global: no Zabbix está em `Zabbix administrators` com `User role`; no Authentik está nos grupos `noc`, `gestao` e `usuarios`.

## 11. Primeiras respostas solicitadas

As respostas operacionais foram incorporadas. Permanecem necessárias:

1. Qual cliente/tenant e quais 50–100 endpoints formarão o piloto integrado GLPI Agent + Zabbix + Wazuh?
2. Quem será o responsável nominal de execução para Platform/SRE, aplicações/API, frontend, Governança/GLPI e Segurança/SOC?
3. Logs de auditoria de ações humanas seguirão 12 meses ou prazo diferente?
4. Qual domínio e SMTP serão reservados ao Psono?
5. Quando será contratado o Contabo Object Storage e criado o usuário read-only da API Contabo?
6. Qual cadência executiva será adotada: semanal recomendada ou quinzenal?

Já aprovados: quatro identidades descartáveis para homologação SSO e endpoint/subdomínio técnico separado para o GLPI Agent.

A auditoria inicial de licenças e reprodutibilidade está em [`docs/execution/open-source-license-audit-2026-08-20.md`](execution/open-source-license-audit-2026-08-20.md). Ela inclui a saída de Redis, TimescaleDB Community, n8n e Evolution, além do pin de todas as imagens por digest.

## 12. Cenários de custo e Gate Financeiro

Os valores serão cotados para SuperOps e os demais componentes, respeitando o teto total de **EUR 2.000/mês**. Wazuh entra progressivamente: oito VPS totais na Onda 1 piloto (sete Wazuh + uma Psono), 10 na Onda 2 de produção e teto de 11; MISP permanece fora até decisão própria.

| Cenário | Composição | Benefício | Limitação |
|---|---|---|---|
| Mínimo | duas VPS atuais, Object Storage, backup diário, monitor externo básico e PWA no Hub existente | menor custo incremental; atende RPO/RTO inicial se restore for eficiente | sem staging dedicado e com maior risco durante mudanças |
| Recomendado | mínimo + VPS pequena de staging/monitor fora de produção + segunda cópia de backup em domínio de falha diferente | valida releases, restore e monitoramento sem afetar produção | custo recorrente adicional moderado |
| Ideal | recomendado + standby AIOps, backup em segundo provedor, observabilidade dedicada e capacidade reservada para a etapa SOC | menor RTO e melhor isolamento de falhas | deve permanecer dentro do teto de EUR 2.000/mês; reduzir escopo se licenças consumirem a reserva |

Para cada cenário serão levantados: custo mensal, setup, licenças RMM, armazenamento, tráfego, retenção, suporte e custo de operação humana.

**Gate Financeiro:** antes de contratar a Onda 1 e novamente antes da Onda 2, aprovar uma BOM cotada e datada com VPS, Object Storage, RMM, IA, tráfego, monitoramento e operação, incluindo margem de crescimento. A soma mensal projetada deve permanecer em até EUR 2.000; sem cotação consolidada e owner financeiro, não há compra.

A composição e os preços públicos de referência estão em [`contabo-bom-gate-2026-08-22.md`](contabo-bom-gate-2026-08-22.md). Como a página pública ao vivo não pôde ser validada pelo coletor, o documento não substitui cotação no carrinho/conta e mantém o Gate em `NO-GO` até os custos omitidos e impostos serem consolidados.

## 13. Próximo marco

Com a aprovação do plano, iniciar a Fase 0 usando [`docs/execution/gate-0-checklist.md`](execution/gate-0-checklist.md) e converter as fases seguintes em:

- ADRs das decisões aprovadas;
- cronograma com datas, owners e dependências;
- backlog executável por fase;
- checklist do Gate 0;
- matriz de riscos e aceite;
- painel semanal de avanço.

A aprovação do plano não elimina os controles por mudança: backup, responsável, avaliação de impacto, janela quando aplicável, validação e rollback continuam obrigatórios.

## 14. Estrutura analítica do projeto

| WP | Pacote de trabalho | Estado inicial | Dependência principal | Entrega/saída |
|---|---|---|---|---|
| WP00 | Gate 0, incidente, segredos e recuperação | em andamento | nenhuma | backups/restore, contenção, acessos nominais e borda segura |
| WP01 | Governança do projeto no GLPI | preparado | WP00 | projeto, tarefas, marcos, riscos, decisões e status semanal |
| WP02 | Psono + SOPS/age + Object Storage | bloqueado externamente | WP00 | cofre recuperável e backups externos S3 |
| WP03 | Reconstrução e polimento Zabbix | em andamento | WP00, WP02; cutover após baseline WP06 | Zabbix limpo, restaurado, reconciliado e operável |
| WP04 | Authentik, RBAC e tenants | parcial | WP00 | SSO/MFA por aplicação e `platform_admin` restrito |
| WP05 | Fundação Contabo/IaC | planejado | WP02, WP04 | VPS, rede, firewall, DNS, TLS, inventário e baseline automatizados |
| WP06 | GLPI/CMDB/catálogo/projetos/runbooks | em andamento | WP04 | fontes canônicas de governança homologadas |
| WP07 | Backend AIOps e integrações | parcial | WP03, WP04, WP06 | ingestão, modelo comum, correlação, incidentes e APIs |
| WP08 | Portal/PWA e indicadores executivos | parcial | WP07 | jornadas por persona, projetos, saúde e drill-down |
| WP09 | Portal/API Contabo | especificado | WP05, WP07 | inventário/reconciliação/finding read-only no ness.OS |
| WP10 | Wazuh Ondas 1–2 e migração | planejado | WP05, WP07, Gate Financeiro | Onda 1 piloto; Onda 2 HA, 624 endpoints migrados e Hostinger removível |
| WP11 | Observabilidade, SLO, DR e hardening | parcial | WP02–WP10 | SLO medido, restore/rollback, pentest e polimento por aplicação |
| WP12 | UAT, treinamento e transição | pendente | WP11 | aceite, plantão, operação assistida e backlog residual |

Cada WP será um projeto ou conjunto de tarefas no GLPI, com código idempotente, owner, data, dependência, evidência e critério de saída. GitHub controla código; GLPI controla execução gerencial; ness.OS consolida o status.

## 15. Marcos de controle

| Marco | Evidência obrigatória |
|---|---|
| M0 — Gate 0 encerrado | restore Zabbix e AIOps, cópia S3, acessos e incidente documentados |
| M1 — Fundação recuperável | Psono/SOPS, IaC, rede, backup e monitor externo |
| M2 — Zabbix estabilizado | cutover aceito, sete dias estáveis, mapas/coleta/backlog com owner |
| M3 — Governança operacional | catálogo, CMDB, cinco projetos e dez runbooks piloto |
| M4 — Núcleo AIOps | sinal Zabbix → incidente qualificado → GLPI → painel, com tenant testado |
| M5 — Portal/Contabo | PWA por persona e recursos Contabo reconciliados |
| M6 — Segurança integrada | Onda 1 piloto aprovada; Onda 2 com dez VPS, HA/N−1, 624 endpoints, incidentes no portal e Hostinger removível |
| M7 — Go-live | UAT, pentest, DR, SLO, treinamento, aceite e operação assistida |

## 16. RACI inicial

`A` aprova, `R` executa/responde, `C` é consultado e `I` informado. `TBD` é uma pendência de staffing, não autorização implícita.

| Domínio | A | R | C | I |
|---|---|---|---|---|
| Prioridade, orçamento e go-live | Ricardo Esper | Ricardo Esper | Rogério, Ismael | Agnaldo/equipes |
| Administração global ness.OS | Ricardo Esper | Ricardo, Rogério, Ismael | Segurança | Agnaldo |
| Infraestrutura, backup e Zabbix | Ricardo Esper | Platform/SRE `TBD` | Rogério, Ismael | Operação |
| GLPI, catálogo, projetos e runbooks | Ricardo Esper | Governança/GLPI `TBD` | Ismael, Agnaldo | Stakeholders |
| Backend AIOps e API Contabo | Ricardo Esper | Aplicações/API `TBD` | Platform/SRE, Segurança | Operação |
| Portal/PWA e indicadores | Ricardo Esper | Frontend/Produto `TBD` | Governança, NOC/SOC | Stakeholders/clientes piloto |
| Wazuh e resposta de segurança | Ricardo Esper | Segurança/SOC `TBD` | Ismael, Platform/SRE | Operação |
| Pentest, risco e exceções | Ricardo Esper | Segurança `TBD` | owners técnicos | Stakeholders afetados |

## 17. Governança e cadência

- atualização operacional: diária durante mudanças/cutovers;
- reunião de entrega: semanal, 30 minutos, baseada em marcos, riscos e decisões;
- steering executivo: quinzenal ou quando custo/escopo/SLO mudar;
- demonstração: ao final de cada Gate, sempre com evidência real;
- risco crítico ou incidente: comunicação imediata e freeze proporcional;
- relatório: avanço por WP, próximos marcos, bloqueios, consumo mensal, SLO, qualidade de dados e decisões necessárias.

Mudança de escopo, aumento do teto de 11 VPS, nova dependência proprietária, ação autônoma de remediação ou novo `platform_admin` exigem aprovação explícita de Ricardo Esper e registro arquitetural.

## 18. Quadro mestre de execução

Este quadro é o ponto único de acompanhamento. O detalhe permanece nos WPs e documentos especializados acima; não se abre uma trilha paralela. Cada linha vira projeto/marco no GLPI e referencia evidência no Git.

| Ordem | Pacotes | Entrega operacional | Estado inicial | Próxima ação objetiva | Dependência/bloqueio | Saída obrigatória |
|---:|---|---|---|---|---|---|
| 1 | WP00 | Gate 0 e recuperação comprovada | em andamento | preservar restores aprovados e publicar/provar a cópia externa Restic/S3 | Object Storage real: endpoint HTTPS, bucket, access key, secret key e senha Restic | M0: restore, checksum, cópia externa, acessos e incidente documentados |
| 2 | WP01–WP02 | governança do projeto, cofre e segredos | preparado/bloqueado | abrir os 13 WPs no GLPI; provisionar VPS dedicada e executar PoC Psono + SOPS/age | owner técnico; domínio/SMTP do Psono; terceira VPS | M1: dois responsáveis recuperam o cofre e o ambiente nasce de IaC |
| 3 | WP04 + WP06 | identidade, GLPI e governança operacionais | parcial/em andamento | homologar Authentik por aplicação; estabilizar GLPI; pilotar 10–20 serviços, cinco projetos, 8–12 runbooks e GLPI Agent | identidades de teste; owners de Governança; tenant/endpoints piloto | baseline GLPI libera o cutover Zabbix; M3 consolida SSO/RBAC, catálogo/CMDB/projetos/runbooks |
| 4 | WP03 | Zabbix reconstruído e polido | em andamento em paralelo | terminar transmutação isolada na KVM8; contratar/provisionar nova Contabo permanente, restaurar e observar 7–14 dias | Gate 0; baseline WP06; nova VPS Contabo aprovada e pendente de contratação | M2: coleta, proxies, mapas/localização, backup, ruído e rollback aceitos |
| 5 | WP07 | núcleo AIOps e integrações confiáveis | parcial | tornar ingestão idempotente, normalizar sinais Zabbix/GLPI, qualificar incidente e provar fluxo até ticket | M2–M3; contratos e owners das integrações | M4: sinal → incidente → GLPI, com deduplicação, tenant e degradação testados |
| 6 | WP08–WP09 | portal/PWA, painel executivo e visão Contabo | especificado/parcial | publicar indicadores reais; implementar Contabo read-only e reconciliar VPS ↔ GLPI ↔ Zabbix | conta API de menor privilégio; qualidade das fontes | M5: personas/tenants testados, 100% das VPS justificadas e nenhum segredo no browser |
| 7 | WP10 | Wazuh hub-spoke Ondas 1–2 | planejado | após Gate 6/Financeiro, provisionar oito VPS totais e pilotar 50–100 endpoints; depois adicionar edge/worker, migrar 624 e observar antes de retirar Hostinger | núcleo aceito; BOM ≤ EUR 2.000; owner SOC; tenant/endpoints piloto e medição APS/EPS | M6: Onda 1 sem HA aprovada; Onda 2 com dez VPS, N−1, ≥98%, zero cross-tenant e Hostinger removível |
| 8 | WP11–WP12 | operação, hardening e go-live | parcial/pendente | medir SLO, executar DR/pentest/UAT, treinar substitutos e concluir polimento de cada aplicação | todos os WPs anteriores | M7: aceite, plantão, RTO/RPO, rollback e operação sem dependência do executor original |

### 18.1 Regra de execução de cada item

Um item só muda para `concluído` quando possui: owner nominal, mudança/ticket GLPI, configuração ou código versionado, segredo fora do Git, teste positivo e negativo proporcional ao risco, backup/rollback, evidência com data e critério de aceite aprovado. `Em execução` sem owner ou evidência volta para `bloqueado`.

### 18.2 Compras e escala

- compra imediata mínima: Object Storage e uma VPS dedicada ao Psono; nenhum outro componente novo compartilha a VPS do cofre;
- Zabbix e AIOps atuais permanecem contabilizados; Hostinger Wazuh e KVM8 são transitórias e valem zero na capacidade permanente;
- Wazuh inicia com oito VPS totais na Onda 1 (sete Wazuh + uma Psono), sem HA/SLA e mantendo a Hostinger; chega a 10 na Onda 2 para edge redundante, terceiro worker e retirada da Hostinger após estabilidade; o teto é 11;
- CDN não entra na compra-base: o owner deve registrar baseline e comparação antes/depois em conteúdo estático representativo, cobrindo p95, cache-hit, banda, segurança e custo; sem ganho mensurável aprovado, o piloto termina sem implantação;
- o custo mensal consolidado — VPS, Object Storage, RMM, IA, tráfego, monitoramento e operação — deve permanecer em até EUR 2.000; qualquer projeção que ultrapasse o teto volta ao steering antes da contratação.

### 18.3 Bloqueios que exigem decisão ou insumo

| Bloqueio | Quem decide/fornece | Efeito até resolver |
|---|---|---|
| Object Storage, região e credenciais exclusivas | Ricardo Esper / administrador Contabo | Gate 0 não encerra e backups permanecem sem cópia externa comprovada |
| owners Platform/SRE, Aplicações/API, Frontend/Produto, Governança/GLPI e Segurança/SOC | Ricardo Esper | respectivos WPs não podem sair de `preparado` para compromisso de prazo |
| tenant e 50–100 endpoints do piloto integrado | Operação + Governança + Segurança | GLPI Agent/Wazuh e testes de isolamento não avançam para produção |
| BOM cotada das Ondas 1 e 2, com total mensal consolidado | Ricardo Esper / owner financeiro `TBD` | nenhuma onda Wazuh é contratada e o teto de EUR 2.000 não pode ser considerado comprovado |
| domínio e SMTP do Psono | Platform/SRE + Ricardo Esper | PoC do cofre não pode ser promovido |
| retenção de auditoria humana e cadência executiva | Ricardo Esper + Governança | storage, relatórios e revisão de acesso permanecem provisórios |

Nenhum bloqueio autoriza indicador simulado, credencial inventada, compra antecipada ou ampliação de privilégio. A administração global permanece exclusivamente com contas nominais e MFA de **Ricardo Esper, Ismael Araujo e Rogério Salerno**.
