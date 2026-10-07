# Hub/GLPI — plano consolidado de conclusão

Atualização: a continuação abaixo superou a indisponibilidade de navegador e
reproduziu a jornada completa. O objetivo integral permanece acompanhado em
[goal-completion-audit-2026-09-08.md](goal-completion-audit-2026-09-08.md).

Solicitação: executar o trabalho de ponta a ponta, sem aprovações intermediárias
para atividades já autorizadas. Escopo: fluxo de produção Zabbix → hub → GLPI,
acesso ao hub, inventário reconciliado e sustentação dessa integração.

## Execução e aceite

| Frente | Trabalho | Critério de conclusão | Estado |
| --- | --- | --- | --- |
| Consistência | Publicar atualização somente após commit; preservar estado em reentregas | Testes de commit, rollback e falha de Redis; implantação | Concluído |
| Acesso | Verificar SSO público e isolamento; preservar NOC global confirmado | Verificações HTTP e política de sessão; distinguir login humano indisponível | Protocolo aprovado; MFA humano pendente |
| Integridade | Comparar incidentes com tickets, entidades e marcadores | Relatório de leitura sem duplicidades ou vínculos incorretos | Concluído |
| Operação | Conferir workers, timers, CMDB, backups e fallback da IA | Relatório atual, tarefas automáticas ativas e contingência documentada | Concluído; IA em contingência |
| Entrega | Executar gates e implantar alterações; atualizar documentação | Evidências, limites e recuperação em um único documento | Concluído |

Não fazem parte desta entrega as demais ondas do programa (Psono, SecOps,
inventário físico por agentes e migração de orquestradores). Faturamento Gemini,
notificações externas e automações corretivas não serão habilitados implicitamente.

## Dependências externas conhecidas

- A ferramenta de navegação retornou `apps: [], browsers: []` nesta execução.
  Login humano/MFA não pode ser declarado aprovado por testes de API.
- A disponibilidade da IA depende da cota Gemini existente. Falha da IA deve
  manter abertura de ticket e indicação de triagem manual.
- Host 10962 (`esper`) permanece sem cliente definido e excluído. Host 10978 é
  sintético e não representa ativo físico.

## Resultado

Execução técnica encerrada em 08/09/2026, aproximadamente 20:30 UTC (17:30 BRT).
O fluxo está operacional. A homologação humana de MFA e a disponibilidade da IA
permanecem abertas, conforme os limites abaixo.

### Correções efetivamente implantadas

1. `workers/alerts.py`: publicação Redis/SSE movida para depois da saída bem-sucedida
   da transação. Rollback não publica; falha Redis não desfaz nem repete a criação
   persistida. Fechamento da conexão Redis ocorre inclusive quando publicar falha.
   Reentrega usa status, ticket e primeira ocorrência persistidos, sem anunciar um
   incidente resolvido como aberto.
2. `core/oidc.py`: versão instalada estava desatualizada e aceitava apenas dois
   argumentos, enquanto o callback passava o verificador PKCE como terceiro.
   Foi implantada a versão já existente/testada no repositório, compatível com
   PKCE. O teste anterior de código inválido retornava 400 por essa incompatibilidade;
   portanto não constituía prova de troca de códigos funcional. A prova positiva
   desta execução substitui essa evidência limitada.

### Evidências

- **226 testes backend aprovados**. Ruff aprovado nos arquivos Python de produto
  e testes alterados nesta rodada. Testes adicionais cobrem commit recusado,
  Redis indisponível, reentrega resolvida e fallback Gemini em 429, timeout e
  resposta inválida. Aviso preexistente de `datetime.utcnow()` permanece.
- Reenvio do evento sintético interno: incidente **22**, ticket **1**, task
  `8543d025-e117-4d13-a6c5-45e088cd0bff`. SSE recebido com `resolved`, ticket 1 e
  correspondência com consulta independente ao banco. Não foi criado novo ticket
  para esse teste nem encerrado ticket real de cliente.
- Auditoria de leitura às **20:22:41 UTC**: **260 incidentes / 260 tickets**, sem
  marcadores duplicados, entidade incorreta, ticket ausente/excluído,
  acompanhamento ausente ou vínculo de ativo esperado ausente. **255 ativos**,
  sem responsável ausente. Contagens são fotografias de produção em movimento.
- Protocolo OIDC real pelo endereço público, com cinco identidades temporárias:
  Alupar e Cavan receberam HTTP 200 e isolamento por cliente; NOC recebeu HTTP 200
  e acesso global. Cliente sem tenant e conta local desativada receberam 403.
  Token emitido pelo Authentik passou pela verificação JWT do hub; tenant foi
  persistido; `/me`, logout, rejeição de replay de código e PKCE incorreto passaram.
  Os cinco usuários Authentik e todos os usuários locais de teste foram removidos;
  arquivos com códigos/verificadores foram removidos dos containers e host.
- Esse teste usa concessões temporárias criadas administrativamente para testar
  a fronteira token/callback. **Não testa autenticação interativa, consentimento,
  políticas de entrada ou MFA**. Não representa sessão de usuário humano.
- `hub-session-readiness.sh`: controles estáticos de cookie, exposição de token
  no frontend e cabeçalhos da borda aprovados. Fontes `useAuth.tsx` e `App.tsx`
  correspondem ao repositório no servidor. Nenhum novo build frontend foi necessário.
- Comparados 19 módulos críticos locais e instalados: 17 correspondências exatas
  após normalizar fim de linha; `core/jwt.py` e `models/users.py` diferem apenas em
  formatação/ordem de imports e um import sem uso. Não foi feita substituição em massa.
- Saúde às **20:27:59 UTC**: Zabbix e GLPI OK, dois workers, três filas vazias,
  zero falhas/retries registrados, zero incidentes sem ticket há mais de cinco
  minutos e zero resoluções pendentes. Timers de monitoramento e CMDB habilitados
  e ativos; relatório CMDB mostra somente as duas exclusões conhecidas.
- Consulta sintética ao analisador confirmou `gemini-2.5-flash` em fallback manual
  por erro HTTP. Notificações externas continuam desativadas. Nenhum faturamento
  ou substituição de provedor foi habilitado.

### Artefatos e recuperação

Relatórios protegidos no servidor:

- `/var/lib/ness-os/hub-integration/integrity.json`
- `/var/lib/ness-os/hub-integration/oidc-protocol.json`
- `/var/lib/ness-os/hub-integration/status.json`
- `/var/lib/ness-os/hub-integration/cmdb.json`

Scripts reproduzíveis no repositório: `infra/scripts/glpi-hub-integrity-snapshot.php`,
`hub-glpi-integrity-check.py`, `hub-oidc-test-fixtures.py` e
`hub-oidc-protocol-check.py`. As fixtures são exclusivamente temporárias; o modo
`NESS_OIDC_CLEANUP=1` remove somente os IDs/nomes do manifesto protegido.

Backup desta rodada: `/opt/n-infraops/rollback/hub-final-20260908/`. Contém o
`alerts.py` anterior e o `oidc.py` legado para diagnóstico. Para reverter somente
a mudança SSE, restaurar `alerts.py` e reiniciar `ninf-worker-alerts` com prazo
de encerramento gracioso de 120 segundos. **Não restaurar o `oidc.py` legado
isoladamente: ele é incompatível com o callback atual.** Preservar a versão
compatível com PKCE e todos os registros operacionais.

Verificada a leitura integral dos arquivos `hub-followthrough-20260908/app-before.tar.gz`
e `hub-complete-20260908/before.tar`; imagem
`ness-frontend:rollback-followthrough-20260908` disponível. Isso prova disponibilidade
e legibilidade dos artefatos, não um teste de recuperação integral das bases.

### Pendências externas, concentradas

1. Uma sessão humana no navegador para aceitar login/MFA e navegação visual.
   Ferramenta de navegação indisponível; os testes de protocolo acima reduzem,
   mas não eliminam, essa pendência.
2. Disponibilizar cota/faturamento Gemini caso análise por IA seja necessária.
   Até lá, tickets continuam com triagem manual explícita.

O host `esper`, a descoberta física por agentes e as outras ondas do programa
continuam fora desta entrega. O typecheck global frontend anteriormente falho
não foi declarado aprovado por esta rodada de backend.

## Continuação do objetivo integral — 08/09/2026, 21:02 UTC

As limitações anteriores são um registro histórico; os resultados abaixo as
atualizam sem declarar o restante do programa concluído.

- Encontrado Chromium funcional no WSL, apesar da ausência de navegador no
  conector. Playwright foi instalado em ambiente temporário isolado. A navegação
  real detectou dois defeitos que a prova de protocolo não cobria.
- Authentik bloqueava a entrada de `usuarios`, embora o backend suportasse clientes.
  Adicionada política exclusiva do hub exigindo grupo `usuarios` e tenant
  reconhecido. Preservadas as associações operacionais. Política
  `ba66f74e-c795-497d-9d76-3206577cf746`, binding
  `76cea9bb-0914-4cdf-a498-34cd1aeaf758`. Teste do PolicyEngine com cache desligado:
  Alupar permitido, tenant vazio e desconhecido negados. Snapshot anterior em
  `hub-final-20260908/hub-access-before.json`; fonte reproduzível em
  `infra/scripts/hub-client-access-policy.py`.
- Atalhos laterais mudavam a seleção, mas não saíam da visão geral. Corrigida a
  seleção do módulo em Dashboard, Nuvem e Incidentes. Clientes agora iniciam em
  incidentes e não consultam painéis globais proibidos. Seletor global e módulos
  operacionais permanecem disponíveis aos papéis NOC/SOC/admin/platform_admin.
  Pricing de gestão preservado. Filtro escolhido pelo operador também acompanha
  a listagem e a recepção SSE de incidentes.
- Corrigidos os erros TypeScript de imports sem uso e tipagem de alertas Cloud.
  **`npx tsc -b --pretty false`, build Vite e lint aprovados** (lint: zero erros,
  um aviso de Fast Refresh em `useAuth`, sem alteração funcional). Builds remotos
  aprovados e frontend recriado com as correções.
- **Navegador real, três contas temporárias:** senha → desafio TOTP → consentimento
  → callback → sessão → tela de incidentes com links GLPI. Alupar e Cavan receberam
  apenas seus dados, sem seletor global e sem falso aviso de desconexão. NOC
  manteve visão global. Verificações API na mesma sessão recusaram seleção de
  outro cliente. Capturas inspecionadas e relatório em `/tmp/ness-hub-browser-result.json`
  no WSL; fonte `infra/scripts/hub-browser-sso-check.py`.
- Logout da aplicação comprovado nos três perfis. Prova adicional NOC aguardou
  a tela `You've logged out of Hub n.infraops.` e verificou `/me` 401. Logout
  central foi testado **como ação separada**, pelo fluxo de invalidação Authentik;
  o próximo acesso SSO exigiu identificação novamente. O botão da aplicação
  não foi alterado para desconectar outras aplicações. Relatório adicional:
  `/tmp/ness-hub-browser-result-ness.json`.
- Usuários de validação do hub removidos. Limpeza Authentik remove os três IDs
  exatos do manifesto e seus autenticadores/sessões; segredos temporários não
  integram os relatórios. Nenhuma conta humana existente teve senha ou MFA alterado.
- Saúde às **21:01:45 UTC**: duas filas de alerta e fila ML vazias, dois workers,
  Zabbix/GLPI OK, zero falhas/retries e zero entregas/resoluções pendentes.

### Pendências que continuam abertas

- **MFA obrigatório para identidades existentes não está concluído.** O estágio
  de autenticação usa `not_configured_action=skip`; não há dispositivos TOTP,
  WebAuthn, Static, Duo ou SMS registrados para usuários reais ativos no Authentik.
  A prova com autenticadores temporários comprova funcionamento, não cobertura
  de todos os usuários nem a política de MFA de um provedor externo Google.
- Gemini confirmado novamente com HTTP 429 `RESOURCE_EXHAUSTED`, limite gratuito
  de 20 requisições. Orçamento mensal solicitado para preparar serviço pago.
- As tarefas F1–F7/P estão preservadas na matriz de conclusão integral; o aceite
  de navegador não equivale à conclusão de recuperação, SecOps ou demais ondas.

Backups adicionais: `frontend-typecheck-before.tar.gz`,
`App-before-navigation.tsx`, `ModuleSwitcher-before-scope.tsx` e imagem
`ness-frontend:rollback-typecheck-20260908`, em complemento ao diretório
`/opt/n-infraops/rollback/hub-final-20260908/`. Rollback da nova regra de entrada:
remover somente o binding novo pelo ID registrado, preservando os anteriores.
