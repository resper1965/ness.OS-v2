# Wazuh R3a single-node: dimensionamento para aprovação de compra (06/11/2026)

**Estado:** proposta, nada contratado. Só documento: sem Terraform, sem Ansible, sem toque em conta de provedor.
Complementa o [BOM de out/2026](../procurement/wazuh-bom-2026-10.md), que já recomendava começar por R3a (all-in-one: manager + indexer + dashboard).

## 1. O que foi medido na `homol` (origem atual, leitura como `ness_ro`, 06/11/2026)

| Medida | Valor | Como |
|---|---|---|
| Máquina | 8 vCPU, 32 GB RAM, disco 387 GB (155 GB usados, 40%), Ubuntu 25.04 | `nproc`, `free`, `df`, `os-release` |
| Carga | load médio 3,2 em 8 vCPU (~40%); uptime 20 d; 10,6 GB de RAM em uso (Java do indexer 8,3 GB), 21 GB de cache | `uptime`, `free`, `ps` |
| Serviços | manager, indexer, dashboard e filebeat ativos (systemd, instalação direta, sem Docker) | `systemctl is-active` |
| Agentes cadastrados | **898** linhas em `client.keys` (886 em 29/10), nenhuma desativada | só contagem de linhas; o conteúdo não foi lido |
| Agentes que geraram alerta | **611** distintos em 04/11 (dia completo) | `agent.id` do `alerts.json` rotacionado, só contagem |
| Alertas/dia (após os cortes de ruído de 29/10) | 03/11: 819.726 · 04/11: 903.631 · 05/11: 954.925 → **média ≈ 893 mil/dia** (≈ 10,3 alertas/s) | linhas dos `.json.gz` diários |
| Antes dos cortes | 6,2 M/dia (BOM, 29/10): queda de ~85% | BOM |
| Tamanho do alerta em JSON bruto | ≈ 2,6 KB (2,2–2,4 GB/dia sem compactar; 0,18–0,19 GB/dia o `.json.gz` + 0,22 GB o `.log.gz`) | tamanho de arquivo ÷ linhas |
| Níveis em 04/11 | ≥ 12: 414 (0,05%) · 7–11: 30.898 · ≤ 6: 872.319 | `rule.level`, só contagem |

**Não medido** (precisa de credencial do manager/indexer, que `ness_ro` não tem; nada foi contornado):
agentes *ativos* hoje (último valor: 391 em 29/10), tamanho real do índice (`/var/lib/wazuh-indexer` sem permissão), retenção configurada no indexer, EPS de entrada, steal de CPU atual, OT (sem dado de OT na `homol`).

## 2. Premissas (explícitas)

- **Agentes de projeto: 624** (o maior número já visto: foto de 21/08, e perto dos 611 que alertaram em 04/11). Cobre os ~400 ativos de 29/10 com margem de ~55%; acima de ~1.000 vale o gatilho de R3b do BOM.
- **Alertas/dia de projeto: 0,9 M** (medido pós-corte, já com 611 agentes reportando) **+30% de crescimento = 1,2 M/dia**. Não vale para volume de OT (desconhecido).
- **Bytes por alerta indexado: 1,1 KB** (teto medido em 29/10: 67 GB ÷ 60,6 M alertas; índice real *não medido* hoje). Dá ≈ 1,0 GB/dia medido e 1,3 GB/dia com a margem.
- Reserva de 30% (shards, heap, snapshots quentes; mesma do BOM) + 30 GB de SO/software + arquivos locais do manager (0,41 GB/dia compactados, **30 dias** assumidos).
- Hardware: Wazuh recomenda indexer 16 GB/8 vCPU e server 4 GB/8 vCPU; o quickstart all-in-one só cobre até 100 agentes (8 vCPU/8 GiB/200 GB em 90 d). Acima disso o all-in-one é por medição, e a `homol` já roda 611 agentes em 8 vCPU/32 GB.

## 3. Opções

Fórmula do disco: `GB/dia × dias de retenção × 1,3 (reserva) + 0,41 × 30 (arquivos locais) + 30 (SO)`.

| | **A — mínimo** | **B — recomendado** |
|---|---|---|
| Retenção pesquisável (opção, o Ricardo decide) | 30 dias | 90 dias |
| vCPU / RAM | 8 / 24 GB (= soma das recomendações; sem folga) | 12 / 48 GB (folga para consulta de 90 d e lote OT) |
| GB/dia de índice | 1,0 (medido) | 1,3 (+30%) |
| Disco calculado | 1,0×30×1,3 + 12 + 30 ≈ **81 GB** | 1,3×90×1,3 + 12 + 30 ≈ **194 GB** |
| Disco a comprar | 300 GB | 400 GB |
| Folga de disco | ~3,7× | ~2,1× |
| Produto Contabo (lista) | Cloud VPS 8: 8 vCPU / 24 GB / 300 GB SSD | Cloud VPS 12: 12 vCPU / 48 GB / 400 GB SSD |
| Preço de tabela, 24 meses | €14,00/mês com IVA (€11,20 sem) | €25,00/mês com IVA (€20,00 sem) |

- Alternativa de retenção 30 d na B: o mesmo servidor, disco calculado ≈ 81 GB. A diferença entre 30 e 90 dias é só disco/consulta, não preço.
- **Sensibilidade (risco principal):** se o volume voltar ao de out/2026 (6,2 M/dia ≈ 6,8 GB/dia), 90 d = 6,8×90×1,3 ≈ 800 GB (BOM: ~0,8 TB), acima dos 400 GB. Pela tabela oficial do Wazuh (2,345 GB/agente/90 d no mix 70/25/5) seriam 624 × 2,345 = 1,46 TB (+30% = 1,9 TB); a medição pós-corte (≈ 152 GB em 90 d com reserva) fica mais de 10× abaixo da tabela. Mitigação sem trocar de servidor: extensão de armazenamento do próprio VPS (a página lista a opção, mas **não o preço**: confirmar no painel) ou, se estourar, gatilho de R3b.
- Identificadores: os `product_id` em `infra/terraform/environments/prod.tfvars` (V102, V98, V156) são de instâncias existentes; a correspondência V-código ↔ nome comercial atual **não foi verificada** (não consultei a API). O nome dos planos mudou desde o BOM (o antigo "VPS 40" 12 vCPU/48 GB é hoje "Cloud VPS 12", com 400 GB em vez de 500 GB).

## 4. Preço (preço de tabela, não verificado na conta)

Fonte: <https://contabo.com/en/vps/> (Core VPS), consultada em 06/11/2026; preço efetivo mensal para contrato de 24 meses, o de 1 mês é maior e não aparece. Moeda e IVA mudam por país/conta; backup automático e extensão de disco não estão incluídos. A página servida pode estar em cache de data anterior.
Referência de disco grande, se a retenção for 90 d com volume de out: Storage VPS 40 (8 vCPU/30 GB/1,2 TB SSD) €25,00 com IVA (€20,00 sem), <https://contabo.com/en/storage-vps/>: ganha disco, perde vCPU/RAM.

## 5. Requisitos Wazuh usados

- Indexer e disco por tipo de endpoint: <https://documentation.wazuh.com/current/installation-guide/wazuh-indexer/index.html>
- All-in-one até 100 agentes: <https://documentation.wazuh.com/current/quickstart.html>

## 6. Ainda sem decisão (nada preenchido por mim)

- **Retenção** pesquisável (30, 90 ou outra) e retenção do bruto arquivado (política de atendimento, regra 3).
- **OT:** duração da janela retrospectiva (teto de 24 h na política), banda, capacidade e retenção; o dado de OT não existe na `homol`, então o pico de lote não está dimensionado.
- **Capacidade:** número de agentes de projeto (624 é premissa minha), limpeza dos desconectados e disco extra se o volume subir.
- **Modalidade/operador** por vínculo de grupo (9 vínculos → clientes `rzk`, `target`, `ness`) ainda nulos; define quem envia dados e de onde.

## Decisão

**Autoriza contratar a VPS do Wazuh na opção B? (sim/não)**
