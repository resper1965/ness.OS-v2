# Publicação do Hub sem GitHub Actions

O publicador local é `infra/scripts/publish-hub-images.py`. Ele exige um checkout
limpo no commit revisado, executa os checks locais, constrói API e frontend com
Docker Buildx, publica no registro privado escolhido e grava as duas referências
imutáveis por digest somente após puxar ambas do registro. Não implanta nem
altera produção.

Executar somente numa máquina de build isolada, sem volumes/segredos produtivos,
com Docker/Buildx, Python 3.12, Node 20, Gitleaks 8 e dependências de teste
instalados. Autenticar no registro antes por mecanismo de credenciais do Docker;
não colocar senha ou token em argumento, arquivo do repositório ou log.
Este script ainda executa os checks no host do builder: não o rode diretamente
de um PR não revisado nem num host que guarde a chave da App ou tenha segredos
produtivos. O runner isolado e o emissor externo continuam pendentes.

```bash
python3 infra/scripts/publish-hub-images.py \
  --commit <sha40-revisado> \
  --registry <registro-privado>/ness \
  --output /caminho-privado/release-images.json
```

O arquivo resultante contém somente commit e referências `@sha256`. O pull local
é obrigatório antes de gravá-lo; confirme também a leitura pela produção e gere
o manifesto de release
existente com esses valores, valide gates, snapshot e rollback e só então
implante. Um push parcial ou check reprovado não produz manifesto nem autoriza
deploy. Não execute o build no host produtivo.

## Estado da transição em 13/10/2026

O usuário desativou GitHub Actions para interromper novas execuções faturáveis.
O repositório agora é privado e se chama `resper1965/ness.OS-v2`. Os quatro
checks exigidos pela proteção da `main` foram preservados: merges novos ficam
bloqueados até existir substituição equivalente. Não remover os checks nem os
workflows antigos para contornar esse bloqueio.

Docker Desktop/Buildx no Windows construiu localmente API e frontend, sem push.
O frontend teve três alertas altos de dependências transitivas; o lockfile foi
atualizado, `npm ci`, lint, build e auditoria passaram com zero vulnerabilidades,
e a imagem local foi recompilada. A integração Docker da distro Ubuntu/WSL
foi comprovada em 13/10/2026: `docker version` retornou cliente e servidor
29.8.0, e Buildx 0.37 está disponível. Estes builds manuais ainda não
executaram o publicador completo.
No commit `92eced4`, os checks locais e o fluxo completo passaram. API e
frontend foram publicados nos pacotes GHCR privados e puxados por digest;
ver `docs/execution/hub-local-publish-2026-10-13.md` na branch de execução.
Ainda falta um status externo confiável. Verificar que PRs sem ele continuam
bloqueadas antes de alterar a origem dos quatro checks requeridos.

O scan local de segredos permanece fail-closed. As credenciais afetadas foram
rotacionadas ou invalidadas e heads/tags foram sanitizados; refs internos de
PR/cache exigem GitHub Support (issue #82). Não registrar valores nem usar
clones antigos, que podem reintroduzir o histórico.
