# Incidente — comprometimento do Zabbix e mineração XMRig

> Detectado: 20/08/2026 16:03 BRT
> Primeira atividade maliciosa confirmada: 22/07/2026 05:12 BRT
> Severidade: crítica
> Encerrado: 21/08/2026
> Estado: resolvido; melhorias estruturais transferidas para o plano de hardening do ness.OS
> Ativo: `zabbix-srv01`

## Resumo executivo

A baseline do Gate 0 encontrou load acima de 170, memória quase esgotada, ausência de swap e MariaDB em ciclo de recuperação após OOM. A causa imediata eram 203 processos ocultos executados pelo usuário `zabbix` a partir de `/var/tmp/.zbx_sys_health`.

O binário foi identificado pelo próprio log como XMRig 6.22.2, conectado a pools MoneroOcean. O crontab do usuário `zabbix` executava o artefato no boot e a cada minuto.

O audit log do Zabbix confirmou uso da conta padrão `Admin` por endereços externos para criar, executar e remover scripts. Foram observados nomes como `MyScripttest`, `AutoRCE_*`, `_d*`, `cron_health_*` e `chk3`. A atividade confirmada começa em 22/07/2026, continua de forma recorrente até 19/08/2026 e culmina no minerador encontrado em 20/08/2026. O incidente deve ser tratado como comprometimento da credencial administrativa e execução de comandos por funcionalidade legítima do Zabbix.

## Impacto observado

- MariaDB morto repetidamente pelo OOM killer e reiniciado 14 vezes.
- Interrupção temporária do banco e degradação do Zabbix.
- Consumo de aproximadamente 2,4 GiB por processo malicioso, com centenas de instâncias.
- Uso de diversos hosts/proxies como contexto das ações manuais. Os registros analisados têm `execute_on=1`, que no Zabbix 7.0 executa o comando no servidor Zabbix; portanto, esses registros não comprovam execução direta nos ativos selecionados.
- Conta `Admin`, sessões e tokens considerados comprometidos.

Não houve evidência, na inspeção inicial, de usuário UID 0 adicional, chave SSH não reconhecida, cron privilegiado, unit systemd recente ou executável temporário remanescente. Isso reduz, mas não elimina, a necessidade de reconstrução limpa.

## Indicadores preservados

| Artefato | SHA-256 |
|---|---|
| `.zbx_sys_health` | `b0e1ae6d73d656b203514f498b59cbcf29f067edf6fbd3803a3de7d21960848d` |
| `.zbx_sys_health.json` | `7fd1d0aa5af1fef317308058ffdc905798c3bc1d14b11de1baba3f9a4ca6728e` |
| `.zbx_sys_health.log` | `113eb70c62c4bdb00004296e68f871a25142505414b0f5b8d19dfdaa44e81213` |
| `client_amd64` | `b67efa0a3caee1c6fe54f0f715e73fb1ba80bed09729a53415b46c79d8fece2a` |

Outros indicadores:

- diretório `/var/tmp/.syslog-4cb9b400`;
- pool `gulf.moneroocean.stream` nas portas 443 e 80;
- persistência no crontab do usuário `zabbix` com `@reboot` e execução a cada minuto;
- quarentena em `/root/incident-quarantine/20260820-zbx-sys-health`, permissões `000` nos arquivos.

Endereços bloqueados após correlação com execução da conta comprometida:

- `111.90.158.58`
- `202.61.130.107`
- `202.61.130.55`
- `166.88.227.34`
- `37.153.90.88`
- `36.234.157.166`
- `111.34.138.86`

Destinos de descarga maliciosa bloqueados para saída no servidor Zabbix:

- `111.90.158.58`
- `111.90.139.202`
- `151.245.90.135`

Outros indicadores de rede observados nos comandos preservados:

- `msys-cdn.s3.amazonaws.com` e `gbcus.s3.amazonaws.com`, usados como origem de payload disfarçado;
- `pool.hashvault.pro`, nas portas 443, 80 e 7777;
- `gulf.moneroocean.stream`, nas portas 443 e 80.

## Contenção executada

1. Hashes dos artefatos e persistência preservados.
2. Crontab malicioso do usuário `zabbix` removido.
3. Processos com linha de comando correspondente ao artefato encerrados.
4. Binários, configuração, log e resíduos movidos para quarentena protegida.
5. Senha da conta padrão `Admin` substituída por valor aleatório irrecuperável; o vínculo formal ao grupo `Disabled` foi identificado como pendência na auditoria de 21/08.
6. 303 sessões da conta `Admin` revogadas.
7. Dois tokens da conta `Admin` removidos.
8. Sete origens correlacionadas bloqueadas no UFW e três destinos de descarga bloqueados para saída.
9. Serviços MariaDB, Zabbix Server, Apache e Agent 2 validados como ativos.
10. HTTP do Zabbix validado com resposta 200 e nenhum novo OOM após a contenção.
11. `EnableGlobalScripts=0` definido explicitamente e Zabbix Server reiniciado com validação e rollback preparado.
12. Sessenta scripts residuais suspeitos, com IDs de 26 a 83, neutralizados pela desativação de scripts no servidor.
13. Exportações forenses dos 58 scripts customizados, do audit log da conta `Admin` e do firewall preservadas com SHA-256 em `/root/incident-quarantine/20260820-zbx-sys-health/db-evidence`.
14. Conta `Admin` associada formalmente ao grupo `Disabled`; validação posterior confirmou ausência de sessões e tokens.
15. Os 58 comandos customizados foram preservados novamente e neutralizados individualmente para `true`; todos possuem o hash esperado após a mudança.
16. O token `resper/intranet`, encontrado habilitado e exposto em código, foi correlacionado a quatro chamadas Python em 19/08, preservado por metadados e desabilitado. A evidência está em `/root/incident-quarantine/20260820-zbx-sys-health/token-revocation-20260821`.
17. O token foi removido das cinco referências identificadas no código; os consumidores passaram a exigir variável de ambiente e autenticação Bearer.

## Evidências de escopo inicial

- Nove cópias históricas/paralelas de `zabbix_server.conf` foram removidas de `/etc/zabbix` e preservadas em `/root/incident-quarantine/20260820-zbx-sys-health/config-backups`, todas como `root:root` modo `600`. Sete continham a credencial de banco vigente; o arquivo ativo permaneceu inalterado.
- `items` com `system.run`: zero no estado atual.
- Itens/scripts atuais contendo os indicadores: zero; os objetos foram apagados após execução.
- O audit log preserva os ciclos de criação, execução e remoção.
- O payload `AutoRCE_*` decodificado tentava baixar e executar `download.sh` do endereço `151.245.90.135:8002`.
- O payload `chk3` tentava instalar `/tmp/.zbx_cron_health`, baixando XMRig de `111.90.158.58` ou `111.90.139.202` e conectando-o ao HashVault.
- As execuções que nomeiam o Zabbix Server, o proxy de Lima e ativos de Anserma/Bogotá registram `script.execute_on=1`. Pela documentação do Zabbix 7.0, o comando é executado no servidor Zabbix. Os ativos foram selecionados como contexto e permanecem em verificação preventiva, mas não há, nesses registros, prova de execução direta neles.
- Em 21/08/2026, a correlação dos 266 registros identificou oito contextos: Zabbix Server, proxy Linux Lima, quatro Fortigate via SNMP e dois Windows Server 2019. A incompatibilidade dos payloads Bash com Fortigate/Windows e `execute_on=1` afastam execução direta por estes registros. Permanece necessária uma coleta IOC independente no proxy Lima e, por confirmação, nos dois Windows; detalhes em [`../../../docs/execution/zabbix-incident-context-verification-2026-08-21.md`](../../../docs/execution/zabbix-incident-context-verification-2026-08-21.md).
- Somente `root` possui UID 0.
- A única chave SSH nominal observada pertence a `ness_admin` e os logins recentes vieram do endereço administrativo esperado.
- Nenhum executável permaneceu em `/tmp`, `/var/tmp` ou `/dev/shm` após a quarentena.
- Permanecem cadastrados 58 objetos customizados relacionados ao incidente apenas para rastreabilidade. A evidência anterior foi preservada, todos os comandos foram neutralizados para `true` e `EnableGlobalScripts=0` impede execução no servidor.

## Melhorias transferidas para hardening

1. Copiar backups e evidências para Object Storage criptografado e executar restauração isolada.
2. Fazer verificação preventiva dos mesmos indicadores no proxy Lima e nos dois Windows usados como contexto, quando os acessos forem disponibilizados.
3. Reduzir os 14 Super Admins para duas identidades break-glass e papéis cotidianos limitados.
4. Tornar Authentik/MFA obrigatório depois da homologação, preservando break-glass.
5. Implantar Passbolt e varredura de segredos no pipeline; nenhuma credencial pode voltar ao código ou aos artefatos de deploy.
6. Restringir 10051 às origens aprovadas.
7. Reconstruir a VPS Zabbix a partir de imagem limpa antes de classificá-la como produção; restaurar apenas banco e configuração revisados.
8. Manter a VPS atual e a quarentena como evidência até o aceite da reconstrução.

## Encerramento e risco residual aceito

O incidente foi encerrado por decisão do owner em 21/08/2026 porque o ambiente ainda não era produção e a contenção técnica foi confirmada: minerador e persistência erradicados, conta comprometida desabilitada, sessões/tokens revogados, scripts bloqueados e neutralizados, serviços estáveis, evidências preservadas e backups verificados. A correlação não demonstrou execução direta nos ativos usados como contexto.

O encerramento não promove o ambiente a produção. Reconstrução limpa, RBAC/MFA, cofre de segredos, backup externo com teste de restauração e inspeção preventiva dos endpoints são critérios obrigatórios de prontidão do ness.OS.

## Lições aprendidas e controles permanentes

- Contas padrão e privilégios excessivos transformaram uma credencial comprometida em execução remota; `Admin` permanecerá desabilitado e Super Admin ficará limitado a duas identidades break-glass.
- Scripts globais não eram necessários para a operação corrente; `EnableGlobalScripts=0` passa a ser baseline monitorada e qualquer exceção exigirá mudança aprovada.
- Tokens e senhas foram encontrados em código e artefatos legados; novos segredos serão fornecidos por cofre/ambiente, com secret scanning no CI e rotação após qualquer exposição.
- Backup local não é recuperação de desastre; cópia externa criptografada e restauração periódica passam a ser controles de entrada em produção.
- Telemetria incompleta dificultou a confirmação do proxy Lima; disponibilidade de agente/RMM e coleta IOC tornam-se requisitos de onboarding.
- Hardening não termina no go-live: será seguido por polimento de coleta, mapas, localização, qualidade de dados, redução de ruído e revisão periódica de acesso.
