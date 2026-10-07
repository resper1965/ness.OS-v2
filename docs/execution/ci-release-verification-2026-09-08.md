# CI e inventário das imagens — 08/09/2026

## Correções

- O CI frontend executava Vite sem verificar TypeScript. Adicionado
  `npm run typecheck` (`tsc -b --pretty false`) antes do build.
- Ajustadas diferenças de formatação em cinco arquivos Python para atender
  simultaneamente Black e Ruff; comportamento preservado.
- Corrigido falso positivo do Gitleaks no `.env.example`: o scanner interpretava
  a variável de verificação TLS como valor do token vazio da linha anterior.
  A ordem foi ajustada e o token vazio ficou explícito, sem allowlist.
- Criado `.github/workflows/ci-sbom.yml`: constrói backend/frontend, gera SBOMs
  CycloneDX por ID da imagem e retém inventários/índice/checksums por 30 dias.
  Não publica imagens e não habilita deploy automático.

## Validação local do CI

Ambiente Python limpo: `/tmp/ness-ci-audit-20260908`, Python 3.12, dependências
instaladas de `requirements.txt`. Ferramentas nas versões dos workflows:
Ruff 0.16.5, MyPy 2.3.1, Black 26.5.1, Flake8 7.3.0.

- pytest: 226 testes aprovados;
- MyPy: 76 arquivos aprovados;
- Black: 107 arquivos aprovados após formatação;
- Ruff lint/format: 76 arquivos aprovados;
- Flake8 E9/F63/F7/F82: zero erros;
- TypeScript: `npm run typecheck` aprovado;
- após a formatação, repetidos os testes afetados: 17 de contratos/autorização
  e 6 de continuidade/CMDB, todos aprovados;
- YAML, scripts Bash e pinning de actions dos workflows alterados aprovados.

Gitleaks 8.30.1 foi obtido usando versão/checksum do workflow existente. A cópia
de 617 arquivos foi formada por `git ls-files --cached --others --exclude-standard`,
usando conteúdo atual e sem seguir links simbólicos. Após a correção do exemplo,
o scan terminou com código zero e nenhuma detecção. O relatório é redigido
(`--redact=100`) em `/tmp/ness-ci-secret-scan/report.json`.
Isso cobre o conteúdo candidato a commit; não prova limpeza de todo o histórico
Git nem revogação de credenciais antigas.

## SBOM das imagens em execução

Gerador: `infra/scripts/generate-image-sbom.sh`.
Syft 1.37.0, binário comparado à distribuição oficial verificada pelo SHA-256:
`b81a0dc81b92265f4597659bba5509e014c78228182804bb1bc97856af26e326`.

| Imagem | Componentes totais | Bibliotecas | Arquivos |
| --- | ---: | ---: | ---: |
| app-api | 3386 | 209 | 3161 |
| app-worker-alerts | 3386 | 209 | 3161 |
| app-worker-ml | 3386 | 209 | 3161 |
| app-frontend | 612 | 273 | 337 |

Contagens incluem componentes de aplicação/sistema, portanto não equivalem a
pacotes únicos. O índice registra o ID exato de cada imagem e seu inventário.
Artefatos completos em `/var/lib/ness-os/sbom/20260908` no servidor e
`outputs/sbom/2026-09-08` na estação (diretório ignorado pelo Git).

O inventário cobre as imagens, incluindo suas dependências; código montado por
bind mount tem a cobertura de fonte/checksums documentada nos backups. SBOM não
é análise de vulnerabilidade ou garantia de ausência de componentes inseguros.
Algumas versões de subpacotes são reportadas como UNKNOWN pelo scanner.

## Limites e pendências

O workflow novo ainda não executou no GitHub Actions. Sua sintaxe foi conferida
e o gerador foi testado nas imagens produtivas existentes; isso não comprova o
build integral em um runner novo. Permanecem pendentes os builds/artefatos no CI,
reconciliação Git/IaC/produção, imagens base imutáveis e substituição do deploy
desabilitado. F7-2 permanece parcial.

Produção às 21:54:42 UTC: Zabbix/GLPI OK, dois workers, filas vazias, zero
falhas/retries e zero tickets/resoluções pendentes.

## Revalidação local em 26/09/2026

No checkout atual, o backend passou com 262 testes; Black, Ruff check/format,
MyPy e Flake8 (E9/F63/F7/F82) também passaram. Pytest emitiu dois avisos de
depreciação ligados a `datetime.utcnow`.

Para o frontend, preservei o `node_modules` antigo e criei uma cópia temporária
com `npm ci`, incluindo dependências de desenvolvimento e opcionais. Oxlint,
TypeScript e build Vite passaram; Oxlint reportou um aviso Fast Refresh em
`src/hooks/useAuth.tsx:144`. `npm ci` instalou 45 pacotes, auditou 46 e reportou
zero vulnerabilidades.

Essa execução comprova os comandos localmente neste checkout. Os workflows do
GitHub Actions, o build em runner limpo e o workflow SBOM continuam pendentes;
F7-2 e o gate de release permanecem parciais até essa execução e a reconciliação
das alterações locais com a produção.

## Regressão do gerador SBOM — 26/09/2026

O gerador agora recusa uma pasta de saída não vazia para impedir mistura de SBOMs
de execuções diferentes. Um teste isolado com `docker` e `syft` simulados cobre
essa recusa, a geração de mais de uma imagem, o índice CycloneDX e os checksums.
O teste falhou antes da correção e passou depois; `bash -n` e parse YAML também
passaram. O workflow executa esse teste antes dos builds. Commit local:
`0c65009 feat(ci): validate image SBOM inventory`. O build real das imagens e a
execução no GitHub Actions seguia pendente na primeira revalidação; o build real
local foi concluído na seção abaixo. O runner GitHub continua pendente.

## Build limpo local das imagens — 26/09/2026

Os Dockerfiles agora usam `npm ci` e digests imutáveis para as imagens base
Python `sha256:f77ac9e4…` e Node `sha256:fb4cd12c…`. Foram adicionados
`.dockerignore` próprios: removem `node_modules`/artefatos locais do frontend e
restringem o contexto backend a `backend/` e `cli/`, sem testes/cache. Antes da
correção, os contextos transferidos chegaram a ~137 MB (backend) e ~126 MB
(frontend); depois, 5,58 KB e 1,85 KB, respectivamente.

Builds locais concluídos com IDs de imagem:

| Imagem | ID local | Componentes CycloneDX (Syft 1.37.0) |
| --- | --- | ---: |
| Backend | `sha256:f0ec17f91b0d04b741202ee161ab30a86b974ea6d1d2f2e955aa52b8072171ee` | 3.396 |
| Frontend | `sha256:0a1503b967627c49d4ac6739bba97996658ec1b98900341336ce8796751a6bb8` | 612 |

Os IDs são locais e não foram publicados como digests de registry. Build frontend
executou `npm ci` (49 pacotes, zero vulnerabilidades reportadas) e `vite build`
passou. Syft gerou SBOMs CycloneDX não vazios a partir de arquivos Docker archive;
SHA-256: backend `0d84761160f684ad33a62de71c4345c4365f9542d1a1e999bb8b1e1b98efb9c4`,
frontend `836559daeec6aae61b7a7af9aa3ed479a5285b6b2f5f9267312ae6ec83abdbac`.
Os arquivos permanecem em `/tmp` e não foram adicionados ao repositório. O workflow
GitHub Actions ainda precisa executar em runner limpo.
