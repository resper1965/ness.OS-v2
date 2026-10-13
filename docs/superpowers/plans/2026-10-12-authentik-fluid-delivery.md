# Authentik — identidade e experiência ness. no ness.OS

> **Somente planejamento; não executar com o modelo autor.** Implementação após troca de modelo e retomada humana. Usar `ponytail:ponytail` full, `superpowers:executing-plans` e `ness-branding`. Automação permanece pausada.

**Objetivo:** entregar identidade central confiável, jornadas claras e customização ness. em todas as superfícies suportadas do Authentik.

**Arquitetura:** reutilizar Brands, fluxos, policies, providers e outposts existentes. Authentik autentica e entrega claims; cada aplicação continua responsável por autorização efetiva. Configuração nativa antes de CSS ou código, uma aplicação por mudança.

**Stack:** Authentik registrado em 2026.5.6, OIDC/SAML/proxy, Google como fonte externa, containers e configuração versionada. Confirmar versão efetiva antes de usar campos ou recursos de outra versão.

**Referências:** `docs/adr/0007-authentik-central-identity.md`, `docs/operations/authentik-ness-implementation-guide-2026-10-12.md`, `config/authentik/ness-os-baseline.yaml`, plano de identidade de 18/09 e [customização transversal](2026-10-12-ness-branding-cross-product-plan.md). Este plano define a próxima sequência; o guia mantém evidências históricas.

## Estado conhecido

| Preservar | Concluir |
|---|---|
| Brand `ness. | acesso`, fluxo `Acesse sua conta`, CSS e logo existentes | Marca nas demais jornadas, portal autenticado, textos e assets aprovados |
| Tela inicial 390/1440px e reduced-motion testados | MFA, recuperação, erros, configurações pessoais e admin ainda sem aceite visual completo |
| Hub provider 9: três callbacks inválidos negados | Jornadas autenticadas, revogação e logout real por aplicação |
| Providers em uso inventariados | Legados e dependências antes de qualquer remoção |
| Três administradores canônicos definidos | MFA nominal e recuperação; último registro sem fatores cadastrados |
| Policies Google existentes | Bindings ausentes nos caminhos efetivos; issue 75 |

Esses dados vêm do registro anterior; não foram reconsultados em produção para escrever este plano. Não repetir branding público, inventário amplo ou restore sem mudança relevante.

## Regras de execução

- Menor mudança completa, teste proporcional e avanço imediato após aceite. Reusar `ness-access.css`, baseline e verificadores existentes.
- Não alterar SQL de autenticação, gerar fatores em nome de pessoas ou expor seeds, QR, códigos, tokens e dados pessoais.
- `platform_admin` permanece restrito a Ricardo Esper, Ismael Araujo e Rogerio Salerno; não conceder por domínio de email.
- Não mudar MFA de `skip` para bloqueio global antes de fatores, recuperação e contingência comprovados.
- Não presumir que MFA externo está imposto no Google nem que logout do IdP encerra todas as aplicações.
- Não apagar provider por parecer sem aplicação: outposts/consumidores podem referenciá-lo. Não migrar GLPI para OIDC no mesmo ajuste visual.
- Preparação visual pode avançar enquanto humanos cadastram fatores. Ativação de controles de acesso continua dependente dos testes necessários.
- Conferir janela vigente antes de mutação. A janela histórica termina em 13/10/2026 11:47:35 BRT; não prolongá-la por este documento.

## 1. Preparar uma mudança pequena e recuperável

**Usar:** guia existente, `infra/scripts/authentik-readiness-report.sh`, `authentik-public-precheck.sh` e seus testes. Atualizar `config/authentik/ness-os-baseline.yaml` apenas após comparar estado real e desejado; ele não é prova de configuração aplicada.

- [ ] Conferir somente mudanças desde o registro anterior: versão, aplicação alvo, objetos envolvidos e acesso administrativo nominal.
- [ ] Exportar objetos da mudança para arquivo protegido e registrar IDs/revisão; excluir segredos dos commits. Precondição evita sobrescrever alteração humana posterior.
- [ ] Preparar fluxo candidato sem ligá-lo globalmente. Definir retorno ao binding/configuração anterior e manter uma sessão administrativa de contingência.

**Pronto quando:** escopo, antes/depois esperado e retorno estão claros. Não precisa criar um novo framework de provisionamento.

## 2. Corrigir a jornada Google sem duplicar identidades

**Usar:** policies e grupo de externos aprovados existentes; referência `docs/execution/authentik-google-external-approval-2026-09-01.md`, issue 75.

- [ ] Conferir associação por email verificado e autorização de enrollment nos fluxos realmente usados. Não alterar matching sem ensaio: pode duplicar usuários.
- [ ] Vincular as policies existentes em fluxo candidato com regra explícita: cadastro interno autorizado; externo somente pré-existente e aprovado; conta desativada continua negada.
- [ ] Testar interno válido, externo aprovado, externo não aprovado, inexistente, email não verificado e conta desativada. Confirmar que o mesmo usuário mantém ID e grupos.
- [ ] Promover somente bindings aprovados; rollback restaura bindings e não remove usuários criados legitimamente.

**Pronto quando:** restrições são efetivas nos caminhos de autenticação e enrollment, sem bloquear externos já aprovados. Presença de policy sem binding não conta.

## 3. Concluir MFA e recuperação

**Usar:** fluxos/etapas nativos, issues 66 e 59. Criar candidatos antes de modificar a Brand.

- [ ] Cada administrador cadastra seu próprio WebAuthn ou TOTP e códigos de recuperação; registrar somente método, horário e resultado. Custódia de contingência segue política aprovada, sem compartilhar fatores pessoais no chat.
- [ ] Provar entrada em sessão nova, fator incorreto, recuperação e acesso de contingência. Interação humana é indispensável para fatores nominais.
- [ ] Exigir MFA para o grupo administrativo em todos os caminhos usados, inclusive Google, antes da abertura de sessão. Usuários comuns mantêm política própria; não aplicar deny global por conveniência.
- [ ] Preparar recuperação nativa com email verificado: expiração, uso único, negação de token errado, conta inexistente sem enumeração, falha SMTP e limitação de tentativas. Não transformar redefinição de senha em bypass de MFA ou reativação de usuário.
- [ ] Usar destinatário de teste autorizado para comprovar envio antes de habilitar o fluxo. Envio de recuperação não autoriza campanhas ou notificações externas das demais ferramentas.
- [ ] Publicar recuperação na Brand apenas após provas; rollback desvincula o fluxo, preservando auditoria e senhas legitimamente alteradas.

**Pronto quando:** administradores conseguem entrar e recuperar acesso, fator é exigido de verdade e não há caminho alternativo que o ignore. Falta de humano bloqueia essa promoção, não a preparação das etapas 4/5.

## 4. Homologar aplicações uma por vez

**Usar:** matriz do guia, `app/backend/tests/test_authentik_rbac.py` quando código Hub mudar e verificadores existentes. Criar `docs/execution/authentik-application-acceptance.md` na execução para registrar resultados, sem payloads de tokens.

| Aplicação | Caminho conhecido | Prova específica |
|---|---|---|
| Hub | OIDC 9 | PKCE, state/nonce, claims, tenant/papel por HTTP/SSE; logout encerra stream |
| GLPI | Proxy 12 | Matching do usuário, headers limpos pelo proxy, backend restrito e perfis/entidades nativos; gap da conta 106 continua no plano GLPI |
| Zabbix e UAT | SAML 6 e 13 | SPs separados, assinatura/audience/ACS, papel nominal, MFA, logout e break-glass; sem ativar coleta |
| Grafana | OIDC 10 | Organização e papel mínimos; ausência de auto-admin por email |
| n8n | Proxy 5 | Autorização nativa owner/editor/viewer; borda não equivale a SSO nativo |
| nessops / n-csirt | OIDC 2 / 16 | Consumidor e políticas efetivos; callbacks exatas, sem regex abrangente |
| Wazuh | OIDC 11 cadastrado | Continua planned até gate próprio; existência de provider não libera aplicação |

- [ ] Em cada aplicação ativa: login permitido/negado, usuário desativado, grupo retirado, sessão expirada, callback inválido, logout e IdP indisponível.
- [ ] Medir tempo real de revogação e distinguir sessão IdP de sessão local. Registrar duração atual, limite exigido e resultado antes de mudar TTL; não prometer logout global sem suporte e prova.
- [ ] Confirmar break-glass separado, restrito e auditado para sistemas críticos; não criar bypass público.
- [ ] Corrigir somente a aplicação que falhar e repetir os testes afetados. Não reaplicar SAML já aprovado sem mudança.

**Pronto quando:** cada aplicação ativa está homologada ou possui bloqueio específico com impacto; G2 não passa enquanto requisito obrigatório estiver pendente.

## 5. Completar a experiência ness.

**Usar:** `config/authentik/ness-access.css`, Brand e campos nativos de fluxo/aplicação. Ampliar `infra/tests/inspect-authentik-branding.cjs` somente para jornadas novas. Aplicar matriz transversal vinculada no início.

- [ ] Inventariar superfícies suportadas na versão/edição: login local/Google, senha, MFA, enrollment, recuperação, consentimento, logout, erro, sessão expirada, biblioteca, configurações pessoais e administração.
- [ ] Manter logo único e título de tarefa separado: `Acesse sua conta`, `Confirme sua identidade`, `Recupere seu acesso`, `Aplicações`. Não repetir marca em título, subtítulo e logo adjacentes.
- [ ] Organizar biblioteca por função e permissão, com ícones aprovados, nomes claros e destinos corretos. Manter apenas aplicativos autorizados; ocultação não substitui autorização.
- [ ] Personalizar fundo, superfícies, foco, botões, ajuda, favicon, títulos e textos pt-BR pelos campos suportados. Não reescrever controles com pseudo-elementos CSS, injetar JavaScript ou alterar dist/core.
- [ ] Incluir identidade visual em templates de email suportados: assunto claro, remetente/domínio verificado, ação única, alternativa de texto e suporte separado do logo. Montserrat no wordmark deve vir de asset aprovado; clientes de email podem não carregar fonte web.
- [ ] Revisar portal pessoal e administração para densidade, consistência e legibilidade; preservar avisos de segurança, identificação técnica necessária e atribuições/licenças obrigatórias.
- [ ] Validar 390/1440px, teclado, foco, zoom 200%, claro/escuro quando suportados, contraste, controles 48px e reduced-motion. Conferir MFA/erros/recovery, não apenas login inicial.

**Pronto quando:** todas as superfícies aplicáveis da matriz têm evidência ou limitação documentada; aceite visual e segurança são separados. Rollback repõe somente configuração/CSS/assets afetados.

## 6. Reduzir legados e fechar sustentação

- [ ] Após jornadas aprovadas, mapear consumidores de providers legados, outposts e callbacks. Remover uma referência por vez, somente com ausência de dependência comprovada e export de retorno.
- [ ] Alertar sobre expiração de certificado, falha de worker/outpost, falha de login agregada e indisponibilidade. Logs não devem conter códigos, tokens ou identidade pessoal desnecessária.
- [ ] Atualizar guia existente com onboarding/offboarding, perda de fator, indisponibilidade, certificado, rollback, suporte e responsáveis. Não criar documentação concorrente.
- [ ] Reusar recuperação válida; ensaiar novamente apenas o que a mudança invalidou. Confirmar backup atual antes de promoção, sem repetir ciclos completos por rotina.
- [ ] Promover por aplicação, verificar acesso e registrar commit/evidência. Observar D+1/D+3/D+7 para encerramento; não aguardar sete dias para começar a usar uma aplicação homologada.

**Pronto quando:** identidade e marca aceitas, recuperação operacional, legados justificados e responsabilidades claras. Revogar acesso temporário ao finalizar a mudança.

## Revisão e handoff

Casos que não podem escapar: Google sem MFA administrativo; email não verificado vinculando conta; logout que mantém aplicação ativa; header externo forjado; CSS cobrindo erro/foco. Testar somente componentes/jornadas alterados e suas dependências diretas; ampliar se houver falha.

Primeira retomada: etapa 1, preparação de 2/3 e experiência 5. Depois homologação por aplicação e limpeza. Nenhum endurecimento global antes de contingência. Executor consulta Context7 para contratos atuais e confirma recursos na versão instalada.

Fontes de customização consultadas via Context7: [Brands](https://docs.goauthentik.io/brands/), [branding](https://docs.goauthentik.io/customize/branding/), [fonte oficial](https://github.com/goauthentik/authentik). Recursos pagos ou ausentes não são presumidos disponíveis; registrar limite e alternativa nativa.

Este documento é planejamento. Nenhum fluxo, provider, usuário, fator ou visual foi alterado por sua elaboração.
