# Especificação de compra — Zabbix permanente na Contabo

> Data: 24/08/2026
> Estado: aprovada como direção; SKU e preço devem ser confirmados no catálogo Contabo no momento da contratação
> Destino: produção definitiva do Zabbix no ness.OS

## Decisão de reaproveitamento

A VPS nova não é recurso temporário. Ela será o Zabbix de produção após restore, UAT e cutover. A VPS atual `144.91.72.202` será preservada intacta como rollback por 7–14 dias e, após aceite formal, liberação forense e reinstalação total, será reaproveitada no piloto Wazuh como Hub all-in-one/candidata futura a indexer.

A Hostinger KVM8 permanece somente como fábrica isolada de saneamento e pacote reproduzível; não será ponte de produção.

## Classe mínima de contratação

| Dimensão | Requisito inicial | Critério |
|---|---|---|
| Provedor/região | Contabo, região EU compatível com o ambiente atual | manter baixa complexidade operacional e domínio de falha conhecido |
| Classe de referência | equivalente a `Storage VPS 40` | validar nome comercial vigente antes da compra |
| CPU | 8 vCPU no mínimo | mesma capacidade observada da origem; subir somente por busy/NVPS/fila medidos |
| RAM | 32 GB preferencial; 24 GB mínimo | origem possui aproximadamente 31,5 GB e KVM8 de ensaio possui 32 GB |
| Armazenamento | contratado separadamente; SSD/NVMe com pelo menos 400 GB úteis | banco restaurado com 34.574.450.688 bytes; origem usa cerca de 76 GB; preferir 1 TB se o diferencial comercial for pequeno |
| Rede | IPv4 público, rede privada/VPN disponível e tráfego compatível com proxies | 443 público; 10051 somente allowlist/VPN; banco nunca público |
| Sistema | Debian 12 limpo | paridade com staging e origem saneada |
| Zabbix | 7.0 LTS, versão fixada e compatível com proxies | não atualizar major durante o cutover |
| Banco | MariaDB 10.11, localhost-only | tuning somente após métricas da nova VPS |
| Backup | Restic para Contabo Object Storage, conjunto `COMPLETED` e SHA-256 | upload, `check` e restore isolado obrigatórios antes do GO |

## Segurança e operação obrigatórias

- acesso nominal `ness_admin`, chave SSH e `sudo`; root, senha e keyboard-interactive desabilitados;
- firewall default-deny; SSH administrativo restrito assim que as origens forem conhecidas;
- TCP/10051 somente para proxies/agentes explicitamente aprovados; TCP/3306 apenas localhost;
- TLS válido no frontend; headers, logs, Fail2ban, NTP e atualizações de segurança;
- `EnableGlobalScripts=0`; scripts históricos neutralizados;
- actions, media types, connectors e notificações desabilitados durante restore/UAT;
- segredos humanos no Psono Community e segredos de automação em SOPS/age antes do go-live;
- monitoração externa do próprio Zabbix, MariaDB, frontend, certificado, backup e capacidade.

## Critérios de aceite da compra

1. CPU/RAM e armazenamento entregues conforme o pedido; virtualização e região registradas.
2. Debian limpo e implantação reproduzível a partir do código/runbooks, sem copiar arquivos históricos cegamente.
3. Restore com schema/contagens/checksums equivalentes à carga aprovada na KVM8.
4. UAT funcional e de segurança sem coleta, execução remota ou notificação acidental.
5. Teste de carga com NVPS, fila, busy processes, preprocessamento, MariaDB e I/O registrados.
6. Backup externo, `restic check` e restore isolado aprovados na nova VPS.
7. Rollback para `144.91.72.202` testável e prazo de 7–14 dias registrado.

## Gatilhos de redimensionamento

Não comprar capacidade para 7.000 ativos no primeiro dia. Reavaliar a classe quando CPU p95 superar 60% por 14 dias, busy processes permanecerem acima do limite operacional, fila/backpressure crescer, I/O/housekeeping sair do SLO ou a previsão de armazenamento alcançar 80% em 90 dias.

## Resultado financeiro/arquitetural

A compra líquida é de uma VPS permanente. Depois do período de rollback, a capacidade antiga deixa de ser redundância ociosa e reduz em uma unidade a compra inicial do Wazuh. Assim, as duas VPS Contabo permanecem justificadas no estado-alvo: nova VPS como Zabbix e antiga, após reimage, como nó do piloto Wazuh.
