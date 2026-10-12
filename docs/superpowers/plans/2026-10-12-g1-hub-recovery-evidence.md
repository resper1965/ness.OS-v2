# G1 Hub/AIOps — recuperação atual e evidência operacional

Data: 2026-10-12 (BRT)  
Escopo: Hub/AIOps na VPS `144.91.115.242`; não inclui Zabbix, DNS, agentes,
proxies, notificações ou escrita em GLPI.  
Pré-requisito: promoção Hub/AIOps do commit `144317f` e backup local
`20261012T085531-0300` concluídos.

## Objetivo e critério

Provar que o conjunto AIOps atual pode ser recuperado de Object Storage
Contabo sem acionar produção. Este plano aprova apenas o subgate G1 do
Hub/AIOps; G1 global continua aberto até que os demais produtores tenham a
mesma evidência dentro do RPO.

RPO alvo: 24 horas. RTO alvo: 4 horas.

## Passo 1 — fotografia antes da cópia

1. Registrar horário BRT/UTC, commit de runtime, digests e conjunto local.
2. Confirmar `COMPLETED`, `SHA256SUMS` e integridade do conjunto
   `20261012T085531-0300`.
3. Registrar o último snapshot remoto, seu tag `ness-backup-set-*`, a idade e
   o resultado do último `restic check`.
4. Se o snapshot remoto não corresponde ao conjunto local atual, marcar a
   lacuna de RPO e seguir para o passo 2.

Falha fechada: sem `COMPLETED` ou checksum válido, não executar upload.

## Passo 2 — cópia externa criptografada

1. Acionar somente `ness-aiops-object-storage-backup.service`.
2. A rotina versionada deve selecionar exclusivamente um conjunto completo,
   verificar checksum antes do upload, criar snapshot tagueado, executar
   `restic check` e preservar ao menos um snapshot anterior.
3. Capturar ID do novo snapshot, tag do backup, tamanho, horário e saída de
   sucesso sem imprimir endpoint, access key, secret ou senha Restic.
4. Confirmar que o timer continua habilitado para 00:30 BRT.

Rollback: não apagar snapshots. Em falha, manter o último snapshot válido e
registrar a lacuna de RPO.

## Passo 3 — prova de recuperação isolada

1. Medir início/fim da execução de `ness-aiops-restore-verify.service`.
2. O verificador deve escolher o snapshot remoto com tag do conjunto atual,
   executar `restic restore --verify` em diretório temporário isolado e validar
   o manifesto/checksums.
3. Não iniciar Compose restaurado, agentes, conectores, notificações nem
   qualquer escrita fora do diretório temporário.
4. Confirmar limpeza do temporário e que o snapshot permanece disponível.
5. Comparar duração com RTO de quatro horas e registrar o resultado.

Falha fechada: checksum, restic ou restauração incompleta mantém G1-Hub/AIOps
reprovado e não remove evidência nem snapshot.

## Passo 4 — observabilidade e registro

1. Verificar timers de backup, Object Storage e restore-verification.
2. Conferir a saúde do runtime promovido: API `/ready`, workers e frontend.
3. Atualizar a evidência datada com fatos observados, lacunas, RPO, RTO,
   rollback e dono.
4. Atualizar `PROJECT_CONTEXT.md`, `implementation-plan-2026-10-11.md` e
   `gate-0-status.md`; criar commit documental separado e enviar à branch de
   entrega.

## Aceite G1-Hub/AIOps

- backup local atual tem `COMPLETED` e checksums válidos;
- snapshot externo corresponde ao mesmo `backup_set_id`;
- `restic check` atual não apresenta erros;
- restore isolado com verificação conclui e limpa temporários;
- RPO é no máximo 24 horas e RTO é medido;
- timers ativos e falhas observáveis;
- nenhum segredo é exposto e nenhum snapshot válido é removido.

## Próxima etapa após aceite

Retomar G0 global: executar CI em runner limpo e concluir a integração
protegida do workflow de publicação. Depois, seguir para G2 de identidade e
cofre; o MVP Zabbix → Hub → GLPI só começa após os subgates correspondentes.
