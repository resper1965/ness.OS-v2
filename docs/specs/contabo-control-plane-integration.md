# Especificação — integração do plano de controle Contabo

## Objetivo

Trazer à gestão do ness.OS uma visão verificável das VPS e do Object Storage da Contabo, correlacionada ao GLPI e ao Zabbix, sem expor credenciais nem transformar o painel em console irrestrito do provedor.

## Fronteira de segurança

- somente o backend acessa a API Contabo;
- credencial em cofre, nunca no navegador, Git ou banco analítico;
- integração começa read-only;
- telas e endpoints administrativos exigem `platform_admin`;
- membros iniciais: Ismael Araujo, Rogerio Salerno e Ricardo Esper;
- MFA, auditoria e isolamento por tenant obrigatórios;
- ações futuras de start/stop/restart/resize exigem mudança aprovada e dupla confirmação.

## Coleta e frequência inicial

| Conjunto | Frequência | Uso |
|---|---:|---|
| Inventário, plano, região, IP e estado das VPS | 30 min | CMDB e capacidade instalada |
| Estado, ações e auditorias do provedor | 5 min | correlação, auditoria e incidentes |
| Snapshots/backups | 15 min | RPO e risco operacional |
| Firewalls e redes privadas | 30 min | exposição, segmentação e drift |
| Capacidade/uso do Object Storage | 1 h | retenção, crescimento e custo |
| Custos/assinaturas, se expostos pela API | 24 h | FinOps e previsão |

## Modelo normalizado

- `provider_resource`: ID imutável, tipo, região, plano, estado e vínculo ao CI GLPI;
- `provider_action`: ator/origem, operação, estado e timestamps;
- `backup_status`: recurso, tipo, última execução, idade e resultado;
- `capacity_forecast`: uso, headroom, tendência e horizonte;
- `control_finding`: recurso órfão, sem monitoramento, backup vencido ou divergência.

Segredos e chaves de Object Storage não integram esse modelo.

## Visão de gestão

O painel deve mostrar VPS por estado/região/papel, capacidade contratada, utilização observada pelo Zabbix, headroom, idade do último backup, crescimento do S3, firewalls/redes privadas, mudanças recentes, recursos órfãos e aderência ao plano de compras.

A correlação separa fontes:

- Contabo `running` + Zabbix indisponível: investigar sistema convidado/rede/agente;
- Contabo indisponível + Zabbix indisponível: provável camada do provedor;
- Contabo fornece inventário/estado e o Zabbix mostra CPU, memória, disco e serviços do sistema convidado; não se deve atribuir à API do provedor uma telemetria que ela não exponha;
- recurso Contabo sem CI no GLPI ou sem host no Zabbix: finding de governança;
- backup vencido: violação de RPO, não apenas alerta técnico.

## Fases

1. inventário read-only e reconciliação com GLPI/Zabbix;
2. métricas, backups, Object Storage e painel executivo;
3. findings e abertura automática de tickets/incidentes;
4. ações controladas, somente após workflow de mudança, auditoria e aprovação.
