# Higienização do repositório — 22/10/2026

Escopo: checkout `feat/incidents-rbac-local` e fila aberta do GitHub
`resper1965/ness.OS-v2`. Esta é uma auditoria pontual, não um gate de release.
Fonte de estado produtivo: [indicador](ness-os-status.md).

## Aplicado

- PR #42 encerrado sem merge: seu head é ancestral da branch do PR #64 e seu
  diff antigo contra `main` estava em conflito. A branch não foi excluída.
- Issues #80 e #67 encerradas como substituídas: pediam grant de GHCR/Actions,
  cobrança e segundo revisor no fluxo antigo. Imagens privadas já foram
  publicadas e lidas por digest; isso não é deploy. CI futura segue no PR #81.
- Issue #68 encerrada: organizava dependências humanas que continuam nas
  issues específicas. Nenhum gate G2 foi aprovado por isso.
- README atualizado para apontar ao plano e indicador atuais, sem comandos de
  provisionamento/deploy nem custos apresentados como vigentes.
- `.gitignore` passou a excluir caches Python gerados localmente. Nenhum cache,
  arquivo pessoal, imagem ou histórico Git foi apagado.

## Fila preservada após a triagem

- 27 PRs abertos: #64 e #81 são entregas draft ativas; #14 e #15 têm diffs
  próprios e precisam de comparação funcional antes de fechamento; os outros
  23 são atualizações de dependências do Dependabot, que exigem teste e
  consolidação por ecossistema. Não fazer merge em massa nem encerrar upgrade
  válido sem substituto testado.
- 27 issues abertas: #74/#76–#79 tratam GLPI; #70–#73 e #57 tratam Zabbix;
  #82 mantém o risco de refs/caches históricos; #69 mantém o pré-requisito do
  runner. As demais cobrem identidade, cofre, e-mail e aceite. Não encerrá-las
  apenas por haver código candidato ou teste local verde.
- Três JPEGs na raiz não têm referência textual no Git, mas podem ser ativos
  visuais de origem humana. Preservados até classificação visual/autoria.
- `cavan-compras/` e os planos históricos foram preservados: podem conter
  evidência comercial ou de decisão, não lixo gerado.

## Próxima higienização segura

1. Comparar os comportamentos exclusivos dos PRs #14/#15 com a branch #64;
   encerrar somente o que estiver comprovadamente absorvido ou abandonado.
2. Atualizar dependências em lotes pequenos por ecossistema, com testes;
   fechar PRs do Dependabot substituídos pelo lote aprovado.
3. Classificar os três JPEGs e quaisquer anexos comerciais com o proprietário
   antes de remover conteúdo ou reescrever histórico.
4. Manter #82 como risco aberto: privatização e fechamento de PR não apagam
   cópias já acessadas, refs de PR ou caches remotos.

Nenhuma alteração desta higienização muda a proteção da `main`, o estado do
Actions, o PR #81, a conta GLPI 106, a coleta Zabbix ou os gates produtivos.
