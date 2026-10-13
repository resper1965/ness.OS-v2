# Checks locais sem GitHub Actions — bootstrap seguro

Os quatro checks requeridos pela `main` (`build-and-test`, `test-and-lint`,
`lint`, `gitleaks`) estão hoje vinculados ao app GitHub Actions (`app_id=15368`).
O builder local passou e publicou imagens privadas, mas **não** pode satisfazer
esses checks com um PAT: a API de *check runs* exige GitHub App. Não alterar a
proteção para aceitar qualquer emissor nem marcar checks manualmente como
sucesso.

1. Criar uma GitHub App privada sob `resper1965`, chamada
   `ness-os-local-ci`, com webhook inativo. Permissões do repositório:
   `Checks: Read & write`, `Contents: Read-only` e `Metadata: Read-only`
   (implícita); nenhuma permissão de administração, issues ou secrets.
2. Instalar a App **somente** em `resper1965/ness.OS-v2`. Gerar a chave privada
   e guardá-la fora do checkout no builder isolado, com acesso exclusivo ao
   operador. Nunca transmitir PEM, installation token ou JWT em Git/chat/log.
3. Implementar e revisar um emissor separado do checkout submetido ao PR.
   Ele deve obter um installation token de curta duração, conferir SHA local
   limpo igual ao head remoto do PR, validar a evidência dos quatro checks e
   só então publicar os quatro *check runs* no SHA exato. O código do PR não
   deve poder ler a chave ou executar no processo privilegiado do emissor.
4. Ensaiar sucesso nos quatro checks e falha fechada com um check ausente,
   SHA divergente e PR sem execução. Só então trocar o `app_id` dos quatro
   checks requeridos de `15368` para o ID da App nova, mantendo nomes,
   revisão obrigatória, proteção de administradores e force-push desligado.
   Confirmar readback e rollback da configuração da branch.

Até essa prova, PR #81 permanece draft/bloqueado; imagem publicada por digest
não equivale a aprovação de merge ou autorização de deploy.

Referências: [registro da App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app),
[API de check runs](https://docs.github.com/en/rest/checks/runs),
[origem exigida de status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
