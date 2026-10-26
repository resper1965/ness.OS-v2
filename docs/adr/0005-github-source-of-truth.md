# ADR 0005 — GitHub como fonte oficial

- Status: aceita
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

A VPS AIOps contém arquivos transferidos manualmente e não é um checkout Git controlado. O workflow atual de deploy não corresponde ao caminho real de produção.

## Decisão

O repositório GitHub atual será a fonte oficial. `main` terá proteção, CI obrigatório e environment de produção com aprovação. Releases serão implantadas por artefatos/imagens imutáveis.

## Consequências

- Mudança manual em produção será exceção registrada e posteriormente reconciliada.
- O deploy atual deve ser substituído antes do go-live.
- Código, configuração não secreta e documentação precisam estar versionados antes de uma release.
