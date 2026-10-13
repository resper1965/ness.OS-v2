# Checks locais sem GitHub Actions — bootstrap seguro

Os quatro checks requeridos pela `main` (`build-and-test`, `test-and-lint`,
`lint`, `gitleaks`) estão hoje vinculados ao app GitHub Actions (`app_id=15368`).
O builder local passou e publicou imagens privadas, mas **não** pode satisfazer
esses checks com um PAT: a API de *check runs* exige GitHub App. Não alterar a
proteção para aceitar qualquer emissor nem marcar checks manualmente como
sucesso.

1. App privada `ness-os-local-ci` criada sob `resper1965` (ID `5307771`),
   webhook inativo; `Checks: Read & write`, `Contents: Read-only` e
   `Metadata: Read-only` (implícita), sem administração, issues ou secrets.
2. Instalação `171160625` limitada a `resper1965/ness.OS-v2`. Segunda chave
   validada por fingerprint e guardada fora do checkout em arquivo
   `root:root 0600`; JWT e token efêmero testados somente com leitura. As
   cópias baixadas no Windows foram removidas. A primeira chave ainda aparece
   ativa: o GitHub desabilita sua exclusão mesmo após gerar a segunda.
   Revogá-la antes de liberar o emissor. Nunca transmitir PEM, installation
   token ou JWT em Git/chat/log.
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

Ensaio de isolamento em 13/10: no checkout do PR #81, backend `24/24` e
frontend lint/build passaram em contêineres sem rede, sem Docker socket e sem
chave. O backend recebeu o checkout limpo em montagem somente leitura; o
frontend recebeu apenas um arquivo Git do SHA. Hashes do lock/requirements
coincidiram com as imagens de dependências locais. Isso prova viabilidade do
sandbox, não um runner reproduzível nem a emissão segura dos quatro checks.
Executar testes do PR no usuário do host, que acessa o Docker socket, não é
substituto para o sandbox mesmo quando a chave está `root:root 0600`.

Referências: [registro da App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app),
[API de check runs](https://docs.github.com/en/rest/checks/runs),
[origem exigida de status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
