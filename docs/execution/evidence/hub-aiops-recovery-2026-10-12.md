# Hub/AIOps — recuperação externa atual

Data da execução: 2026-10-12 (BRT)  
Escopo: VPS AIOps `144.91.115.242`; Object Storage Contabo; restore isolado.

## Resultado

**G1-Hub/AIOps: PASS.** A cópia externa e a restauração isolada correspondem
ao conjunto local atual, sem iniciar serviços restaurados ou remover snapshots.
Isto não aprova G1 global: Zabbix, GLPI, Authentik e Psono exigem evidência
equivalente e atual dentro do RPO.

| Prova | Fato observado | Resultado |
| --- | --- | --- |
| Backup local | `20261012T085531-0300`, `COMPLETED` e checksums aprovados; término 09:01:13 BRT | PASS |
| Cópia criptografada | snapshot Restic `43192e11`, tag `ness-backup-set-20261012T085531-0300`, 904,870 MiB | PASS |
| Integridade externa | `restic check` de 39 snapshots terminou sem erro | PASS |
| Restore local isolado | 4 bancos PostgreSQL, 16 archives/volumes, 143 s | PASS |
| Restore externo isolado | snapshot `43192e11`, 28 paths restaurados, 26 arquivos verificados, 4 bancos PostgreSQL, 16 archives/volumes, 196 s | PASS |
| Limpeza | nenhum diretório `remote-*` remanescente em `/opt/n-infraops/restore-tests` | PASS |
| Runtime após prova | API `/ready`, API e workers `healthy`, frontend HTTP 200 internamente | PASS |

## Correção encontrada durante a prova

A unidade `ness-aiops-restore-verify.service` chamava o verificador sem
`--remote`; ela testava somente o conjunto local. O artefato versionado já
suportava a opção, mas a cópia instalada era anterior. A alteração
`9f382f0` passa `--remote`, foi publicada na branch de entrega e instalada com
rollback root-only em
`/opt/n-infraops/rollback/g1-remote-restore-20261012T0922-0300`.

O primeiro ensaio local comprovou o conjunto local. Após a correção, a unidade
restaurou e verificou especificamente o snapshot externo, registrando:

```text
isolated_restore=PASS backup_set_id=20261012T085531-0300 remote=1
```

Avisos de timestamps futuros em arquivos de cache de tradução GLPI foram
emitidos pelo `tar`, mas não impediram checksum, restore nem limpeza. Eles são
risco de higiene de dados, não aprovação de integridade temporal; devem ser
investigados antes de transformar esses caches em fonte de métricas.

## Timers e continuidade

- backup local: diário, próximo ciclo 23:00 BRT;
- cópia Object Storage: diária, próximo ciclo 00:30 BRT;
- restore-verification remoto: semanal, próximo ciclo 18/10 04:33 BRT.

RPO observado ao final da cópia: minutos, abaixo do alvo de 24 horas. RTO
medido para o restore remoto: 196 segundos, abaixo da meta de quatro horas.
O Object Storage Contabo continua sendo cópia única externa; a limitação 3-2-1
permanece risco aceito sujeito a revisão trimestral.

## Limites preservados

Não houve mudança em Zabbix, DNS, agentes, proxies, notificações, GLPI ou
segredos. O restore usou containers e volumes descartáveis sem rede; nenhum
runtime restaurado foi iniciado.
