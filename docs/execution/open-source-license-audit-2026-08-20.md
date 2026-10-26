# Auditoria de licenças e reprodutibilidade — AIOps

> Data da coleta: 20/08/2026
> Escopo: componentes em execução na VPS AIOps e imagens declaradas nos Compose locais
> Política: o núcleo autohospedado deve usar somente software sob licença aprovada pela OSI, com fonte auditável e versão reproduzível.

## Resultado executivo

A stack atual **ainda não atende integralmente** à política open source. O serviço permanece operacional, mas quatro componentes exigem tratamento: Redis 7.4, n8n, TimescaleDB Community e Evolution API. Também existem imagens com tag flutuante (`latest`, `latest-pg16` ou apenas major), o que impede reproduzir com segurança um deploy ou rollback.

Nenhuma substituição será feita diretamente em produção. Cada migração exige backup, exportação lógica, homologação, teste de integração, rollback e janela registrada.

## Inventário e decisão

| Componente observado | Situação de licença | Decisão alvo | Prioridade |
|---|---|---|---|
| Zabbix 7.0 LTS | GPLv2; compatível | manter, fixar versão e registrar pacote/repositório | manter |
| GLPI | GPLv3; compatível | manter; fixar versão e digest da imagem | alta |
| Caddy | Apache-2.0; compatível | manter; fixar versão e digest | alta |
| MariaDB 10.11 | GPLv2; compatível | manter; fixar patch e digest | alta |
| PostgreSQL 16 | PostgreSQL License; compatível | manter | manter |
| pgvector | PostgreSQL License; compatível | manter e atualizar de forma ensaiada | média |
| Passbolt | AGPLv3; compatível | implantar em terceira VPS; assinatura de suporte/recursos não altera a exigência de código AGPL | projeto |
| Psono Community | Apache 2.0 no servidor comunitário; compatível | candidato preferencial ao PoC do cofre; não usar recursos Enterprise no desenho | projeto |
| Authentik core | MIT; compatível | manter core; inventariar e desabilitar qualquer recurso enterprise não deliberadamente contratado | alta |
| Redis 7.4.9 | RSALv2 ou SSPLv1; não atende à política OSI | migrar para Valkey sob BSD-3-Clause | alta |
| TimescaleDB 2.28.2 Community | mistura Apache-2.0 e Timescale License | remover extensão/imagem Community; hoje há **zero hypertables**, portanto usar PostgreSQL 16 + pgvector | alta |
| n8n 2.28.4 | Sustainable Use License/fair-code; o próprio projeto declara não ser open source OSI | migrar os quatro workflows para Node-RED Apache-2.0; Windmill somente se compilado da fonte AGPL sem código enterprise | alta |
| Evolution API/Manager | Apache-2.0 com condições adicionais; releases novas exigem ativação externa | congelar a versão atual como fallback, não atualizar por `latest`; substituir por adaptador/conector OSI homologado ou integração oficial isolada | crítica antes de upgrade |
| Hub/API/PWA próprios | sem arquivo de licença/SBOM no repositório | definir titularidade e licença interna/open source, gerar SBOM e política de dependências | alta |
| SuperOps, Datto, Atera e canal WhatsApp | serviços externos proprietários | tratar apenas por adaptadores substituíveis na borda; não podem compor o núcleo nem ser fonte única dos dados | arquitetura |

## Evidências operacionais

- Redis em execução: 7.4.9.
- PostgreSQL: 16.14; TimescaleDB: 2.28.2; pgvector: 0.8.1.
- Banco atual não possui hypertables TimescaleDB.
- n8n utiliza SQLite e contém quatro workflows, dos quais três ativos, uma credencial e nenhum histórico de execução retido no momento da coleta.
- As automações usam poucos tipos de nós: HTTP, webhook, código, e-mail, resposta a webhook e cron. A migração para Node-RED é de baixo volume, mas deve preservar idempotência, autenticação, retries, logs e trilha de mudança.
- Compose contém imagens flutuantes para GLPI, Evolution API/Manager, TimescaleDB e n8n; `redis:7-alpine` e `caddy:2-alpine` também flutuam dentro do major.
- A inspeção dos nomes das variáveis de ambiente do Authentik não encontrou token/licença enterprise explícito. A presença do módulo `authentik.enterprise` na imagem e no middleware não prova uso licenciado; permanece necessário inventariar os recursos configurados pela API/UI antes de concluir conformidade.
- Os digests exatos observados foram registrados em [`aiops-image-lock-2026-08-20.md`](aiops-image-lock-2026-08-20.md) e aplicados somente ao Compose local; nenhum contêiner foi recriado.

## Sequência de regularização

1. Exportar inventário de imagens em execução com tag, digest, versão, origem e licença; manter a evidência junto ao release.
2. Trocar tags flutuantes por versão exata e digest **do artefato atualmente validado**, sem atualizar conteúdo nessa mudança.
3. Criar staging restaurável a partir do backup AIOps.
4. Migrar Redis para Valkey, validar compatibilidade de clientes, TTL, filas Celery e cache da Evolution/Auth­entik; executar teste de carga e rollback.
5. Restaurar o PostgreSQL em imagem PostgreSQL 16 + pgvector sem TimescaleDB Community; validar extensões, schema, dumps e todas as aplicações consumidoras.
6. Reimplementar os quatro workflows do n8n em Node-RED conforme [`n8n-to-node-red-migration.md`](n8n-to-node-red-migration.md), com credenciais fora dos flows, projetos versionados, autenticação via Authentik/Caddy e logs enviados ao núcleo de auditoria.
7. Executar paralelismo controlado dos workflows sem efeitos duplicados; comparar entradas, saídas, retries e falhas. Desligar n8n somente após aceite.
8. Congelar Evolution no digest atual e bloquear atualização automática. Abrir prova de conceito de conector substituto; não promover release com ativação externa obrigatória.
9. Auditar recursos enterprise efetivamente habilitados no Authentik e remover o que não estiver coberto pela edição/política adotada.
10. Gerar SBOM CycloneDX/SPDX por release, executar scan de licença e vulnerabilidade no CI e bloquear licença desconhecida, não-OSI ou imagem sem digest.

## Critérios de saída

- Nenhum contêiner de produção usa tag flutuante.
- Todos os componentes do núcleo têm licença OSI identificada e evidência da fonte correspondente.
- Redis foi substituído por Valkey e TimescaleDB Community foi removido sem perda de dados.
- Os quatro workflows do n8n foram migrados, comparados e possuem rollback testado.
- Evolution não atualiza automaticamente e seu caminho de substituição tem owner, data e critérios de aceite.
- Hub possui SBOM, licença definida, inventário de dependências e verificação automática no CI.
- Integrações proprietárias são opcionais, substituíveis e não detêm o registro canônico.

## Referências primárias

- [Redis 7.4.9 — RSALv2/SSPLv1](https://github.com/redis/redis/blob/7.4.9/LICENSE.txt)
- [Valkey — BSD-3-Clause](https://github.com/valkey-io/valkey/blob/unstable/COPYING)
- [n8n — Sustainable Use License e declaração de que não é open source OSI](https://docs.n8n.io/privacy-and-security/sustainable-use-license/)
- [Node-RED — Apache-2.0](https://github.com/node-red/node-red)
- [TimescaleDB — licenças por diretório/artefato](https://github.com/timescale/timescaledb/blob/main/LICENSE)
- [Evolution API — condições adicionais](https://github.com/evolution-foundation/evolution-api/blob/main/LICENSE)
- [Authentik — repositório e licença](https://github.com/goauthentik/authentik)
- [GLPI — GPLv3](https://github.com/glpi-project/glpi)
- [Caddy — Apache-2.0](https://github.com/caddyserver/caddy)
- [Passbolt CE — AGPLv3](https://github.com/passbolt/passbolt_api)
