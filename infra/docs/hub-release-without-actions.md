# Publicação do Hub sem GitHub Actions

O publicador local é `infra/scripts/publish-hub-images.py`. Ele exige um checkout
limpo no commit revisado, executa os checks locais, constrói API e frontend com
Docker Buildx, publica no registro privado escolhido e grava as duas referências
imutáveis por digest. Não implanta nem altera produção.

Executar somente numa máquina de build isolada, sem volumes/segredos produtivos,
com Docker/Buildx, Python 3.12, Node 20, Gitleaks 8 e dependências de teste
instalados. Autenticar no registro antes por mecanismo de credenciais do Docker;
não colocar senha ou token em argumento, arquivo do repositório ou log.

```bash
python3 infra/scripts/publish-hub-images.py \
  --commit <sha40-revisado> \
  --registry <registro-privado>/ness \
  --output /caminho-privado/release-images.json
```

O arquivo resultante contém somente commit e referências `@sha256`. Confirme
que os dois digests são puxáveis pela produção, gere o manifesto de release
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
Antes da primeira publicação, resolver o scan de segredos, executar o fluxo
completo num commit revisado, comprovar escrita/leitura do registro privado e
um status externo confiável. Verificar que PRs sem esse status continuam
bloqueadas antes de alterar a proteção.

O scan local de segredos está em fail-closed. Em 13/10/2026 encontrou três
ocorrências no checkout `main`, incluindo dois valores no inventário Ansible
com aparência de credenciais. Não registrar os valores; confirmar uso, conter
exposição e rotacionar antes da primeira publicação. Histórico público não é
apagado por tornar o repositório privado. A contenção e rotação estão
registradas na issue #82.
