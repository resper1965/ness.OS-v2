# Fixação de imagens AIOps — 21/08/2026

## Resultado

As dez imagens de terceiros em execução no AIOps estão referenciadas por digest no Compose e nos contêineres ativos:

- TimescaleDB/PostgreSQL;
- Redis;
- Evolution API e Manager;
- Caddy;
- n8n;
- Authentik server e worker;
- MariaDB e GLPI.

Após o saneamento final dos defaults, o Compose versionado e o instalado possuem o mesmo SHA-256: `5fbb56babe2ba2e60741f18e4ebf7b599cb2cd518099850e5e8c3010b8105634`.

A aplicação foi feita de forma transacional por [`../../infra/scripts/aiops-apply-pinned-images.sh`](../../infra/scripts/aiops-apply-pinned-images.sh), após backup recuperável. O procedimento preservou o Compose anterior em diretório `root-only` e tinha rollback automático.

## Verificação pós-mudança

- 14 contêineres em execução;
- zero contêineres `unhealthy`;
- zero units systemd falhas;
- GLPI interno HTTP 200;
- Hub HTTP 200;
- Authentik HTTP 302 para o fluxo de autenticação;
- backup pós-mudança `20260821T135439-0300` com 18 checksums válidos;
- restauração isolada desse backup concluída com `isolated_restore=PASS`.

Os serviços construídos localmente (`api`, `frontend` e workers) não usam imagem pública e precisam de proveniência de build/commit no CI/CD; digest de dependência externa não substitui essa rastreabilidade.
