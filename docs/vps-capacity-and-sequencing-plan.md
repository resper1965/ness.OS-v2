# Plano de capacidade e sequência de VPS — ness.OS

> Data-base: 21/08/2026
> Estado: direção aprovada para planejamento; dimensionamento Wazuh de produção depende de piloto e medição de APS/EPS.

## Decisões executivas

1. O cofre Community não compartilhará host com Zabbix, AIOps/GLPI, Wazuh nem plataforma de phishing. Psono Community foi escolhido; Passbolt Community é apenas contingência se o PoC reprovar.
2. A plataforma de phishing ficará em VPS de laboratório segregada e poderá ser criada somente durante campanhas. Ela pode compartilhar host com outras ferramentas de laboratório, mas nunca com identidade, cofre, ITSM ou monitoração.
3. O GLPI e o catálogo de serviços passam a ser prioridade funcional imediata. O GLPI permanece na VPS AIOps enquanto capacidade e SLO permitirem; o banco observado é pequeno e ainda não justifica outra VPS.
4. O polimento lógico do Zabbix será feito antes da migração. Tuning dependente de SO, banco e I/O será concluído depois da reconstrução.
5. A reconstrução usará a Hostinger KVM8 somente como fábrica de transmutação. Foi aprovada a compra de uma nova VPS Contabo permanente, que será o Zabbix definitivo. A origem atual será preservada como rollback por 7–14 dias e, após aceite/liberação forense e reimage total, reutilizada no piloto Wazuh.
6. Wazuh não compartilhará as duas VPS atuais. Para 7.000 agentes, o estado-alvo será distribuído; a quantidade final de indexadores, workers e armazenamento será fechada após piloto com volume real.

## Cofre Community e laboratório de phishing

O PoC usará Psono Community em uma VPS de 2 vCPU, 4 GB RAM e 40 GB, com aplicação e PostgreSQL isolados em contêineres/redes distintas, SMTP, NTP, TLS, backup externo e healthcheck. A documentação Psono recomenda separar aplicação e banco em produção; para a pequena equipe inicial será aceita uma única VPS como compromisso de custo, sem HA, desde que backup/restore seja comprovado. Se o PoC falhar, Passbolt Community usará a mesma classe de VPS.

Mesmo com contêineres separados, coabitar o cofre com uma plataforma de phishing ampliaria o raio de impacto de uma aplicação deliberadamente exposta a conteúdo, links e campanhas. A economia de uma VPS pequena não compensa o risco de perder simultaneamente o ambiente e as credenciais de recuperação.

Para reduzir custo, o laboratório de phishing será efêmero quando possível: provisionar para a campanha, preservar configuração/evidência necessária, remover dados pessoais conforme política e destruir/reinstalar a VPS. O domínio, IP de envio e reputação de e-mail devem permanecer segregados dos domínios transacionais do ness.OS.

## Reconstrução do Zabbix

### Papel da Hostinger KVM8 temporária

A KVM8 disponibilizada por Ricardo será um ambiente efêmero de engenharia, não o destino permanente. Ela fica fora da contagem permanente de VPS do ness.OS. Em razão da restrição de armazenamento/topologia entre Hostinger e Contabo, a KVM8 poderá ser promovida a ponte operacional temporária somente após UAT e go/no-go explícito: produção atual na Contabo → KVM8 → Contabo limpa. O endereço definitivo continuará pertencendo ao ambiente Contabo.

Na KVM8 serão executados restaurações repetíveis, saneamento de configuração, ensaios de atualização, testes funcionais e de carga e a construção do pacote versionado que será aplicado na VPS Contabo limpa. Um backup antigo pode alimentar os ensaios; cada transição operacional exigirá carga atualizada extraída dentro da janela aprovada. O roteiro operacional e os critérios de descarte estão em [`execution/zabbix-transmutation-kvm8-plan.md`](execution/zabbix-transmutation-kvm8-plan.md).

### Capacidade inicial

A especificação de aquisição e aceite está em [`procurement/zabbix-contabo-permanent-spec-2026-08-24.md`](procurement/zabbix-contabo-permanent-spec-2026-08-24.md).

- Manter inicialmente a classe observada: 8 vCPU, 24–32 GB RAM e armazenamento SSD de pelo menos 400 GB; preferir 1 TB se o preço permanecer próximo ao plano atual.
- Não dimensionar somente pelos 7.000 ativos. Os fatores reais são itens habilitados, intervalo médio, NVPS, history/trends, LLD, proxies, preprocessamento e retenção.
- Manter Zabbix Server e proxies na mesma versão major 7.0 para compatibilidade completa.

### Trabalho necessário

1. Medir NVPS, filas, processos ocupados, crescimento diário e I/O no ambiente atual.
2. Provisionar Debian limpo, acesso nominal, firewall, NTP, TLS, backup e monitoração externa.
3. Instalar versões fixadas de Zabbix 7.0 LTS, frontend e MariaDB compatível.
4. Restaurar cópia do banco de aproximadamente 39 GiB em staging e medir o tempo real de restore.
5. Sanear usuários, roles, tokens, scripts, actions, media types, webhooks, macros e segredos.
6. Aplicar a configuração segura como código; não copiar cegamente arquivos históricos do host comprometido.
7. Atualizar proxies para a mesma major, configurar TLS PSK/certificados e restringir 10051 às origens aprovadas.
8. Executar UAT de coleta, trigger, incidente, notificação, proxy e backup.
9. Gerar na KVM8 o pacote reproduzível: código de infraestrutura, versões/digests, configuração saneada, checksums, inventário de segredos, backup validado e runbooks.
10. Provisionar a nova VPS Contabo Zabbix definitiva, classe inicial equivalente à atual (8 vCPU e 24–32 GB RAM, armazenamento separado), com o pacote aprovado e repetir restore/UAT sem depender do estado interno da KVM8.
11. Congelar mudanças, realizar dump final, cortar DNS/IP para a VPS definitiva e observar por 7–14 dias.
12. Manter a VPS antiga como evidência até aceite; depois reinstalá-la do zero antes de qualquer reutilização. Apagar com segurança a KVM8 após comprovar que nenhum artefato necessário existe somente nela.

O esforço esperado é de 3–5 dias úteis de engenharia mais 7–14 dias de observação. A indisponibilidade de corte somente será estimada depois do teste de restauração; com o banco atual, planejar provisoriamente uma janela de 1–3 horas.

## Polimento antes e depois da migração

### Antes da migração

- corrigir itens não suportados e triggers desconhecidos por lotes;
- remover ou desabilitar objetos obsoletos;
- normalizar hosts, grupos, templates, macros, clientes, localidades e manutenções;
- revisar discovery, intervalos, timeouts, dependências e severidades;
- reduzir tempestades de eventos e escalations vencidas;
- usar GLPI como fonte de localização, owner e criticidade antes de reconstruir Geomap/mapas;
- exportar configuração, registrar diff e gerar backup antes de cada onda.

### Depois da migração

- tuning de MariaDB, caches, pollers, preprocessors, escalators e housekeeping;
- tuning de filesystem/I/O e retenção com base na nova VPS;
- validação de TLS dos proxies, firewall, backup/restore e SLO;
- acabamento de mapas, dashboards e experiência do operador sobre dados já saneados.

## Wazuh hub-and-spoke

### Princípios

- O Wazuh possui server/manager, indexer e dashboard; para escala alta eles serão separados.
- O quickstart all-in-one é referência apenas para piloto de até 100 endpoints e 90 dias.
- A documentação atual recomenda, por nó indexer, 8 vCPU e 16 GB RAM; disco depende dos alertas por segundo e retenção.
- Armazenar no Wazuh alertas pesquisáveis pelo prazo operacional; manter 12 meses apenas para incidentes qualificados no AIOps/GLPI. Snapshots frios podem ir para Object Storage.
- Spoke não será criado automaticamente por cliente. Será usado quando houver rede isolada, necessidade de buffer/localidade, syslog local ou requisito contratual. Sempre que possível, a VM spoke pertence à infraestrutura do cliente.

### Etapa A — piloto

| Função | Quantidade | Capacidade inicial | Origem |
|---|---:|---|---|
| Wazuh Hub all-in-one | 1 | 8 vCPU, 16–30 GB RAM, 300 GB–1,2 TB SSD | Reutilizar VPS Zabbix antiga somente após aceite, preservação e reimage total |
| Wazuh Spoke piloto | 1 | 4 vCPU, 8 GB RAM, 80–150 GB | Preferencialmente VM no cliente; VPS segregada se necessário |

O piloto começa com 50–100 agentes representativos por 30 dias e mede eventos/alertas por segundo, bytes por agente/dia, CPU, heap, fila, shards, latência e taxa de conversão em incidente.

### Etapa B — produção distribuída para até 7.000 agentes

| Função central | Quantidade-base | Capacidade por nó | Observação |
|---|---:|---|---|
| Wazuh indexer | 3 | 8 vCPU, 16–32 GB RAM, 1–2 TB SSD/NVMe | Quórum/replicação; tamanho final depende do piloto e retenção |
| Wazuh server | 2 inicialmente | 8 vCPU, 8–16 GB RAM, 100–200 GB | 1 master + 1 worker; adicionar worker conforme fila/APS |
| Dashboard + balanceador | 1 | 4 vCPU, 8 GB RAM, 80–100 GB | Sem banco de dados compartilhado com AIOps |
| Spokes | `N` | 4–8 vCPU, 8–16 GB RAM, 100–300 GB | Somente onde a topologia/requisito justificar |

Base central: seis VPS Wazuh. Crescimento provável: sete ou mais ao adicionar workers. Uma das três VPS indexer poderá ser a antiga VPS Zabbix depois de reinstalada; portanto a compra líquida central pode começar em cinco VPS, não seis.

Portas de referência: agentes em 1514/TCP, enrollment em 1515/TCP, cluster de managers em 1516/TCP, API server em 55000/TCP, API indexer em 9200/TCP, cluster indexer em 9300/TCP e dashboard em 443/TCP. APIs e portas de cluster ficam apenas em rede privada/VPN.

### Cenário de processamento para 5.000 endpoints — fotografia de 21/08/2026

Este cenário considera apenas processamento. Disco e retenção são contratados e tratados separadamente. A projeção parte da carga observada no Wazuh atual com 624 endpoints: 4 vCPU, CPU média de 21,2% e pico de 41,16%. O fator de expansão para 5.000 endpoints é 8,01, resultando em aproximadamente 6,8 vCPU médios e 13,2 vCPU no pico antes da separação de papéis, redundância e reserva operacional.

#### Capacidade existente

| Máquina | Estado observado | Papel preservado |
|---|---|---|
| Contabo Zabbix `144.91.72.202` | 8 vCPU, 31,5 GB RAM, 1,2 TB; serviços Zabbix/MariaDB/Apache ativos | origem e rollback por 7–14 dias; após reimage, Hub piloto/candidato a indexer Wazuh |
| Contabo AIOps `144.91.115.242` | 8 vCPU, 23,5 GB RAM, 400 GB; Docker ativo | ness.OS, GLPI, Authentik e integrações |
| Hostinger Wazuh `62.72.8.164` | 4 vCPU, 16 GB RAM, 200 GB; 624 endpoints | origem temporária da migração; não entra na capacidade-alvo e será desativada |
| Hostinger KVM8 `148.230.77.242` | 8 vCPU, 32 GB RAM, 400 GB | fábrica temporária da transmutação Zabbix; não entra na capacidade permanente |

#### Capacidade final — topologia hub-spoke para até 5.000 endpoints

| Papel | Quantidade nova | Classe Contabo de referência | CPU/RAM por nó |
|---|---:|---|---:|
| Indexer no hub | 3 | Cloud VPS 40 | 12 vCPU, 48 GB |
| Wazuh master no hub | 1 | Cloud VPS 20 | 6 vCPU, 12 GB |
| Worker/spoke | 4 | Cloud VPS 30 | 8 vCPU, 24 GB |
| Dashboard/API/balanceador HA | 2 | Cloud VPS 10 | 3 vCPU, 8 GB |
| Psono Community | 1 | Cloud VPS 10 | 3 vCPU, 8 GB |

O teto permanente, sem contar com a sobrevivência da Hostinger, continua sendo **11 VPS**, mas ele não será comprado no primeiro dia. O Wazuh Hostinger permanece somente como origem dos 624 endpoints durante a migração. A plataforma de phishing acrescenta um Cloud VPS 10 temporário apenas durante campanhas.

No teto de 5.000 endpoints, os quatro spokes Contabo distribuem cerca de 1.250 endpoints cada. Durante a migração, a comunicação com o Wazuh Hostinger ocorre exclusivamente por VPN site-to-site e sem torná-lo membro permanente do cluster; a porta 1516 nunca será publicada na Internet.

#### Compra progressiva aprovada

| Onda | Faixa operacional | Compra acumulada | Incremento | Condição |
|---|---:|---:|---:|---|
| 0 — transmutação | 624 atuais | 1 VPS permanente | nova Contabo para Zabbix definitivo; KVM8 apenas staging e origem atual preservada para rollback |
| 1 — fundação | até ~1.000 | 8 VPS | 3 indexers VPS 30, 1 master VPS 20, 2 workers VPS 30, 1 edge VPS 10 e 1 Psono VPS 10 | homologação; edge ainda sem HA |
| 2 — produção | até ~2.500 | 10 VPS | +1 edge VPS 10 e +1 worker VPS 30 | concluir antes de assumir SLA e retirar Hostinger |
| 3 — crescimento | até ~3.750 | 11 VPS | +1 worker VPS 30 | manter N−1 com quatro workers |
| 4 — teto | até ~5.000 | 11 VPS | sem novo nó; substituir indexers VPS 30 por VPS 40 em rolling, somente se necessário | capacidade comprovada por métricas |

Uma nova onda é aberta quando ocorrer qualquer um destes gatilhos: 70% da faixa de endpoints; previsão de atingir 80% em 90 dias; CPU p95 de workers/indexers acima de 60% por 14 dias; fila/backpressure persistente; heap/latência do indexer fora do SLO; ou teste N−1 reprovado. Contagem de endpoints isoladamente não autoriza compra.

A API Contabo documenta upgrade de add-ons, mas não redimensionamento de CPU/RAM da instância. Por isso, mudança de classe será feita por substituição rolling: adicionar novo nó, sincronizar, validar, retirar o antigo e só então cancelar o recurso substituído.

## GLPI prioritário

O GLPI permanece na VPS AIOps atual, que possui 8 vCPU, 23 GiB RAM e 400 GB; o banco GLPI observado tinha cerca de 62 MB. Antes de criar outra VPS, serão aplicados limites de recursos, rede de dados separada, versão fixada, backup/restore e métricas.

### Onda 1 — fundação (semana 1)

- homologar login/logout/Auth­entik, perfis e entidades;
- fixar versão do GLPI e documentar deploy/rollback;
- testar backup e restauração do banco, documentos e plugins;
- definir identidade/deduplicação do GLPI Agent;
- criar ambiente de homologação lógico separado da operação.

### Onda 2 — governança e catálogo (semanas 1–3)

- workshops com Governança para serviços, owners, clientes, horários, impacto, criticidade, SLA/OLA, grupos resolvedores, aprovações e conhecimento;
- publicar primeiro catálogo com 10–20 serviços prioritários;
- definir modelos separados para incidente, requisição, problema e mudança;
- vincular cada serviço aos ativos/locais da CMDB.

### Onda 3 — inventário (semanas 2–4)

- piloto do GLPI Agent em grupo representativo;
- distribuição pelo RMM já presente em cada ativo;
- reconciliação com SuperOps, Atera, Datto e Zabbix;
- medir cobertura, duplicidade, última comunicação e qualidade de localização/owner.

### Onda 4 — integrações

- Zabbix/Wazuh/AIOps abrem ou enriquecem somente incidentes qualificados;
- deduplicação e idempotência impedem múltiplos tickets para o mesmo incidente;
- PWA apresenta o incidente e referencia o ticket canônico no GLPI.

Separar o GLPI em outra VPS somente se métricas demonstrarem saturação/competição, se o SLO exigir domínio de falha próprio ou se crescimento de inventário/documentos tornar o backup incompatível com o RTO.

## Quadro consolidado de VPS

| Momento | VPS totais Ness | Mudança líquida | Observação |
|---|---:|---:|---|
| Atual | 2 | 0 | Zabbix e AIOps/GLPI |
| Próximo passo seguro | 3 | +1 | Cofre Community dedicado; PoC Psono |
| Campanha de phishing ativa | 4 | +1 temporária | Laboratório segregado/efêmero |
| Transmutação Zabbix em KVM8 | 4–5 | +1 temporária já disponível | Fábrica efêmera; pode ser ponte operacional curta, mas não substitui o destino Contabo |
| Corte para Contabo limpa | 4–5 | +1 permanente | Nova VPS torna-se Zabbix definitivo; origem fica como rollback por 7–14 dias e depois é reaproveitada no Wazuh |
| Piloto Wazuh após aceite Zabbix | 4–5 | 0 adicional | Reimage da antiga VPS Zabbix para Wazuh Hub piloto |
| Wazuh onda 1 | 10 | +8 | Zabbix e AIOps existentes + oito VPS novas; até ~1.000 endpoints |
| Wazuh onda 2 | 12 | +2 | segundo edge e terceiro worker; até ~2.500 endpoints |
| Wazuh ondas 3–4 | 13 | +1 | quarto worker; 11 VPS novas no teto de 5.000 endpoints |

Este quadro não inclui Object Storage, que é serviço de armazenamento e não VPS, nem MISP externo.

## Referências oficiais

- Psono e Passbolt Community: edições, instalação, recuperação, HTTPS, backup e healthcheck.
- Wazuh: arquitetura, quickstart, indexer, dashboard, portas e implantação distribuída.
- Zabbix 7.0: compatibilidade de proxies e TLS PSK/certificados.
