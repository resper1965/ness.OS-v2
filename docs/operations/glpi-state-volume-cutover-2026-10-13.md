# GLPI — troca controlada do volume de estado

Estado: **corte produtivo concluído em 13/10/2026, ~08:30 BRT**;
validação nominal SSO/perfil/ticket ainda pendente. A issue #76 controla a
observação e o retorno. Este procedimento não aprova T03/G2 nem reativa a
conta 106. O GLPI produtivo agora monta `app_glpi-state` em `/var/glpi`;
o volume anônimo original permanece preservado para rollback.

Incidente pós-corte, 13/10 ~08:47 BRT: login nominal HTTP 500 por
`TooManyResultsException` no GLPI ao encontrar o mesmo nome nos IDs 49/59.
Não há evidência de erro no volume. Pela API nativa, ID 49 (antigo,
`authtype=0`) foi renomeado e desativado; ID 59 (LDAP), perfil e vínculos
foram preservados. Readback PASS; login nominal ainda exige novo teste.
Rollback fino, se outro registro for escolhido como canônico: restaurar
nome/estado do ID 49 pela API, ciente de que isso reabre a colisão.
Auditoria agregada: 34 outros nomes duplicados, 33 grupos com dois ativos;
issue #77 controla a reconciliação. Não alterar em lote antes de validar a
identidade canônica.

## Resultado do corte de 13/10

- GO explícito de Ricardo neste chat, com Ismael como responsável técnico,
  registrado na issue #76. Janela vigente até 11:47:35 BRT.
- Backup `COMPLETED` de 12/10 23:07 BRT, com `SHA256SUMS` íntegro, inclui
  banco GLPI e o volume original. Caddyfile anterior e Compose anterior foram
  preservados em `/opt/n-infraops/rollback/glpi-state-20261013/` (root-only).
- Primeira tentativa de reload da manutenção não isolou a rota porque
  `install` trocou o inode do bind mount somente leitura. O Caddyfile no host
  foi restaurado antes de parar o GLPI. O candidato foi então carregado pela
  API de administração do Caddy a partir de `/tmp` no contêiner, sem restart:
  GET/POST públicos GLPI=503; Hub=200 e SSO=302 preservados.
- GLPI parado; cópia `cp -a` do volume anônimo original para
  `app_glpi-state`; comparador integral PASS: 5.780 arquivos e
  8.490.431.469 bytes. Compose corrigido montou o volume nomeado exatamente
  em `/var/glpi`; somente `ninf-glpi` foi recriado. Guard de volume PASS,
  contêiner `running` com zero reinícios, diretórios de configuração/arquivos
  presentes, UI/API internas=200 e `database:check_schema_integrity` PASS.
- Caddy original recarregado; GET/POST públicos GLPI=302 (redirect SSO
  pré-existente), Hub=200, SSO=302. O teste nominal de login, perfil, ticket e
  anexos ainda precisa ser observado; não declarar aceite funcional completo.
- Rollback preparado por override explícito
  `app/docker-compose.glpi-state-rollback.yml` com o nome do volume original
  fornecido em `GLPI_ROLLBACK_VOLUME`. Nunca usar apenas o Compose antigo.
  Após reabertura, fechar rota e reconciliar novas escritas antes de qualquer
  retorno; não executar rollback cego.

## Entrada obrigatória

1. Ticket aceito, owner, janela, GO, último backup `COMPLETED` aplicável e
   critério de aborto. Registrar o nome do volume original pelo `docker
   inspect ninf-glpi` e manter esse volume intacto até a observação.
2. Conferir que `/opt/n-infraops/app/Caddyfile` conserva SHA-256
   `9969174781724155323d7a996beb6bcf58422deb83fe3f503140606ff30ff3b5`.
   Se mudou, revisar o delta e **não** usar o candidato antigo. O arquivo
   versionado e o runtime tinham hash idêntico em 13/10.
3. Gerar o candidato com `infra/scripts/glpi_caddy_maintenance.py`, exigindo
   esse hash, em arquivo novo root-only. Validar com `caddy validate --config`.
   O script altera apenas o bloco `n-ticket.ness.com.br`, para responder 503
   com `Cache-Control: no-store`; nunca envia o conteúdo ao chat ou ao Git.
4. Guardar cópias root-only do Caddyfile e Compose efetivos. Confirmar que
   Caddy monta `/opt/n-infraops/app/Caddyfile` em `/etc/caddy/Caddyfile` e
   que seu admin endpoint responde via loopback dentro do container. Ambos
   foram observados em leitura em 13/10; isso não prova isolamento de rede.

## Corte sem escrita

1. O bind mount de `/etc/caddy/Caddyfile` é somente leitura: **não substituir
   seu inode no host**. Copiar o candidato para um arquivo temporário root-only
   dentro de `ninf-caddy`, validar e executar `caddy reload --config` apontando
   para esse arquivo. Confirmar GET e POST públicos para
   `n-ticket.ness.com.br` = 503; Hub e SSO continuam disponíveis. Falha em
   qualquer verificação: recarregar `/etc/caddy/Caddyfile` original e abortar
   antes de tocar GLPI.
2. Parar somente `ninf-glpi`. Confirmar parado e sem rota interna direta.
   O banco permanece intacto; não modificar credenciais nem tickets.
3. Criar volume nomeado **novo** para `/var/glpi`. Copiar do volume anônimo
   original com `cp -a` enquanto GLPI está parado. Rodar
   `glpi_state_volume_compare.py` nos mountpoints, exigindo igualdade de
   conteúdo e metadados. Falha: manter original e restaurar serviço/rota
   originais; não remover volume algum.
4. Preparar Compose que monta o novo volume nomeado exatamente em
   `/var/glpi`; validar o Compose resolvido. Recriar apenas `glpi`, sem
   recriar banco/Hub/Caddy. Confirmar mount efetivo igual ao novo volume,
   configuração, arquivos, UI/API interna e ausência de erros antes de
   reabrir tráfego. O guard `glpi_state_volume_preflight.py` deve passar
   **após** essa troca; ele bloqueia intencionalmente o primeiro handoff.
5. Se falhar ainda em manutenção: parar novo `glpi`, usar um override
   root-only que remonte **explicitamente o volume original** em `/var/glpi`,
   recriar só `glpi`, validar e só então restaurar Caddyfile original. O
   Compose antigo sozinho não serve de rollback: criaria outro volume
   anônimo. Preservar o volume novo para diagnóstico.
6. Reabrir tráfego apenas após GO e smoke interno. Validar SSO nominal,
   perfil, ticket e Caddy. Qualquer falha após reabertura exige fechar a
   rota imediatamente e reconciliar escritas novas antes de voltar ao volume
   original; rollback cego pode perder anexos/configuração recentes.

## Evidência e limite

O laboratório descartável passou para 503 GET/POST exclusivo do GLPI,
Hub/SSO sintéticos 200, cópia `cp -a`, comparação e reanexação do volume
original. Um segundo ensaio Compose, também sintético, iniciou um serviço
com o volume `original` em `/var/glpi`, recriou-o com override para
`candidate` e então com override de rollback para `original`. `docker
inspect` confirmou o nome do volume em cada etapa. Os dois volumes de teste,
o serviço e os arquivos temporários foram removidos com ausência verificada.
Isso não equivale a corte produtivo, SSO autenticado ou prova de rollback
com escritas. Nenhum volume produtivo foi copiado ou recriado.
