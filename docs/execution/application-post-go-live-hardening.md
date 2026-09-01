# Checklist de hardening e polimento pós-go-live por aplicação

> Aplicação:
> Versão/digest:
> Owner:
> Data do go-live:
> Início do hardening:
> Prazo: go-live + 5 dias úteis
> Mudança/rollback:

## Regra de entrada

O hardening e o polimento aprofundados acontecem depois que a aplicação está funcional em produção controlada. O objetivo não é apenas segurança: inclui estabilizar coleta, dados, integrações, telas, mapas, dashboards, alertas, runbooks e experiência do operador. Antes do go-live continuam obrigatórios: TLS válido, credenciais únicas e não versionadas, MFA administrativo quando suportado, exposição mínima, backup inicial, healthcheck, logging e rollback. Uma vulnerabilidade crítica conhecida bloqueia o go-live.

## 1. Inventário e superfície

- [ ] Registrar versão, digest da imagem, licença open source, repositório upstream e data de fim de suporte.
- [ ] Enumerar portas, rotas públicas, jobs, webhooks, integrações, bancos, volumes e contas de serviço.
- [ ] Confirmar que portas administrativas e bancos não estão publicados diretamente.
- [ ] Remover endpoints de debug, exemplos, instaladores, usuários padrão e funcionalidades não utilizadas.
- [ ] Gerar SBOM e executar scan de imagem/dependências; registrar CVEs e decisão de tratamento.

## 2. Identidade, sessão e autorização

- [ ] Integrar ao Authentik quando homologado; manter break-glass local exclusivo e auditado.
- [ ] Exigir MFA para administradores e acessos sensíveis.
- [ ] Aplicar menor privilégio a roles, grupos, tokens, contas de serviço e permissões por tenant/cliente.
- [ ] Testar usuário comum, administrador limitado, usuário sem grupo, usuário desativado e tentativa cross-tenant.
- [ ] Revisar duração, revogação, logout, rotação, cookies `Secure`/`HttpOnly`/`SameSite` e proteção CSRF.

## 3. Segredos e criptografia

- [ ] Migrar credenciais humanas para Psono Community e automação para SOPS/age.
- [ ] Remover defaults e falhar o startup quando segredo obrigatório estiver ausente.
- [ ] Separar credenciais por aplicação/ambiente e definir owner, criação, expiração e rotação.
- [ ] Validar TLS de saída e entrada; eliminar `verify=false`, certificados autoassinados não controlados e cifras obsoletas.
- [ ] Confirmar que logs, erros, traces e backups não revelam tokens ou payload sensível.

## 4. Runtime, contêiner e sistema operacional

- [ ] Executar como usuário não root quando suportado, com filesystem somente leitura e volumes explicitamente necessários.
- [ ] Aplicar `no-new-privileges`, capabilities mínimas, limites de CPU/memória/PIDs e healthcheck.
- [ ] Fixar imagens por versão/digest e definir rotina de atualização/rollback.
- [ ] Segmentar redes; permitir comunicação somente entre consumidores e dependências necessários.
- [ ] Revisar permissões de arquivos, volumes, sockets e diretórios temporários.

## 5. Aplicação, API e dados

- [ ] Configurar headers de segurança, CORS por allowlist, limites de upload/body e rate limiting.
- [ ] Validar entrada, saída, serialização, tratamento de erro e ausência de stack trace público.
- [ ] Proteger webhooks com assinatura, timestamp, replay window e idempotência.
- [ ] Aplicar conta de banco exclusiva, schema/privilegios mínimos, migrations controladas e conexões TLS quando cabível.
- [ ] Validar isolamento de cliente, retenção, anonimização/redação e exclusão conforme política.

## 6. Auditoria, detecção e resposta

- [ ] Registrar login, falha, elevação, mudança de configuração, acesso a segredo e ação de alto impacto.
- [ ] Enviar logs estruturados ao destino aprovado, com relógio sincronizado e retenção definida.
- [ ] Criar métricas/alertas para indisponibilidade, erro, latência, fila, capacidade e falhas de autenticação.
- [ ] Vincular alertas a runbook, owner e escalação; testar pelo menos um evento sintético.
- [ ] Definir procedimento de comprometimento, revogação, coleta de evidência e reconstrução.

## 7. Controles específicos

- [ ] **Zabbix:** scripts globais, roles, proxies, porta 10051, itens não suportados, ações internas, macros secretas, templates, qualidade da coleta, inventário, localização, mapas, dashboards e ruído de alertas.
- [ ] **Authentik:** flows, providers, redirect/logout URIs, claims, recovery, MFA, tokens, branding, jornada de login e mensagens de erro.
- [ ] **Psono Community:** chaves estáveis do servidor, recovery/emergency codes, MFA, SMTP, grupos, onboarding, revogação e restore em host vazio.
- [ ] **Hub/API/PWA:** OIDC+PKCE/BFF, JWT, SSE, service worker/cache BYOD, autorização por rota/tenant, responsividade, acessibilidade e jornadas do operador.
- [ ] **GLPI:** instalador/debug, entidades/perfis, API, inventário, uploads/plugins, tarefas agendadas, regras de importação, deduplicação e formulários/filas.
- [ ] **n8n:** editor não público, encryption key, credenciais, execução de código, webhooks, retenção, nomes/pastas, tratamento de erro e idempotência visualmente verificável.
- [ ] **Evolution:** Manager privado, API key, sessões, webhooks, mídia, logs, retenção, contatos/canais e mensagens de fallback.

## 8. Qualidade operacional e polimento

- [ ] Definir objetivo mensurável de qualidade para dados, coleta, erro, latência e ruído da aplicação.
- [ ] Padronizar nomes, tags, grupos, owners, descrições, ícones, cores e links para runbooks.
- [ ] Revisar telas, dashboards, mapas, filtros, buscas, estados vazios, erros e jornadas mobile/desktop com operadores reais.
- [ ] Remover dados de demonstração, duplicidades, cadastros órfãos, integrações inativas e alertas sem ação possível.
- [ ] Registrar melhorias restantes como backlog priorizado; polimento não pode virar uma fase sem critério de saída.

### 8.1 Trilha obrigatória para Zabbix

- [ ] Definir taxonomia única de grupos e tags: `cliente`, `site`, `servico`, `ambiente`, `tecnologia`, `scope` e `owner`.
- [ ] Usar o GLPI como fonte canônica de ativo, cliente, site, endereço e coordenadas; sincronizar ao Zabbix sem criar edição concorrente.
- [ ] Habilitar/revisar inventário por host e preencher nome visível, tipo, modelo, serial, sistema, contato, site, endereço, `location_lat` e `location_lon` conforme aplicável.
- [ ] Ligar itens ao inventário automático somente para atributos técnicos coletáveis; não sobrescrever dados de negócio vindos do GLPI.
- [ ] Criar Geomap executivo por cliente/site usando latitude/longitude do inventário e filtros por grupo/tag.
- [ ] Criar mapas de rede por cliente/site com links, dependências e status; evitar um mapa único ilegível com todos os ativos.
- [ ] Criar dashboards por função: NOC geral, cliente, capacidade, disponibilidade, proxies/coleta e qualidade da monitoração.
- [ ] Versionar e revisar templates/macros; eliminar chaves/OIDs inválidos e itens duplicados antes de aumentar pollers.
- [ ] Reduzir itens ativos não suportados para menos de 0,5% do total, sem host com dezenas de falhas não justificadas; toda exceção recebe owner e prazo.
- [ ] Eliminar triggers `unknown` persistentes por mais de 24 horas fora de manutenção ou registrar exceção técnica.
- [ ] Revisar dependências, correlação, manutenção, severidade, tags e ações para que cada alerta tenha destinatário e resposta definida.
- [ ] Medir precisão: incidentes úteis, falso positivo, alerta duplicado, tempo até reconhecimento e ativos sem dados recentes.

## 9. Verificação e aceite

- [ ] Executar smoke tests e testes negativos depois do hardening.
- [ ] Confirmar backup posterior, leitura/checksum e restore mínimo.
- [ ] Demonstrar rollback da configuração/imagem endurecida.
- [ ] Anexar evidências sem segredos e registrar achados residuais com severidade, owner e prazo.
- [ ] Obter aceite do owner da aplicação e da função de segurança.

**Saída obrigatória:** nenhuma vulnerabilidade crítica/alta sem correção ou exceção formal; aplicação monitorada, recuperável e com privilégios mínimos comprovados.
