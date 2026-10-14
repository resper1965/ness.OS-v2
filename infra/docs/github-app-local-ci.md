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

O launcher candidato `infra/scripts/local-ci-backend-sandbox.py` exige SHA
exato de checkout limpo e ID imutável da imagem local; roda os testes backend
com rede desativada, fonte somente leitura, UID sem privilégio, sem chave e sem
Docker socket. No commit `f9076cf`, 24 testes backend passaram nesse modo;
dois testes do launcher comprovaram o contrato e a recusa de SHA divergente.
Com `--frontend-image` (ID imutável), o mesmo launcher envia somente o arquivo
Git do frontend por stdin a outro contêiner sem rede/mount do host e executa
lint e build. No commit `1b1abde`, backend 24/24, frontend lint (zero avisos)
e build passaram juntos. Com `--lint-image`, ID imutável da imagem construída
de `infra/local-ci/python-quality.Dockerfile`, Black, Flake8, Ruff e Mypy
também rodam sem rede/socket/chave, checkout somente leitura e caches em tmpfs.
No commit `f07ca2d`, backend 24/24 e esses quatro checks passaram; quatro
testes do launcher passaram. A opção `--scan-image` também executa Gitleaks
sem rede/socket/chave, com Git safe.directory limitado à montagem `/src`.
O scanner pode registrar erro e sair com código zero; por isso qualquer stderr
falha fechado, sem imprimir possível segredo. No commit `e1501ae`, backend
24/24, Gitleaks e seis testes do launcher passaram. A execução mais restrita
usa `--scan-ignore` para montar uma lista revisada **fora do checkout** e
`--ignore-gitleaks-allow` para que comentários do PR não suprimam achados.
`GITLEAKS_CONFIG_TOML` fixa as regras padrão embutidas no binário; um
`.gitleaks.toml` acrescentado pelo PR não muda a política. O commit
`18382e4` passou no scan real com essa configuração; suíte local `35/35`.
Dois fingerprints históricos em `PricingModule.tsx:91` foram classificados
como a constante pública `STORAGE_KEY` do navegador e incluídos pontualmente
na lista candidata, sem registrar o valor. O ensaio com cópia externa
temporária passou; no SHA `4fe116e`, backend `24/24`, Black, Flake8, Ruff,
Mypy, Gitleaks, frontend lint/build e suíte local `35/35` passaram. Não usar
essa cópia gravável pelo executor como gate.
Instalar a política e o launcher revisados em área controlada pelo runner,
sem permissão de escrita para PRs, antes de emitir check confiável.
Antes de aceitar PRs não confiáveis, instalar uma cópia revisada do launcher
fora do checkout submetido e acrescentar os demais checks isolados. Esse
ensaio não emitiu status externo nem mudou a proteção da `main`.

Referências: [registro da App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app),
[API de check runs](https://docs.github.com/en/rest/checks/runs),
[origem exigida de status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
