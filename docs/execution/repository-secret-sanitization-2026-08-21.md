# Saneamento de segredos do repositório — 21/08/2026

## Resultado da árvore versionada

A varredura final foi feita sobre os arquivos rastreados pelo Git, sem imprimir valores. Resultado:

- zero ocorrência dos marcadores das senhas conhecidas expostas;
- zero `StrictHostKeyChecking=no`;
- zero arquivo `.env` real rastreado (`app/.env.example` permanece apenas como modelo);
- cinco arquivos contêm deliberadamente `<REVOKED_USE_PSONO>` e falham fechado;
- o script legado `run_sql.sh`, que escrevia diretamente no banco GLPI, foi neutralizado e retorna código 64;
- `check_glpi_sso.sh` passou a usar `ness_admin`, chave, `BatchMode` e host key verificada;
- o script de transferência legado passou a exigir host key verificada;
- o backend deixou de oferecer senha de banco e client secret OIDC conhecidos como defaults; OIDC fica desabilitado sem configuração explícita;
- 12 testes relevantes de backend passaram; existe um aviso não bloqueante sobre `datetime.utcnow()`.

Os dois padrões de URI restantes são controlados: uma fixture de teste do sanitizador e uma URL Compose cujo segredo vem de variável obrigatória, não de literal.

## Arquivos locais não rastreados

A varredura ampla encontrou scripts/resultados locais não rastreados com comandos antigos que desabilitam a verificação de host key. Eles não fazem parte da árvore versionada e não foram apagados ou movidos para preservar o trabalho do usuário. Devem ser tratados como quarentena local: não executar, não publicar e não copiar para produção até revisão individual.

Em 22/08/2026 foi adicionada a verificação open source `.github/workflows/secret-scan.yml`, com Gitleaks 8.30.1 fixado e validado por checksum. Pull requests examinam somente o intervalo novo; a execução manual examina o snapshot, sempre com redaction total, sem persistir relatórios e com permissões read-only.

A primeira varredura manual controlada do snapshot retornou código 1 e **73 achados potenciais**: 4 em arquivos versionados e 69 em não versionados. Nenhum valor, conteúdo ou caminho sensível foi exibido ou preservado; todos os temporários foram removidos. Esse resultado não prova 73 credenciais válidas, mas invalida qualquer afirmação de repositório pronto para publicação até triagem e rotação. O histórico Git ainda não foi examinado.

Os quatro achados versionados foram posteriormente classificados como exemplos/fixtures, sem credencial real. Foram adicionadas quatro exceções `gitleaks:allow` estritamente locais em três arquivos, sem baseline global; parsing/sintaxe e equivalência estrutural passaram. A repetição da varredura ficou em **zero achado versionado**.

Em 24/08/2026, a classificação dos 69 achados restantes foi refinada: eles estavam em 24 arquivos **ignorados pelo Git**, principalmente uma `.venv` Windows, além de três arquivos locais de configuração/chaves. Os segredos, runtimes e 66 scripts/artefatos avulsos foram movidos para quarentena externa recuperável, com acesso restrito; quatro planos históricos foram organizados em `docs/legacy/`. A repetição do Gitleaks 8.30.1 sobre o workspace retornou **zero achado**. Evidências e limites em [`repository-quarantine-2026-08-24.md`](repository-quarantine-2026-08-24.md).

## Limites desta conclusão

O saneamento da árvore atual não limpa o histórico Git, forks, clones, logs de CI, conversas nem backups. Toda credencial que apareceu nesses meios continua considerada comprometida até revogação. A senha administrativa informada e o token Hostinger exposto nesta conversa não devem ser reutilizados; o token precisa ser revogado no hPanel.

## Pendências antes de publicar o repositório

1. analisar o histórico completo; se houver segredo, reescrever o histórico coordenadamente;
2. rotacionar/revogar todos os achados — mover ou apagar texto não invalida credencial;
3. proteger branches e impedir merge quando o scanner detectar segredo novo;
4. manter segredos humanos no Psono Community e automação em SOPS/age, nunca no Git;
5. revisar e versionar o trabalho preservado em commits atômicos a partir de checkout limpo.
