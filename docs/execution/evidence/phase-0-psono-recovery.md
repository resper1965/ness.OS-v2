# Fase 0 — evidência de restauração isolada Psono

**Resultado: PASS** — backup remoto mais recente restaurado e aplicação inicializada
sem rede externa, com os dados e a assinatura do serviço verificados.

## Identificação

- VPS: AIOps `144.91.115.242` (`aiops`).
- `backup_set_id`: `20260925T013239-0300`.
- Snapshot Restic: `9f4a0b54`.
- Conjunto restaurado: `/var/backups/ness-os/psono/20260925T013239-0300`.
- Unit: `ness-psono-restore-verify.service`.
- SHA-256 do script local e instalado: `bfa30a179b7ab6cc1a177f9ff6efe937f48acdb93dad9bed635bebe939b503d2`.

## Execução

- Início: `2026-09-25T21:04:13Z`.
- Término: `2026-09-25T21:04:53Z`.
- Duração reportada: 39 segundos.
- Unit: `Result=success`, `ExecMainStatus=0`.
- Restic recuperou 9 arquivos/diretórios; `psono.pgdump` e
  `configuration.tar.gz` passaram em SHA-256.
- Dump importado em Postgres temporário com imagem de produção, container e volume
  descartáveis; rede definida como `none`; 51 tabelas restauradas e consultadas.
- Aplicação Psono inicializada com a configuração restaurada: endpoint
  `/server/info/` respondeu HTTP 200, assinatura validada e chave pública
  conferida com a configuração do backup.
- Após a execução, nenhum container nem volume `ness_psono_restore_*` permaneceu.
  `ness-psono` e `ness-psono-db` continuaram saudáveis.
- Próxima execução periódica da verificação: `2026-09-27 05:23:55 -03`.

Nenhum valor de segredo foi registrado nesta evidência.
