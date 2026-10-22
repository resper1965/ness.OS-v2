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
   A App atual não tem `Pull requests: Read-only`. Essa permissão mínima e o
   aceite da atualização da instalação são pré-requisitos para ler o
   `head.sha` de `GET /pulls/{number}`. A API de Git refs documenta
   `heads/*` e `tags/*`, não `pull/*`; nome de branch isolado não é prova do
   head do PR. Até o readback dessa permissão, não emitir checks.
   **Fronteira adicional (13/10 22:40 BRT):** o usuário do runner `resper`
   pertence ao grupo `docker`, e o socket observado é `root:docker 0660`.
   A documentação do Docker classifica o grupo como privilégio equivalente a
   root no daemon. Portanto `root:root 0600` na chave, por si só, não prova
   separação do emissor no mesmo domínio de acesso ao Docker. Não conectar
   `/etc/ness-os/github-app-ness-os-local-ci.pem` ao processo ou máquina do
   builder até separar o signer do socket/usuário Docker (por host ou
   isolamento equivalente demonstrado), ensaiar negativa de leitura a partir
   do builder e provar que o signer verifica o SHA do PR e a evidência
   confiável antes do POST. Não testar a falha tentando montar ou ler a chave.
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
No commit `f43e227`, backend e qualidade Python passaram a montar só
`app/backend` e `cli`, nunca `.git`; backend `24/24` e Black/Flake8/Ruff/Mypy
passaram no Docker real. Apenas o binário Gitleaks recebe o Git histórico,
somente leitura e sem chave/socket.
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
Em 13/10 ~21:41 BRT, uma cópia de `49c802f` foi instalada em `/opt/ness-ci`:
diretório `root:root 0755`, launcher `root:root 0555` e lista Gitleaks
`root:root 0644`, com comparação byte a byte contra o checkout limpo. A cópia
externa rodou no SHA exato com IDs locais imutáveis: backend `24/24`, Black,
Flake8, Ruff, Mypy, Gitleaks e frontend lint/build PASS, sem rede/socket/chave
nos contêineres. O launcher também recusa diretórios de fonte com links
simbólicos que escapariam da montagem prevista. Esta instalação é **candidata**:
sem emissor isolado, teste negativo de SHA/check ausente, revogação da primeira
chave e troca controlada da origem requerida dos checks, não há gate de merge.
Esse ensaio não emitiu status externo nem mudou a proteção da `main`.

Em 13/10 ~22:02 BRT, `local_ci_check_gate.py` ganhou uma validação **offline**
do payload de `GET /pulls/{number}`: somente PR aberto, do mesmo repositório,
com base `main`, número e `head.sha` exatamente iguais ao commit testado é
aceito. Casos de SHA divergente, PR fechado, fork, base errada, número errado e
head ausente falham fechados; 19 testes de infraestrutura e 43 testes Python
do checkout passaram (dois avisos de depreciação preexistentes). O módulo
ainda não lê a API, não autentica a App e não publica checks. Falta conceder
`Pull requests: Read-only`, confirmar o readback e integrar o runner/emissor
sob identidade privilegiada separada antes de qualquer status externo.

## Tentativa de isolamento no mesmo WSL — 22/10/2026

O caminho Docker rootless no mesmo Ubuntu/WSL foi considerado, sem instalar
pacotes ou alterar o daemon. O preflight atual encontrou a CLI do Docker
Desktop como link para uma montagem indisponível; `docker` e o socket não
estavam acessíveis nesse momento. Mais importante, um processo Linux executado
como `nobody` invocou `wsl.exe -d Ubuntu -u root -- id -u` e obteve `0`
(exit 0). O teste não leu chave nem segredo. Nesta
configuração, separar usuários Linux ou instalar um daemon rootless **não**
isola a chave root-only da execução não confiável; não usar esta distro como
builder e signer co-localizados.

Próximo desenho precisa manter o emissor/chave fora desse domínio de escalada
(ou comprovar uma barreira equivalente por teste negativo), além de obter
`Pull requests: Read-only`, revogar a primeira chave, vincular os resultados
ao SHA remoto do PR e ensaiar check ausente/SHA divergente. Sem isso, não
publicar check runs nem alterar a proteção da `main`.

Referências: [registro da App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app),
[API de check runs](https://docs.github.com/en/rest/checks/runs),
[origem exigida de status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
[privilégio do grupo Docker](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user).
