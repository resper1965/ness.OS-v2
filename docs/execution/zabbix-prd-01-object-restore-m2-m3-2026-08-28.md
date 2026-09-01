# Zabbix PRD-01 — gates Z-M2 e Z-M3 aprovados (2026-08-28)

## Rollback preservado

Antes da importação foi revalidado o backup offline
`20260828T174151-0300`: marcador `COMPLETED`, seis entradas SHA-256 e
`gzip -t` aprovados. O conjunto permanece intacto em
`/var/backups/zabbix/nightly/`.

## Z-M2 — importação isolada

| Controle | Evidência |
| --- | --- |
| Snapshot de entrada | Restic `96f2a24e` |
| SHA-256 do dump | `038fb55db4ec3677d5117f0829a7cec4370e3ce8dcfc15e8762939d39c1079ff` |
| Tempo de importação | 5.026 segundos |
| Tabelas | 203 |
| Hosts | 677 |
| Itens | 61.777 |
| Triggers | 25.229 |
| Versão obrigatória | `7000000` |
| Ações ativas | 5 → 0 |
| Mídias ativas | 1 → 0 |
| Conectores ativos | 0 → 0 |
| Resultado | `restore=PASS` |

## Z-M3 — isolamento e baseline

A verificação independente confirmou MariaDB ativo e localhost-only, NTP
sincronizado, Apache e agente inativos, `zabbix-server` inativo/mascarado, sem
listener `10051` e com ações, mídias e conectores desabilitados.

A baseline offline da Onda 0 registrou:

- 314 hosts monitorados e 362 templates;
- 43.307 itens habilitados em hosts monitorados;
- 2.609 itens não suportados e 1.143 triggers em estado desconhecido;
- 20 hosts monitorados sem template e 277 sem tag;
- um mapa com um elemento;
- banco com 53.490.728.960 bytes.

Os relatórios detalhados, root-only, permanecem em
`/var/lib/ness-os/restore-evidence/` no `zbx-prd-01`.

## Próximo gate

Z-M4: revalidar frontend HTTPS/SAML e homologar o piloto Cavan — Matriz sem
ativar coleta, ações, mídias, conectores, proxies ou agentes. O corte Z-M5
continua proibido sem aceite explícito.

### Preflight Z-M4

- a credencial do frontend PHP foi sincronizada com o usuário isolado
  `zabbix_staging`, com cópia root-only do arquivo anterior, sintaxe PHP e login
  MariaDB aprovados;
- Apache, certificado e vhosts passaram na validação local; UFW continua
  permitindo HTTPS somente a partir das redes Cloudflare;
- o endpoint UAT respondeu como Zabbix `7.0.27`;
- o token atualmente consumido pelo Hub foi rejeitado pelo snapshot restaurado;
- o snapshot contém o diretório SAML de produção (`zabbix.ness.com.br`), com
  JIT e SCIM ativos, e reintroduziu Super Admins herdados.

Por isso o Apache foi desligado novamente. Na abertura da janela de 29/08, uma
credencial Super Admin válida do próprio Zabbix foi entregue em arquivo
root-only e validada pela API. O frontend foi republicado sem iniciar o
`zabbix-server`.

### Identidade e RBAC Z-M4 — 29/08

- o diretório SAML restaurado foi alterado pela API suportada para o provedor
  Authentik `zabbix-uat`; IdP, SSO e SP agora apontam para o UAT;
- o certificado IdP instalado possui o mesmo SHA-256 publicado nos metadados;
- JIT, SCIM e provisionamento permanecem desabilitados; autenticação local de
  contingência continua tecnicamente disponível;
- o login SAML nominal de `resper` foi confirmado até o dashboard;
- nove Super Admins herdados foram preservados, mas rebaixados para `Admin
  role`; permanecem temporariamente como Super Admin `resper`, `iaraujo`,
  `rsalerno`, o `Admin` local e a integração `zbxgrafana`;
- a senha temporária de recuperação foi rotacionada, comprovadamente rejeitada
  e seu arquivo plaintext removido; o token de automação permanece root-only
  (`0600`) e válido;
- snapshots antes/depois e o vínculo legado de provisionamento removido de
  `akadmin` estão em `/var/lib/ness-os/restore-evidence/`, `root:root 0600`.

O bloqueio de credencial/SAML foi encerrado. Z-M4 ainda não está aprovado por
inteiro: faltam os testes nominais de `iaraujo` e `rsalerno`, os testes negativos
de identidade e o piloto Cavan — Matriz. Z-M5 e qualquer ativação de coleta
continuam proibidos sem aceite explícito.
