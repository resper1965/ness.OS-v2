# Plano de rotação de segredos — 22/08/2026

## Regra de segurança

As credenciais expandidas durante o diagnóstico de 22/08 são consideradas expostas. Nenhum rollback pode reativar um segredo antigo: rollback restaura código/configuração/dados usando outro segredo novo ou mantém a integração desabilitada. Valores nunca entram neste documento, Git, logs ou comandos de evidência.

Antes de cada fase: backup/checksum, inventário sanitizado de consumidores, acesso break-glass testado, janela/owner definidos e rollback preparado. Depois: health funcional, teste negativo do segredo anterior, backup novo e restore isolado proporcional ao risco.

## Ordem por dependência

| Ordem | Classe | Produtor e consumidores principais | Aceite mínimo |
|---:|---|---|---|
| 0 | Contabo | provedor → backend Contabo | revogar administração exposta; emitir conta/API read-only; GET apenas sob `platform_admin`+MFA; segredo antigo rejeitado |
| 1A | PostgreSQL AIOps | PostgreSQL → API, workers, Evolution e Authentik | SQL real, todos os healthchecks, Authentik/Hub e backup+restore aprovados |
| 1B | MariaDB GLPI | MariaDB → GLPI e configuração persistente | credenciais root/aplicação separadas, GLPI HTTP/banco/cron e restore aprovados |
| 2 | Authentik interno | Authentik → server/worker | reinício conjunto, sessões antigas invalidadas, login break-glass e MFA comprovados |
| 3A | OIDC | Authentik → backend Hub | callback, issuer/JWKS, claims/grupos, 401/403 e revogação do anterior |
| 3B | JWT | backend → todas as sessões locais | reinício atômico das réplicas, logout global esperado, token antigo rejeitado |
| 4 | Tokens GLPI | GLPI → backend/n8n | leitura e criação controlada via API, histórico pelo usuário técnico, anteriores revogados |
| 5 | n8n/webhooks | n8n → backend, GLPI e Zabbix | payload sintético, assinatura/autorização, idempotência, fila/retry e URLs antigas rejeitadas |
| 6 | API Zabbix | Zabbix → backend/n8n | token de serviço read-only, consultas e alerta→incidente aprovados, anterior revogado |
| 7 | Gemini | provedor → integração/ML/workers | chamada mínima sem dado sensível, limites/erros e sanitização aprovados |
| 8 | VAPID | backend → frontend/browser | par coerente, subscriptions refeitas e push ponta a ponta aprovado |

## Ferramentas já existentes

- `infra/scripts/aiops-secret-consumer-report.sh`: inventário sem valores;
- `infra/scripts/aiops-rotate-shared-secrets.sh`: PostgreSQL/consumidores;
- `infra/scripts/glpi-pin-and-rotate.sh` e `glpi-sync-persistent-db-password.sh`: GLPI/MariaDB;
- `infra/scripts/zabbix-revoke-intranet-token.sh`: somente após confirmar o identificador exato.

## Bloqueios

- Psono Community ainda não está disponível para segredos humanos;
- SOPS/age e secret scanning open source ainda não estão implantados para automação/repositório;
- a conta Contabo read-only e o grupo Authentik `platform_admin` com MFA ainda não foram homologados;
- os tokens GLPI de implantação e a senha de `svc_ness_os` estão temporariamente em `secrets/runtime/glpi-integration.env` (ignorado pelo Git, `0600`); migrar consumidores ao cofre/SOPS-age, gerar novos valores e provar rejeição dos atuais antes do go-live;
- a primeira geração desses três valores foi invalidada imediatamente após expansão indevida em retorno local; somente a segunda geração permanece no arquivo protegido, e ela também deve ser substituída no gate final;
- rotação em massa é proibida; executar uma classe por vez e registrar evidência sem valores.
