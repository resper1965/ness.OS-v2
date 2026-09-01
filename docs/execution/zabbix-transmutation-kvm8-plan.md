# Transmutação do Zabbix em Hostinger KVM8 temporária

> Estado: KVM8 reinstalada e baseline endurecida; aguarda prazo de descarte e carga de ensaio
> Papel: staging efêmero e, se aprovado, ponte operacional curta; nunca destino permanente
> Produção vigente: `144.91.72.202`, mantida até o cutover aprovado

## Objetivo

Usar a capacidade da KVM8 para restaurar e transformar o Zabbix fora da produção, provar a recuperação e produzir uma implantação reproduzível para a Contabo limpa. A KVM8 não entra na capacidade permanente do ness.OS. Se for necessário liberar e reinstalar a VPS Contabo atual, ela poderá sustentar a operação somente pelo intervalo previamente aprovado entre os dois cortes.

## Dados de acesso resolvidos

- IP `148.230.77.242`, usuário `ness_admin`, SSH/22 por chave dedicada e `sudo` validados;
- Debian 12 reinstalado do zero em KVM8 com 8 vCPU, 32 GB RAM e 400 GB, igual ao SO da origem;
- MariaDB 10.11.18 e Zabbix 7.0.27 instalados nas versões exatas da produção, com o server mascarado até o restore;
- firewall do provedor e do SO permitem somente SSH nesta fase;
- evidências em [`zabbix-kvm8-bootstrap-2026-08-21.md`](zabbix-kvm8-bootstrap-2026-08-21.md).

Ainda são necessários:

- data e hora limite para devolução/destruição;
- decisão sobre snapshot temporário antes de eventual promoção operacional.

Não enviar senha, chave privada ou token pelo chat. Acesso inicial deve usar chave pública; qualquer segredo necessário ficará temporariamente em arquivo `root:root` modo `600` e migrará para Psono/SOPS assim que disponíveis.

## Regras de segurança e mudança

1. Não apontar DNS, agentes ou proxies de produção para a KVM8 durante os ensaios. Uma promoção temporária exige UAT, backup, rollback, janela e go/no-go próprios.
2. Não habilitar actions, media types, webhooks ou notificações reais no restore de ensaio.
3. Não permitir coleta paralela que duplique eventos ou altere estado nos ativos.
4. Toda cópia deve ter SHA-256 conferido na origem e no destino; transporte apenas por SSH autenticado ou repositório criptografado.
5. Mudanças que afetem a VPS Zabbix vigente obedecem à janela 22:00–00:00 BRT. Trabalho isolado na KVM8 pode ocorrer fora dela.
6. Configurações históricas do host comprometido não serão copiadas cegamente. Segredos, scripts, users, roles, tokens, macros e integrações serão reconstruídos ou saneados.
7. A KVM8 não receberá credenciais operacionais antes de baseline, hardening e inventário de exposição; credenciais usadas na ponte serão rotacionadas ao retornar à Contabo.
8. A capacidade de armazenamento não será presumida entre provedores. Dumps e artefatos devem caber no disco local temporário ou atravessar um caminho de transferência previamente medido e verificado.

## Sequência de execução

### Fase 1 — entrada e baseline

- registrar plano, CPU, RAM, disco, rede, SO, relógio e recursos do provedor;
- reinstalar com imagem limpa suportada, se autorizado, e aplicar patches;
- criar acesso nominal, validar `sudo`, desabilitar SSH por senha/root e restringir firewall;
- configurar NTP, logs persistentes, Fail2ban e monitoração externa mínima;
- registrar versões, portas e hashes da configuração-base.

### Fase 2 — fábrica reproduzível

- provisionar Zabbix 7.0 LTS, frontend e MariaDB compatível usando código versionado e versões/digests fixos;
- separar dados, configuração e segredos; nenhum passo indispensável pode existir somente no shell history;
- deixar envio de mensagens, webhooks e actions desabilitados por padrão;
- criar rotinas idempotentes de instalação, backup, restore, validação e rollback.

### Fase 3 — ensaio de restauração e transmutação

- importar uma cópia verificada do banco e dos artefatos necessários;
- medir duração, espaço temporário, crescimento do banco e recursos máximos do restore;
- validar schema, versão, hosts, itens, triggers, proxies, templates e dependências;
- ensaiar qualquer atualização de schema em etapas suportadas, preservando evidência antes/depois;
- sanear usuários, roles, tokens, scripts, actions, media types, webhooks, macros e segredos;
- comprovar que nenhum canal real de notificação ou execução remota ficou ativo por acidente.

### Fase 4 — polimento pré-corte

- reduzir itens não suportados, triggers desconhecidos e escalations obsoletas por lotes com rollback;
- normalizar grupos, templates, tags, severidades, macros, manutenções e ownership;
- usar o GLPI como fonte de localização, criticidade e responsável para Geomap/mapas;
- revisar discovery, intervalos, timeout, dependências e ruído;
- manter dashboards e mapas executivos sobre dados saneados, com cobertura e qualidade explícitas.

O polimento lógico começa antes da migração. Tuning dependente de disco, filesystem, banco e I/O será repetido na VPS final.

### Fase 5 — qualificação

- testar coleta representativa sem dupla ingestão, preferencialmente com hosts/proxy de laboratório;
- testar autenticação, RBAC, MFA, logout, revogação e duas contas break-glass;
- testar backup e restauração integral em isolamento;
- medir NVPS, filas, busy processes, preprocessamento, housekeeping, banco e I/O;
- executar UAT de host, item, trigger, evento qualificado, incidente, proxy, TLS e interface;
- registrar RTO/RPO medidos, pendências aceitas e capacidade projetada por 12 meses.

### Fase 6 — pacote de saída

Antes de liberar a KVM8, produzir e copiar para repositório/armazenamento externo:

- infraestrutura e configuração como código;
- matriz de versões/digests e inventário de pacotes;
- exportações saneadas, migrations e checksums;
- inventário de segredos sem seus valores;
- backup final validado e evidência do teste de restore;
- runbooks de deploy, cutover, rollback, backup, restore e perda total;
- relatório de capacidade, riscos residuais e aceite técnico.

Nenhum segredo, dump ou evidência sensível será commitado no Git.

### Fase 7 — nova Contabo permanente e corte direto

Decisão aprovada por Ricardo Esper em 24/08/2026: contratar uma nova VPS Contabo permanente para o Zabbix, desde que o recurso permaneça útil no ness.OS após a migração. A condição é atendida porque a nova VPS será o Zabbix de produção definitivo; não será descartada após o corte.

- referência inicial: classe equivalente à atual, `Storage VPS 40`, 8 vCPU e 24–32 GB RAM; armazenamento é dimensionado/contratado separadamente;
- aplicar Debian limpo, hardening, acesso nominal, firewall, TLS, monitoração e o pacote reproduzível aprovado na KVM8;
- repetir restore e UAT na nova Contabo sem ligar coleta, proxies, actions ou notificações reais;
- preparar TTL/DNS, congelamento, comunicação, go/no-go e rollback material para um único corte produtivo;
- na janela, obter backup final da origem, validar hash, restaurar no destino, repetir contagens e cortar DNS/proxies/agentes em ondas;
- preservar a VPS Zabbix atual intacta como rollback por 7–14 dias;
- após aceite formal e liberação forense, reinstalar do zero a VPS antiga e reaproveitá-la no piloto Wazuh: primeiro como Hub all-in-one e, se o piloto distribuído aprovar, como candidata a um dos indexadores;
- rotacionar os segredos que tocaram origem/KVM8 e descartar a KVM8 somente quando nenhuma dependência permanecer nela.

A KVM8 permanece fábrica de saneamento e ensaio, mas deixa de ser ponte operacional planejada. Isso elimina um corte adicional, evita produção na Hostinger e mantém rollback material na Contabo antiga.

### Fase 8 — descarte da KVM8

- confirmar que código, evidências e backups necessários existem fora dela e conferem por checksum;
- revogar chaves, tokens e credenciais temporárias;
- remover snapshots, volumes e backups do provedor conforme o escopo contratado;
- executar reinstalação/eliminação disponibilizada pelo provedor e registrar a evidência;
- cancelar/devolver a KVM8 dentro do prazo informado.

## Critérios de aceite

- duas restaurações consecutivas e reproduzíveis sem passos secretos manuais;
- UAT funcional e de segurança aprovado, sem notificações ou execução remota acidentais;
- RTO/RPO e capacidade medidos, não estimados apenas por quantidade de hosts;
- implantação da Contabo limpa reproduzível a partir de código, backup e runbooks externos à KVM8;
- KVM8 sem qualquer dependência de produção e com descarte comprovado.

## Bloqueios atuais

- prazo exato de disponibilidade/descarte da KVM8;
- contratação e provisionamento da nova VPS Contabo permanente;
- definição da capacidade de armazenamento/IOPS da nova VPS a partir da retenção e do crescimento medidos;
- confirmação da limitação exata de storage/transferência Hostinger ↔ Contabo e espaço livre real da KVM8.
