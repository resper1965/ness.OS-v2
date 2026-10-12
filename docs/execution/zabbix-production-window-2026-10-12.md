# Zabbix — janela excepcional autorizada

Autorização direta do usuário: 24 horas de janela; prioridade de entrega
produtiva em quatro horas, permitindo Cavan como piloto.

Registro: 12/10/2026 11:47:35 BRT (14:47:35 UTC). Limite operacional adotado:
13/10/2026 11:47:35 BRT. Após esse limite volta a janela 22:00–00:00 BRT.
A meta de quatro horas não elimina rollback, isolamento ou evidência de corte.
Observação 24–72h/D+1/D+3/D+7 continua posterior, sem aceite fictício imediato.

Origem: Zabbix 7.0.27 e MariaDB ativos. Último conjunto existente:
20261011T220025-0300, snapshot externo f0b19cf8 de 12/10 às 05:32 BRT.
Destino: backup offline de rollback 20261012T112805-0300 terminou com sucesso
e COMPLETED. Nenhum novo dump de teste será iniciado nesta preparação.

Credencial válida encontrada no consumidor Hub, permitindo leitura da origem.
Os cinco hosts Cavan 10873,10874,10877,10878,10885 já têm tags tenant, site,
environment, scope, owner, role e technology na origem. O banco antigo da UAT
não tinha essas tags. Prioridade passa a sincronizar a UAT com a origem;
não aplicar o pacote antigo de tags sobre uma baseline corrente diferente.

Staging do snapshot f0b19cf8 iniciado pela unidade
ness-zabbix-migration-stage-20261012. Restore no banco definitivo ainda depende
de staging íntegro e preservação do rollback. Origem continua coletando até o
freeze final de corte; destino permanece mascarado/inativo para impedir dupla
coleta. Toda evidência deve distinguir preparação, aplicação e produção.

Staging concluído às 11:54:38 BRT: dump 5.261.041.778 bytes, SHA256SUMS e gzip
aprovados. Snapshot restaurou seu conteúdo na raiz de restic-f0b19cf8. A primeira
tentativa de refresh usou caminho inexistente e abortou antes de tocar o banco;
caminho corrigido após inspeção. Importação corrente na unidade
ness-zabbix-refresh-validated-20261012, PID inicial 556425.

Leitura corrente na origem via credencial runtime do Hub e leitura SQL restrita:
os cinco hosts Cavan possuem um template vinculado cada. Itens não suportados:
10873=1, 10874=1, 10877=2, 10878=0, 10885=0. A ausência de parentTemplates
na resposta do token Hub não comprova ausência de template; a consulta de banco
confirmou os vínculos. O pacote antigo de correção não deve sobrescrever isso.

Branding nativo aplicado no destino, usando `local/conf/brand.conf.php` e
logos oficiais já existentes, sem editar core. Rollback:
`/var/lib/ness-os/restore-evidence/branding-20261012T120055-0300`.
PHP lint e comparação dos assets passaram; inspeção da UI depende de terminar
a importação. Publicação e aceitação visual ainda não estão declaradas.

O destino possui 48 GiB RAM e buffer pool 16 GiB. Durante a importação isolada,
`innodb_flush_log_at_trx_commit` mudou temporariamente de 1 para 2; a unidade
ness-zabbix-reset-durability-20261012 está enfileirada após o import para voltar
a 1, inclusive se a importação falhar. A promoção exige confirmar 1. Risco
restrito ao dump em importação: uma queda pode perder até o último segundo de
transações e exigir reimportação do snapshot imutável; origem não foi alterada.

Ticket operacional GLPI 75426 registra owner, janela, rollback e abort criteria.
A API Change retornou 403; o ticket não representa aprovação formal desse
objeto. Branding nativo aplicado também na origem às 12:09 BRT, mantendo
Zabbix/MariaDB ativos. Rollback da origem:
`/var/lib/ness-os/restore-evidence/branding-20261012T120907-0300`.
Assets de login/sidebar responderam HTTP 200 pela URL pública. Não se declara
aceite visual desktop/móvel antes da inspeção renderizada.

Quatro itens prioritários do piloto: 97468/97845 (FortiGate: cálculo de espaço
livre divide por capacidade), 63249 (Windows: swap livre depende de contador
Paging file), 63256 (Windows: utilização depende de used/total). A leitura API
mostra fórmulas herdadas; alteração no template raiz afetaria outros clientes.
Nenhuma correção global ou desativação em massa foi aplicada.

## Continuação 12/10 — 12:17 BRT

A mesma unidade de refresh permanece `activating/start`, não concluída;
diretório do banco destino avançou para 13 GiB. Destino continua mascarado e
inativo. Durabilidade ainda 2 durante import; reset para 1 aguarda a unidade.
`Result=success` durante `activating` não é prova de conclusão do restore.

Escopo autorizado ampliado aos 325 hosts; trilha registrada no commit 0c45004.
Classificação em leitura: 60 erros de divisão por zero em 60 hosts e 93 erros
de dependência de cálculo em 44 hosts, na primeira amostra. Categorias não são
diagnósticos finais. A amostra seguinte por tipo evidenciou concentração em
itens dependentes (tipo 18: 1.395 em 27 hosts), checks simples (tipo 3: 255 em
7), agente passivo (tipo 0: 237 em 46) e cálculos (tipo 15: 153 em 104).
Contagens são amostras distintas de produção viva, não uma soma reconciliada.

Causa específica confirmada no piloto: FortiGate 97468/97845 divide por
capacidade zero; Windows 63249/63256 não tem dados suficientes nas dependências.
Próximo passo técnico é conferir capacidade real do appliance e disponibilidade
dos itens-base Windows antes de alterar fórmulas. Não mascarar coleta inválida
com valores artificiais ou propagar edição de template raiz aos outros tenants.

### Verificação das dependências — continuação 12:22 BRT

Importação na mesma unidade continua ativa; diretório de banco agora 15 GiB.
Nenhum restart ou novo restore foi iniciado.

Leitura pontual indexada do último histórico das dependências do piloto:
FortiGate 97469/97846 (capacidade) e 97470/97847 (uso) têm último valor zero.
Os itens estão habilitados e sem erro próprio; isso não torna o cálculo de
percentual válido. Investigar se os appliances realmente possuem storage
antes de declarar aplicabilidade; não trocar divisão por zero por saúde falsa.

Windows 63235 (Paging file), 63250 (swap total), 63254 (memória total) e 63255
(memória usada) estão habilitados e sem erro próprio, mas não há histórico nas
tabelas correspondentes ao value_type. A falha é ausência de amostras, não uma
fórmula comprovadamente errada. Priorizar disponibilidade/agente/intervalos e
retenção antes de editar os dois itens calculados; trends não foram consultadas.

## Resultado do refresh — 12/10/2026 12:38:46 BRT

`ness-zabbix-refresh-validated-20261012` terminou com Result=success,
restore=PASS e isolated_refresh=PASS. Import nativo: 2.471 segundos,
203 tabelas, 687 registros em hosts (325 hosts + 362 templates), 64.688 itens,
26.927 triggers, dbversion obrigatório 7000000. Snapshot f0b19cf8 e SHA do dump
a1db6a00f97582f035004ceee8201a9fbb735099667da5c5625c31f7f2379f36.
Não repetir esta transferência/importação sem mudança relevante.

Durabilidade voltou automaticamente a 1, com unidade de reset aprovada.
MariaDB/Apache ativos; Zabbix inativo/mascarado, listener 10051 ausente,
ações/mídias/conectores habilitados=0. API pública 7.0.27 e frontend HTTP 200,
sem erro de conexão ao banco, com referência nativa ao logo oficial.

Paridade corrente origem/destino: mesmos totais de hosts/itens/triggers.
Inventário normalizado de IDs/status/proxy/monitored_by, tags e templates
diretamente vinculados: 325 hosts, 262 tags, 315 vínculos, SHA-256 idêntico
48c80da9959e9013a21024fcc45ef453b678cf3ad5450589e7c43bd4acce45f8.
Isso prova paridade desses campos, não igualdade de todo histórico produtivo
após o snapshot. Cavan conserva tags e um template por host do piloto.

Correção factual: 10877 está desabilitado na origem e no destino; seus erros
históricos não entram na prioridade de coleta ativa. Não será reativado.
Dois masters SNMP 85756/85977 nos hosts 10768/10769 propagaram erros para
992 dependentes. Hosts respondem ICMP e walk recebe dados parciais antes de
timeout. Global SNMP=3s; itens herdam 46234 sem timeout específico. Timeout
de objeto herdado é somente leitura; não aplicar override inválido nem editar
template compartilhado. Variante isolada exige acesso de escrita e teste.

SSO não aprovado: snapshot restaurou SP EntityID da origem e endpoint IdP
da aplicação zabbix; ness_uat_breakglass não existe no banco restaurado.
Nenhum usuário/autenticação foi alterado por SQL. Issue #51 atualizada e
instruções enviadas a Ismael/Ricardo; acesso API mínimo continua na #71.
Token do Hub permite leitura/ACK e não será elevado para editar itens/hosts.
DNS, coleta e notificações produtivas permanecem na origem; corte ainda não
executado. Próximo passo obrigatório: regularizar SSO/API UAT e validar login,
antes de promover as correções e preparar o freeze final autorizado.
