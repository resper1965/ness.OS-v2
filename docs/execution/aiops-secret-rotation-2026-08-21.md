# Rotação dos defaults AIOps — 21/08/2026

## Achado

O Compose ativo ainda fornecia defaults conhecidos para a senha PostgreSQL compartilhada e para `AUTHENTIK_SECRET_KEY`. A inspeção sem exposição de valores confirmou que API, Evolution e Authentik usavam o mesmo usuário/senha PostgreSQL e que os dois defaults estavam efetivamente ativos.

## Correção

- senha do role PostgreSQL `nessops` substituída por valor aleatório;
- `NINF_DATABASE_URL`, Evolution, PostgreSQL e Authentik sincronizados com o novo valor;
- `AUTHENTIK_SECRET_KEY` substituído por valor aleatório;
- defaults removidos do Compose e substituídos por variáveis obrigatórias;
- configurações e segredos anteriores preservados somente em rollback `root-only`;
- API, workers, PostgreSQL, Evolution e Authentik recriados de forma transacional;
- rollback automático mantido até a conclusão de todos os testes.

A troca do `AUTHENTIK_SECRET_KEY` invalida sessões Authentik existentes. Esse efeito é esperado e documentado oficialmente para versões atuais; a instalação usa 2026.5.6.

## Evidências

- senha consistente entre todos os consumidores: `yes`;
- default conhecido do banco ainda em uso: `no`;
- default conhecido do Authentik ainda em uso: `no`;
- 14 contêineres ativos, zero `unhealthy` e zero units falhas;
- conexão SQL real pela API: passou;
- Hub HTTP 200, Authentik HTTP 302 e GLPI interno HTTP 200;
- Compose local/remoto, após retirar também o fallback da URI Evolution: SHA-256 `5fbb56babe2ba2e60741f18e4ebf7b599cb2cd518099850e5e8c3010b8105634`;
- backup pós-rotação `20260821T142635-0300`: checksums válidos e `isolated_restore=PASS`.

Os diretórios de rollback que continham as credenciais antigas foram removidos definitivamente após o restore passar. A recuperação permanece disponível no backup pós-rotação protegido como `root-only`.

Scripts reutilizáveis:

- [`../../infra/scripts/aiops-secret-consumer-report.sh`](../../infra/scripts/aiops-secret-consumer-report.sh), relatório sem segredos;
- [`../../infra/scripts/aiops-rotate-shared-secrets.sh`](../../infra/scripts/aiops-rotate-shared-secrets.sh), rotação transacional.

Fonte oficial: [authentik — Configuration](https://docs.goauthentik.io/install-config/configuration/).
