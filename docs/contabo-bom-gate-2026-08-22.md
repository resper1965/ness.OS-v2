# BOM de referência Contabo — Gate Financeiro ness.OS

**Data-base:** 22/08/2026
**Status:** estimativa para planejamento; não autoriza compra

## Premissas

- região UE, sem taxa adicional de localização;
- Zabbix e AIOps existentes ficam fora desta compra e devem aparecer separadamente no custo consolidado;
- disco adicional, impostos/VAT, IPv4/add-ons, RMM, IA e operação não estão incluídos;
- preços de VPS abaixo vieram do catálogo público oficial indexado, mas a página ao vivo retornou HTTP 403 ao coletor. Eles precisam ser confirmados no carrinho Contabo, com país/VAT e prazo mensal, antes de aprovação;
- teto aprovado para toda a operação: **EUR 2.000/mês**.

## Onda 1 — piloto, sem HA/SLA

| Papel | SKU | Qtd. | Referência unitária | Subtotal |
|---|---:|---:|---:|---:|
| Wazuh indexer | Cloud VPS 30 | 3 | EUR 14,00 | EUR 42,00 |
| Wazuh master | Cloud VPS 20 | 1 | EUR 7,00 | EUR 7,00 |
| Wazuh worker | Cloud VPS 30 | 2 | EUR 14,00 | EUR 28,00 |
| Wazuh edge | Cloud VPS 10 | 1 | EUR 4,50 | EUR 4,50 |
| Psono Community | Cloud VPS 10 | 1 | EUR 4,50 | EUR 4,50 |
| **Total Onda 1** |  | **8 VPS** |  | **EUR 86,00/mês** |

Capacidade nominal agregada: 52 vCPU, 148 GB de RAM e 1.250 GB NVMe incluídos. A Hostinger permanece como origem/fallback; esta onda não autoriza SLA nem sua retirada.

## Onda 2 — HA e saída controlada da Hostinger

| Incremento | SKU | Qtd. | Referência unitária | Subtotal |
|---|---:|---:|---:|---:|
| Segundo Wazuh edge | Cloud VPS 10 | 1 | EUR 4,50 | EUR 4,50 |
| Terceiro Wazuh worker | Cloud VPS 30 | 1 | EUR 14,00 | EUR 14,00 |
| **Incremento Onda 2** |  | **2 VPS** |  | **EUR 18,50/mês** |
| **Total cumulativo** |  | **10 VPS** |  | **EUR 104,50/mês** |

Capacidade nominal cumulativa: 63 vCPU, 180 GB de RAM e 1.525 GB NVMe incluídos. A Hostinger só pode sair após edge redundante, teste N−1 e estabilidade de 7–14 dias.

## Object Storage S3 — linha separada

| Capacidade de referência | Estimativa mensal |
|---:|---:|
| 250 GB | EUR 2,49 |
| 500 GB | EUR 4,98 |
| 1 TB | EUR 9,96 |
| 2 TB | EUR 19,92 |
| 5 TB | EUR 49,80 |
| 10 TB | EUR 99,60 |

O cenário inicial ilustrativo de Onda 2 + 1 TB soma **EUR 114,46/mês**, deixando margem aritmética de EUR 1.885,54 frente ao teto. Essa margem não representa orçamento livre: ainda faltam impostos, máquinas atuais, RMM, IA, operação, monitoramento e eventuais adicionais.

## Critério de aprovação

Antes de qualquer contratação, o Platform Admin deve anexar uma cotação datada do carrinho/conta Contabo confirmando:

1. disponibilidade dos SKUs no datacenter UE escolhido;
2. preço final, prazo mensal, VAT/país de faturamento e add-ons/IPs;
3. capacidade S3 calculada pela retenção/RPO e custo de crescimento;
4. custo das VPS Zabbix/AIOps atuais, RMM, IA, operação e monitoramento externo;
5. total consolidado com margem de crescimento dentro de EUR 2.000/mês;
6. owners financeiro e técnico e aprovação explícita de cada onda.

Sem esses seis itens, a BOM permanece referência e o Gate Financeiro fica **NO-GO**.

## Fontes oficiais

- [Contabo — pricing](https://contabo.com/en/pricing/)
- [Contabo — Object Storage](https://contabo.com/en/object-storage/)
- [Contabo — política de tráfego/fair use](https://help.contabo.com/en/support/solutions/articles/103000271195-are-there-any-bandwidth-limits-at-contabo-)
- [Contabo — taxa de localização](https://help.contabo.com/en/support/solutions/articles/103000269774-what-is-the-location-fee-)
- [Contabo — alteração de preço-base](https://help.contabo.com/en/support/solutions/articles/103000406805-why-did-my-service-price-increase-)
