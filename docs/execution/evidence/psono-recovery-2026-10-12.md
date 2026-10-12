# Psono — recuperação externa atual

Data: 2026-10-12 (BRT)  
Escopo: Psono atual na VPS AIOps; restauração remota isolada.

## Resultado

**Recuperação Psono: PASS.** O conjunto `20261012T013812-0300` teve checksum
validado, snapshot Restic `536bca5e` salvo e `restic check` sem erros. A
restauração isolada confirmou 51 tabelas, HTTP 200 da aplicação restaurada,
assinatura de informação válida e chave pública igual à cópia, em 36 segundos.

O ambiente temporário foi removido pelo verificador. O timer de backup diário
e o timer semanal de recuperação permanecem ativos.

## Limite

Esta prova confirma recuperação, não promove o cofre a produção. O Psono ainda
compartilha a VPS AIOps e a custódia/MFA dos dois responsáveis ainda não está
homologada; ambos são pré-requisitos de G2.

## Readiness F2 atual — 2026-10-12 10:08 BRT

A verificação posterior com `check-custodian-readiness.py` retornou `FAIL`
para MFA de Ricardo, recovery codes dos dois custodians, emergency code e
MFA imposto. O inventário foi lido diretamente do servidor; o validador
permanece local e não alterou a configuração. Cinco testes de regressão
passaram, incluindo relatório ausente, duplicação e recuperação inválida.

O relatório root-only `f2-readiness-report.sh` foi executado na VPS AIOps sem
imprimir segredos. Psono e PostgreSQL estavam `healthy`; HTTPS respondeu,
timer de backup estava ativo, a última execução teve `success` e os dois
arquivos de ambiente permaneceram `root:root 0600`.

| Controle | Ismael (`iaraujo`) | Ricardo (`resper`) |
| --- | --- | --- |
| Conta ativa e superuser | sim | sim |
| Primeiro acesso concluído | sim | sim |
| MFA cadastrado | sim | não |
| Códigos de recuperação | 0 | 0 |

`MULTIFACTOR_ENABLED` continua `false`; não pode ser imposto enquanto Ricardo
não cadastrar e provar seu fator. Não há emergency codes. A recuperação de
senha e SMTP estão atualmente habilitados, divergindo do registro histórico
que os descrevia como desabilitados. Essa divergência é uma pendência de
decisão/controlada antes da promoção: não foi alterada automaticamente, pois
interfere no percurso de recuperação dos custodians.
