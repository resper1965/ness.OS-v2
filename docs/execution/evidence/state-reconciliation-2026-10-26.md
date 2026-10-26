# Reconciliação de estado — 2026-10-26

Task 0.1 do [plano de execução](../../superpowers/plans/2026-10-26-ness-os-execution-plan.md).
Leitura do remoto, da API do GitHub e da AIOps (read-only). Não aprova gate.

## Remoto `resper1965/ness.OS-v2`

| Ref | SHA | Estado |
|---|---|---|
| `main` | `2e5b45a` (13/10) | contém o PR #65 como `5f8da9c` |
| PR #64 `feat/incidents-rbac-local` | `2e1772c` | draft → `main`; 402 commits à frente, 1 atrás (`c0e94e8`) |
| PR #81 `no-actions-release` | `5051d4c` | draft → `main`; 35 à frente, 0 atrás |
| PR #84 `chore/ci-local` | `4a49c05` | aberto, pronto, → `main`; `scripts/ci-local.sh` (Ricardo, 23/10) |

Actions: `enabled: false`. Os SHAs `11a18cd`/`49c802f` citados no indicador
para o #81 não são o head publicado; o head é `5051d4c`.

PR #84 relata no `main`: passam `flake8`, `pytest` (24 testes), frontend
(`npm ci`, `oxlint`, `vite build`); falham `black --check` (26 arquivos),
`ruff check`, `ruff format --check` e `mypy`.

## Produção AIOps (`vmi3409271`)

- Compose em `/opt/n-infraops/releases/144317fd5262ecf242b118774573a62df8e88d78/app`.
- API e workers: `ghcr.io/resper1965/ninf-api@sha256:cd3224cf…caadf` (criada 12/10 09:04 BRT).
- Frontend: `ghcr.io/resper1965/ninf-frontend@sha256:604e9b9e…f425`.
- Igual a [hub-immutable-release-2026-10-12](hub-immutable-release-2026-10-12.md). Nenhuma promoção desde 12/10.
- `/opt/n-infraops` não é checkout Git; contém `fix_saml.py` e `run_provision_saml.py` soltos.
- Imagens sem tag fixa: `psono-combo`, `evolution-api`, `evolution-manager`, `n8n`, `timescaledb` e `elestio/glpi` em `:latest`.

## Correções aplicadas

- Links `github.com/resper1965/n-infraops` → `ness.OS-v2` em 9 arquivos.
- PR #65 registrado como integrado em `gates/phase-0-recovery-release.md` e `gate-0-status.md`.

## Correções que dependem do Ricardo

- `148.230.77.242`: o registro de 02/09 diz que a KVM8 foi devolvida e proíbe
  contato; hoje é o IP da `stack` (`srv1013444.hstgr.cloud`), onde os agentes
  rodam. Confirmar titularidade para corrigir o registro.
- Caminhos `/home/resper/ness.OS*` e o ledger são de outra máquina; não estão nesta.

## Consequência para D1

O PR #84 já roda os checks localmente sem Actions. Falta só confiança no
resultado (quem roda, em qual SHA, e como a proteção da `main` aceita). As
falhas de `black`/`ruff`/`mypy` no `main` são o primeiro trabalho de qualquer
opção de CI.
