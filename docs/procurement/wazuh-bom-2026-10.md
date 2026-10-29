# BOM Wazuh — out/2026

> Task 9.1 do [plano de execução](../superpowers/plans/2026-10-26-ness-os-execution-plan.md).
> Decisão de compra: D6 (Ricardo). Recomendação: **começar por R3a** e migrar para R3b por métrica/HA, **sem reinstalar** (mesma role Ansible, mais nós — Task 9.2).

## Carga observada (origem Hostinger, transitória)

Medido em 29/10/2026 por leitura (`ness_ro` no SSH e `ness_ro_api` com papel `readonly` na API do manager), manager no ar há 9 dias e 18 h. Antes, a fotografia de 21/08 (`docs/vps-capacity-and-sequencing-plan.md`) dizia 624 endpoints e 4 vCPU.

| Medida | Valor |
|---|---|
| Máquina | 8 vCPU, 32 GB, disco 387 GB (197 GB usados), Ubuntu 25.04, Wazuh 4.14.1 (manager, indexer, dashboard) |
| Agentes | 886 cadastrados: **391 ativos**, 485 desconectados (146 há mais de 30 dias), 10 nunca conectaram. Dos ativos, 389 são Windows e o resto Linux; 48 estão com versão desatualizada. Grupos: RZK-AGRO 644, RZK-HOLDING 147, TARGET 82, RZK-SOL 2 |
| Eventos recebidos | 153,9 M em 9,8 dias ≈ **182 EPS** médio (o BOM de 26/10 estimava 95). Por hora: ~0,23 M à noite e ~1,0 M em horário comercial, pico ≈ **290 EPS**. Por ativo: ≈ 0,46 EPS, acima dos 0,1 da tabela de workstation |
| Origem dos eventos | `winevt` 99,4 M (**65%**), `syscollector` 20,5 M (13%), `syscheck` 2,5 M, `sca` 1,3 M |
| Eventos descartados | 1,77 M no analysisd (1,15%) e 0,71 M no remoted |
| Alertas gravados | 60,6 M ≈ **6,2 M/dia** (≈ 72/s) |
| Alertas em disco | `alerts.json` de hoje com 5 GB e `.log` com 7 GB sem compactar (13:45 UTC); compactado 0,7–0,8 GB/dia o JSON e ~1 GB/dia o `.log` |
| Indexer | 67 GB; ≤ 1,1 KB por alerta, tomando os 60,6 M como base (limite superior: o índice pode ter mais de 9 dias) |
| CPU/memória | `analysisd` 41% de um núcleo; Java do indexer com 7,9 GB; ociosa 18–40% |
| Steal de CPU | **31–60%** no `vmstat`: o hospedeiro da Hostinger está disputando CPU |

Leitura: ≈ 16.000 alertas por agente ativo por dia é volume de regras ruidosas, e dois terços vêm de eventos do Windows. Ajustar regras antes de dimensionar disco pode cortar o custo bem mais que comprar espaço.

## Premissas de dimensionamento

- Retenção 90 dias (alertas pesquisáveis); incidentes qualificados seguem no AIOps/GLPI por 12 meses.
- Bytes/evento e APS por endpoint conforme tabela oficial do Wazuh indexer 4.14 (ver fontes): servers 0,25 APS → 3,7 GB/90d por agente; workstations 0,1 APS → 1,5 GB/90d; network devices 0,5 APS → 7,4 GB/90d.
- Mix adotado para a conta (sem perfil real por endpoint, *A CONFIRMAR* no piloto Task 9.3): 70% workstations, 25% servers, 5% network devices.
- Disco indexer = soma(per-endpoint × nº), +30% reservas (shards, OS, heap, snapshots quentes), arredondado.
- EPS: a tabela do Wazuh (APS × endpoints, ≈ 0,16 APS no mix) subestima a origem, que mede ≈ 0,46 EPS por ativo; para extrapolar use o medido.
- **Medido** = seção de carga observada. **Teto** = 1,1 KB/alerta. **Estimativa** = tabela do Wazuh e mix 70/25/5. Pela tabela: 2,345 GB/endpoint/90 d → 624 = 1,46 TB (+30% = **1,90 TB**); ~400 ativos = 0,94 TB (+30% = ~1,2 TB).

## Topologia R3a — single-node (Contabo Cloud VPS 40)

| Item | Valor |
|---|---|
| Classe | Cloud VPS 40 — 12 vCPU, 48 GB, 500 GB SSD |
| Papéis | Indexer + Server + Dashboard (all-in-one) |
| Endpoints suportados | ~400 ativos (**medido** na origem, que roda all-in-one com 8 vCPU/32 GB e 182 EPS). O quickstart oficial só recomenda all-in-one até ~100 endpoints; acima disso é validar no piloto (Task 9.3) e o gatilho de R3b cobre o risco |
| EPS | **~182 EPS medidos** hoje na Hostinger (a estimativa de 95 não vale) |
| Disco 90 d | Medido (teto): 6,2 M alertas/dia × 90 × 1,1 KB ≈ 615 GB + 30% ≈ **0,8 TB** para os ~400 ativos. Pela tabela do Wazuh: ~1,2 TB (~400 ativos) ou 1,90 TB (624). Não inclui `alerts.json`/`.log` em disco (~1,7 GB/dia compactado ≈ +160 GB se guardados 90 d) |
| Disco da VPS | 500 GB — **insuficiente** p/ 90 d dos ~400 ativos (0,8–1,2 TB); usar add-on de disco (+1 TB, total ~1,5 TB) ou Storage VPS 40 |
| HA | Nenhum (SPOF); rollback = origem Hostinger preservada |
| Custo/mês | VPS 40 €25 + add-on disco *A CONFIRMAR*; estimado €35–45 |
| Rollback | Agentes voltam para o Hostinger; janela de 7–14 d preservada |
| Operação | Baixa: 1 nó, 1 runbook, snapshot diário |

**Disco é o gargalo de R3a.** Resolução mais barata: add-on de armazenamento na própria VPS 40 (preço e tamanho máx. *A CONFIRMAR* no painel Contabo); alternativa Storage VPS 40 (8 vCPU/30 GB/1,2 TB SSD, €20) — perde vCPU/RAM, ganha disco, mas 1,2 TB cobre os ~0,8 TB medidos e os ~1,2 TB da tabela (justo), mas não os 1,90 TB de 624 endpoints. Confirmar no piloto (Task 9.3) o APS real por perfil antes de fechar disco.

## Topologia R3b — onda 1 (cluster, rede privada R4)

| Nó | Classe | vCPU/RAM | Disco | Papel | €/mês |
|---|---|---|---|---|---|
| 3× | Cloud VPS 30 | 8/24 GB | 400 GB | Indexer (quórum) | 42 |
| 1× | Cloud VPS 20 | 6/12 GB | 200 GB | Server master | 7 |
| 2× | Cloud VPS 30 | 8/24 GB | 400 GB | Server worker | 28 |
| 1× | Cloud VPS 10 | 4/8 GB | 100 GB | Dashboard + balanceador | 4,50 |
| R4 | Rede privada | — | — | Portas 1516/9200/9300/55000 internas | *A CONFIRMAR* |
| **Total** | | | | | **€81,50 + R4** |

- **Endpoints:** até ~1.000 (limite da onda 1 do plano de capacidade).
- **EPS estimado (1.000):** ~460 EPS (extrapolado dos 0,46 EPS/ativo medidos; a tabela daria ~160, abaixo do observado).
- **Disco 90 d (1.000):** 1.000 × 2,345 ≈ 2.345 GB + 30% ≈ **3,05 TB**; em 3 indexers sem réplica ≈ 1,0 TB/nó, com réplica 1 (HA real dos dados) ≈ 2,0 TB/nó. Os 400 GB/nó **não bastam**: exige add-on em cada indexer. Para ~400 ativos (0,8–1,2 TB) são 0,3–0,4 TB/nó sem réplica e 0,5–0,8 TB com réplica. *A CONFIRMAR* no piloto.
- **HA:** quórum de 3 indexers tolera 1 falha; cluster de managers (1 master + 2 workers) mantém ingest com 1 nó fora; dashboard é SPOF aceitável na onda 1.
- **Rollback:** Remover nó novo do cluster (rolling); estado íntegro nos demais; sem reinstalação.
- **Operação:** Alta: 7 nós, certificados TLS entre nós, IPSec/WireGuard da rede privada, monitoração por nó. Custo de humano significativo.

## Comparação e recomendação

| Critério | R3a single-node | R3b onda 1 |
|---|---|---|
| Custo/mês | €25–45 | €81,50 + R4 |
| HA | Não | Sim (indexer + server) |
| Disco 90 d (~400 ativos) | **Cobrir com add-on** | Add-on em cada indexer (400 GB/nó não basta com réplica) |
| Esforço op. | Baixo | Alto (7 nós) |
| Path para 5.000 | Migrar tudo | Adicionar nós (onda 2+) |
| Rollback | Origem Hostinger | Rolling do nó |

**Recomendação:** iniciar por **R3a** (single-node Cloud VPS 40 + add-on de disco confirmado). Migrar para **R3b** quando **qualquer** gatilho abaixo disparar (medido em R3a por ≥14 dias):

1. EPS sustentado > 70% da capacidade do nó por 14 d, **ou** pico de CPU > 70% por 14 d.
2. Disco projetado a < 20% livre antes de 90 d (retenção ameaçada).
3. Exigência contratual/SLA de HA (D7 / cliente), **ou** endpoints > 900 com projeção de ultrapassar 1.000 em 90 d.
4. Fila/backpressure persistente no server (events_dropped > 0 em `wazuh-analysisd.state`).

A migração R3a → R3b não reinstala: a role Wazuh (Task 9.2) adiciona nós ao cluster existente, reindexa e descomissiona R3a; mesmos agentes, mesmos certificados de CA, sem toque nos endpoints.

## A CONFIRMAR (pré-compra)

- **Dimensionar para ~400 ativos, não 886 nem 624**: limpar os 485 desconectados e os 10 que nunca conectaram antes da migração (decisão do Ricardo; o Wazuh só removeria o cadastro, não os dados).
- **Retenção e tamanho reais do índice**: `_cat/indices` exige usuário do indexer (a API do manager não cobre); sem isso o 1,1 KB/alerta é só limite superior.
- **Steal de 31–60%** na Hostinger: confirmar se persiste ou se é pico; pesa na escolha de classe de CPU.

- Preço e tamanho máx. do **add-on de disco** na Contabo (R3a e por-indexer em R3b).
- Preço da **rede privada R4** (Contabo Private Networking).
- **APS real por perfil** de endpoint (workstation/server/network) — medir no piloto Task 9.3 antes de fechar disco de produção.
- `product_id` atuais no painel/API Contabo na data da compra (não fixados aqui, regra do plano).

## Fontes (consulta em 26/10/2026)

- Preços e specs Contabo Cloud VPS 10/20/30/40: <https://contabo.com/en-us/pricing> e <https://contabo.com/en-us/vps> (preços para termo de 24 meses; confirmar no painel na compra).
- Requisitos de hardware Wazuh 4.14 (indexer: min 4 GB/2 vCPU, recom. 16 GB/8 vCPU; server: min 2/2, recom. 4/8) e tabela de disco por agente/90 d: <https://documentation.wazuh.com/current/installation-guide/wazuh-indexer/index.html> e <https://documentation.wazuh.com/current/installation-guide/wazuh-server/index.html>.
- Plano de capacidade e BOM anterior: [`docs/vps-capacity-and-sequencing-plan.md`](../vps-capacity-and-sequencing-plan.md) (onda 1: 3× VPS 30, 1× VPS 20, 2× VPS 30, 1× VPS 10).
- Carga observada: idem, fotografia de 21/08/2026 (624 endpoints, 4 vCPU, 21% médio / 41% pico).