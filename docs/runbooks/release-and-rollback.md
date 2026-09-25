# Release e rollback

Este procedimento exige que o manifesto de release esteja pronto, que os artefatos
da release estejam identificados por digest e que o gate operacional esteja em
`PASS`. Não faça deploy enquanto houver divergência de arquivos, imagem ou migração
sem plano de reversão.

## Preparar a release

1. Confirme árvore limpa, CI aprovada e tag ligada ao commit revisado.
2. Gere o manifesto: `python3 infra/scripts/ness-release-manifest.py --output release-manifest.json`.
3. Confira `release_ready`, `blockers`, `images` e `deployed_file_hashes`. Uma imagem
   sem `@sha256:` é bloqueio. Para imagens construídas pelo projeto, publique a
   imagem no registry, registre seu digest e atualize o Compose para referenciá-lo.
4. Compare os fatos de produção com o manifesto e revise toda divergência antes
   de iniciar qualquer migração.
5. Confirme backup recente e restaurável dos dados que serão alterados. Para
   mudanças de schema, registre também o procedimento de reversão ou restauração.

## Implantar

1. Acesse o host autorizado e confirme o commit e os arquivos da release.
2. Baixe as imagens exatas referenciadas pelos digests revisados; não substitua
   tags mutáveis durante o deploy.
3. Faça backup imediatamente antes da migração. Preserve o identificador do
   conjunto de backup e os logs da operação, sem incluir credenciais.
4. Execute a migração aprovada uma vez e registre o resultado.
5. Suba os serviços usando o Compose revisado e imagens por digest.
6. Verifique estado dos containers, healthchecks e sondas funcionais do Hub,
   integrações e autenticação. Confirme também os timers de backup e sua próxima
   execução.
7. Registre commit, digests, hashes implantados, horário e resultado no artefato
   de evidência da release.

## Rollback

1. Interrompa novas alterações de tráfego ou dados conforme o procedimento do
   serviço afetado.
2. Reimplante o manifesto anterior, preservando exatamente os digests anteriores.
3. Se a migração for compatível com a versão anterior, reverta os serviços e
   valide as sondas. Não execute uma migração reversa improvisada.
4. Se houve mudança incompatível de schema ou corrupção de dados, restaure o
   backup anterior em ambiente isolado, valide-o e aplique o procedimento de
   recuperação aprovado antes de substituir dados de produção.
5. Confirme saúde dos serviços e integrações. Registre a causa, o commit/digest
   restaurado, o conjunto de backup usado e os resultados das sondas.

## Prova de restauração

Faça primeiro a restauração isolada, com rede de produção desabilitada e sem
montar volumes produtivos. Compare versões e contagens funcionais com o registro
do backup. Só considere rollback de dados concluído após essa validação e após
confirmar que os serviços produtivos permanecem saudáveis.
