# Identidades de serviço e rotação de segredos

## Regras

- Cada integração usa identidade técnica própria, com o menor escopo aceito pelo serviço.
- Não compartilhar conta humana, senha administrativa ou token entre integrações.
- Guardar valores somente em Psono durante a custódia humana e em arquivos root-only provisionados para consumidores. Segredos não entram em Git, evidência, ticket, argumento de processo ou log.
- Registrar em inventário protegido o consumidor, proprietário, origem segura, escopo aprovado, data da última rotação e prova de revogação. Nunca registrar o valor do segredo.
- A idade do arquivo de ambiente não prova a idade do segredo; usar a data de rotação documentada pelo custodiante.

## Inventário protegido para o relatório

O relatório aceita `--metadata-file /etc/ness-os/service-identities.tsv`. O arquivo é TSV UTF-8, com seis colunas e sem cabeçalho: `identidade`, `consumidor`, `origem`, `escopo`, `última_rotação` e `expira_em`. Datas usam `YYYY-MM-DD`; data de expiração vazia significa que o emissor não forneceu uma expiração explícita e será marcada `expiry_unverified`. `origem` é um caminho de arquivo protegido, nunca um URI ou valor do segredo. Proteja o inventário com proprietário root e modo `0600`.

O relatório marca origem ausente, compartilhada, versionada ou expirada e calcula a idade a partir da data declarada pelo custodiante em UTC. Escopo ou data de rotação vazios aparecem como não verificados. Sem inventário, o relatório marca os metadados como não verificados. Esses resultados locais não comprovam permissões efetivas no emissor nem revogação; mantenha esses pontos como pendências até o teste no serviço.

## Rotação controlada

1. Escolher uma credencial não crítica e um consumidor de teste; confirmar acesso de recuperação antes da mudança.
2. Aprovar a mudança com o proprietário do serviço e o custodiante da credencial. Definir como validar o consumidor e como interromper a rotação antes de revogar a credencial anterior.
3. Criar uma credencial nova com escopo mínimo. Atualizar o ciphertext SOPS e renderizar para um destino explícito em `/etc/ness-os` ou `/run/ness-os` com `infra/secrets/render-env.sh`.
4. Reiniciar somente o consumidor escolhido. Validar readiness e uma operação de leitura não destrutiva.
5. Revogar a credencial anterior no serviço emissor e comprovar que ela deixou de autenticar. Atualizar o inventário com data, proprietário, escopo, consumidor e resultado da revogação.
6. Remover cópias temporárias e confirmar permissões root-only. Não incluir valores na evidência.

Se a validação falhar antes da revogação, restaurar o arquivo protegido anterior e revalidar o consumidor. Depois que o serviço emissor revogar a credencial antiga, não restaurá-la; corrigir a nova credencial ou emitir outra.

## Limites atuais

O bootstrap real de SOPS/age ainda exige duas chaves de custódia testadas. O inventário da Fase 1 registra apenas declarações locais e não autoriza rotação em produção. UAT sem contas dedicadas, credenciais ou aprovação do gate da Fase 0 permanece pendente; marcar como bloqueado, sem declarar aprovação.
