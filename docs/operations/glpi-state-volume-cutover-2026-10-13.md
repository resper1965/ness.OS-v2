# GLPI — troca controlada do volume de estado

Estado: **preparado, não liberado para execução produtiva**. A issue #76 é o
controle da mudança. Este procedimento não aprova T03/G2 nem reativa a conta
106. O GLPI produtivo ainda usa um volume anônimo em `/var/glpi`; o Compose
atual monta outro volume em `/var/www/html/glpi`.

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

1. Instalar o candidato no mesmo bind mount e executar `caddy reload
   --config /etc/caddy/Caddyfile` no container `ninf-caddy`. Confirmar GET e
   POST públicos para `n-ticket.ness.com.br` = 503; Hub e SSO continuam
   disponíveis. Falha em qualquer verificação: restaurar Caddyfile original,
   recarregar e abortar antes de tocar GLPI.
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
original. Isso não equivale a corte produtivo, SSO autenticado ou prova de
rollback com escritas. Nenhum volume produtivo foi copiado ou recriado.
