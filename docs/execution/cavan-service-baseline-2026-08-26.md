# Cavan — baseline de serviços para o ness.OS

## Escopo

- Cliente/tenant: **Cavan**.
- Primeiro recorte operacional: **Matriz**; unidades fabris entram como
  contexto de ativos e serviços, não como tenants distintos.
- Ambiente: produção.
- Fonte de saúde inicial: Zabbix UAT, sem notificações ou automações ativas.

## Catálogo mínimo de saúde

| Serviço | Saúde consolidada | Ativos iniciais da Matriz | Severidade acordada |
|---|---|---|---|
| Conectividade corporativa | disponibilidade dos dois links em balanceamento | Fortigate AmericaNet WAN1; Fortigate Vivo LAN3 | uma perda: atenção; perda dos dois: crítica |
| Rede core | disponibilidade e capacidade do núcleo | SW01-SP-Core | crítica |
| Identidade e arquivos | autenticação e serviços de diretório | CL-AD02; VMAD01 | crítica |
| Virtualização | disponibilidade dos hypervisors | ESXI01; ESXI02; ESXI03 | crítica |
| Aplicações | disponibilidade dos serviços de negócio | VMAPP01; VMAPP02; VMAPH01 | alta |
| Dados | disponibilidade e capacidade do banco | VMSQLP01 | alta |
| Acesso remoto | disponibilidade do serviço remoto | VMRDS01 | alta |
| Observabilidade | saúde do caminho de monitoramento | Proxy Zabbix | alta |

## Uso nas ondas do ness.OS

1. **Zabbix:** etiquetas, dependências, mapas e ruído são organizados por este
   catálogo; não alterar templates inferidos sem validação técnica.
2. **GLPI:** cada serviço terá owner, ativos relacionados, tickets, SLA e
   runbook operacional.
3. **AIOps:** alertas são correlacionados primeiro por serviço; apenas
   incidentes confirmados chegam ao portal executivo.
4. **Portal:** mostra saúde geral da Cavan e a decomposição por serviços;
   usuários do cliente terão leitura apenas após go-live formal.

## Limites atuais

- Este é o baseline operacional, não catálogo comercial final.
- A descoberta de dependências e owners de negócio continuará durante o
  piloto; qualquer mudança de criticidade será versionada.
