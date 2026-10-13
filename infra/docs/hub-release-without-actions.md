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

## Corte do Actions

Ainda **não** desabilitar Actions nem remover os checks exigidos na branch:
o publicador precisa de um builder real e um registro privado com escrita/leitura
comprovadas. Antes do corte, rode o fluxo completo em commit revisado e publique
um status externo confiável para substituir os checks obrigatórios; verifique
que PRs sem esse status continuam bloqueadas. Só então desabilite Actions e
retire os workflows antigos. Runner próprio registrado no Actions não elimina
a dependência do Actions e não deve executar PRs de um repositório público.

O scan local de segredos está em fail-closed. Em 13/10/2026 encontrou três
ocorrências no checkout `main`, incluindo dois valores no inventário Ansible
com aparência de credenciais. Não registrar os valores; confirmar uso, conter
exposição e rotacionar antes da primeira publicação. Histórico público não é
apagado por tornar o repositório privado.
