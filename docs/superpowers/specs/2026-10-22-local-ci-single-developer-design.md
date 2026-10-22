# CI local para repositório privado — proposta de desenho

**Data:** 22/10/2026  
**Estado:** proposta aprovada em conversa; aguardando revisão deste documento.  
**Escopo:** substituir os quatro checks GitHub Actions do `ness.OS-v2` por um único status obrigatório emitido pela GitHub App existente após a execução local dos mesmos testes.

## Objetivo e premissas

O repositório continua privado e o GitHub Actions continua desativado. Não adquirir VPS nem depender de serviço CI externo. O único desenvolvedor inicia o CI localmente para cada commit de PR que pretende integrar. A proteção continua exigindo PR e resultado CI antes do merge, com strict mode, administradores cobertos, sem force-push e sem aprovações obrigatórias.

O computador local, seu WSL/Docker e o operador são a base de confiança. O contêiner reduz o acesso do código testado às credenciais; ele não transforma o próprio computador em um domínio confiável independente.

## Desenho

Um launcher instalado fora do checkout, controlado por root e não editável pelo PR, recebe número do PR e SHA. Ele confirma que o PR está aberto, vem do próprio repositório, tem base `main` e aponta para o SHA informado. Inicia no GitHub o status `ci/local` como `pending`.

O launcher confere um checkout limpo daquele SHA e executa backend, frontend, lint/tipagem e Gitleaks nas imagens locais fixadas por digest. A fonte é somente leitura; os contêineres não recebem rede, socket Docker, chave da App, token GitHub, diretório pessoal ou política de scan editável pelo PR. O launcher e a política de Gitleaks vêm de instalação root-owned, não do checkout. Uma etapa falha, falta, gera erro de scanner ou não pode ser concluída: o status termina `failure` ou permanece `pending`, nunca `success`.

Depois dos testes, o launcher consulta novamente o PR. Só publica `success` para `ci/local` se todos os comandos terminaram com código zero, o SHA local permaneceu limpo e o `head.sha` remoto ainda é o mesmo. Falha de rede, processo interrompido, PR atualizado ou validação inconclusiva não produz verde. O status aponta para um log local ou instrução de execução sem publicar conteúdo potencialmente sensível.

## Identidade GitHub e proteção

Reutilizar a GitHub App `ness-os-local-ci` (ID `5307771`, instalação somente em `resper1965/ness.OS-v2`). Conceder apenas `Pull requests: read` e `Commit statuses: write`; retirar permissões que deixarem de ser necessárias, incluindo `Checks: write` e `Contents: read`. A chave permanece no host, em arquivo root-only fora do checkout, e o processo de testes não a recebe. O App publica um status simples via Commit Status API; não requer Actions nem PAT de usuário.

Depois de validar o emissor, readback de permissões e testes negativos, a proteção da `main` trocará os quatro contextos atuais (`build-and-test`, `test-and-lint`, `lint`, `gitleaks`, app `15368`) pelo único contexto `ci/local`, exigindo como origem o App `5307771`. Todo o restante da regra fica idêntico e é lido de volta. Se o status não puder ser publicado ou o readback divergir, restaurar os contextos anteriores. A primeira chave da App deve ser revogada e confirmada antes do uso operacional da segunda.

## Falhas e recuperação

- PR de fork, fechado, base diferente, SHA inválido ou divergente: abortar antes dos testes e registrar `failure`/manter `pending`.
- Check ausente, comando falho, scanner com stderr, imagem ausente ou evidência inválida: não publicar sucesso.
- PR atualizado durante os testes: não marcar o SHA antigo como aprovável; iniciar nova execução quando solicitada.
- WSL/Docker/API indisponível: CI fica pendente; reparar o executor ou executar a alternativa de recuperação documentada antes de mudar a proteção.
- Nunca permitir que o processo do PR invoque o launcher privilegiado com argumentos livres, leia a chave ou escolha contexto/SHA de sucesso.

## Riscos aceitos

O operador e o host têm poder para publicar `success`; comprometimento deles pode falsificar o CI. Um escape do contêiner ou falha do Docker/WSL também pode comprometer o host. O launcher root-owned, rede desligada, montagens somente leitura, ausência de socket e credencial fora do contêiner reduzem a exposição do código do PR, mas não eliminam vulnerabilidades do host ou do runtime. Executar o CI exige o computador ligado e acesso ao GitHub; não haverá resultado automático quando ele estiver desligado.

O único desenvolvedor aceitou, em 22/10/2026, confiar no próprio computador para simplificar a solução. Isso não equivale a aceitar execução de código de PR com acesso deliberado à chave, ao token ou ao socket Docker.

## Critérios de aceite

1. Launcher/política fora do checkout e instalados com hashes/permissões verificados.
2. Os quatro comandos existentes executam no SHA exato em contêineres sem rede, socket, credenciais e fonte gravável.
3. Testes negativos para SHA errado, PR de fork/base errada, checkout sujo, etapa ausente/falha, stderr do scanner, PR atualizado durante execução e falha da API; nenhum gera sucesso.
4. Teste real da App cria `pending` e só conclui `success` após todos os testes; falha de etapa conclui em não sucesso.
5. App permissions e revogação da primeira chave verificadas por readback.
6. Antes/depois da alteração da proteção comparados: apenas os quatro contextos/origem do App mudam; strict, PR obrigatório, admin, aprovações e force-push ficam iguais.
7. PR de prova com novo SHA passa; falha deliberada fica bloqueada. Sem merge/deploy automático.

## Sequência de implementação

1. Atualizar App permissions e revogar a primeira chave; confirmar readback.
2. Integrar validador de PR/SHA, execução local do runner existente e publicação de `ci/local`, com testes de falha.
3. Fazer ensaio no PR #81 e guardar evidência sanitizada.
4. Somente após sucesso do ensaio, trocar o contexto requerido e conferir readback/rollback.

Este documento especifica o desenho, não concede autorização para mudar a proteção, emitir sucesso sem os critérios, fazer merge, publicar o repositório ou implantar ness.OS em produção.
