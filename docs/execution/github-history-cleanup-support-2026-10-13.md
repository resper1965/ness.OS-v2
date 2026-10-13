# GitHub Support — limpeza residual do histórico (13/10/2026)

Repositório privado: `resper1965/ness.OS-v2`.

As credenciais afetadas foram rotacionadas ou invalidadas antes da reescrita.
O `git-filter-repo --sensitive-data-removal` reescreveu as 34 branches e uma
tag; o push foi verificado por ref, e um clone novo de heads/tags passou no
scan histórico com exclusões pontuais de falsos positivos revisados. A proteção
original da `main` está restaurada: PR obrigatório, quatro checks, enforcement
para administradores, force-push desligado. Não houve deploy.

Solicitação no [GitHub Support portal](https://support.github.com/):

- Remover/dereferenciar refs internos dos **45 PRs afetados** (73 refs
  `refs/pull/*` continuam visíveis), executar garbage collection e remover
  visualizações em cache conforme a documentação do GitHub.
- First Changed Commit do `git-filter-repo`:
  `862680ece493e6e49d95c848f4dc9e999b84c48b` →
  `333e9df4ff6f34044da1cf6a6f0c30bb3d38230c`.
- O filtro não relatou objetos Git LFS órfãos. O repositório informa zero forks.
- Referência privada de acompanhamento: issue #82. Não enviar valores dos
  segredos no ticket; fornecer apenas os metadados pedidos pelo suporte.

Os PRs abertos tiveram SHAs alterados; diffs, comentários e checks antigos não
são evidência de revisão atual. Não fazer merge de clones antigos: recriar ou
rebasear a partir de um clone limpo para evitar recontaminação.
