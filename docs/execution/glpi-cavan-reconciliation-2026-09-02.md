# GLPI — reconciliação Cavan — 02/09/2026

## Resultado desta etapa

A comparação somente leitura encontrou 15 hosts da matriz no Zabbix e 14
registros correspondentes no GLPI. A diferença é estrutural: o Zabbix mantém
dois testes de conectividade WAN e um host para o firewall físico, enquanto o
GLPI ainda possui dois equipamentos representando os links. O inventário
canônico esperado é de 13 ativos, com os dois links preservados como testes de
serviço, não como appliances adicionais.

O mapeamento por IDs está versionado em
[`../../config/glpi/cavan-matriz-reconciliation-v1.yaml`](../../config/glpi/cavan-matriz-reconciliation-v1.yaml).
Ele registra também três VMs atualmente classificadas como
`NetworkEquipment`; essa conversão foi separada para uma migração com
preservação de histórico.

## Metadados aplicados

Uma transação pela camada de modelos do GLPI:

- criou `Matriz — São Paulo` na entidade Cavan;
- vinculou à localização os oito computadores e seis equipamentos de rede da
  matriz já existentes;
- corrigiu o fabricante do `SW01-SP-Core` de Cisco para Aruba;
- removeu o modelo Catalyst incorreto e deixou o modelo vazio até o SNMP
  retornar `sysObjectID`/`sysDescr` confiável.

A verificação posterior confirmou os 14 vínculos de localização e o fabricante
Aruba. Nenhum ativo foi criado, excluído ou movido de entidade. Snapshot para
rollback: `/opt/n-infraops/rollback/glpi-cavan-metadata-20260902T184242-0300`.

## Contenção do inventário nativo

O endpoint de inventário estava habilitado sem autenticação e continha sete
registros de agente sem ativo vinculado. Seis nomes armazenavam payloads de
scanner baseados em `SELECT/EXISTS/SLEEP`, recebidos entre 15 e 27/07/2026.
A auditoria não encontrou esses padrões em computadores, usuários ou logs,
nem ativos criados na janela. Os registros foram preservados e nenhum dado foi
apagado.

Como contenção reversível, `enabled_inventory` passou de `1` para `0` pela
configuração do GLPI. A rota privada responde 403 e a pública continua
protegida pelo Authentik com 302. Evidência restrita:
`/opt/n-infraops/rollback/glpi-inventory-containment-20260902T184702-0300-retry1`.

O GLPI Agent não será ativado até existir autenticação própria do endpoint,
restrição de origem para o piloto e regra explícita que importe na entidade
Cavan. Descoberta de rede, inventário de rede e deployment permanecerão
desligados no piloto; somente inventário do computador será permitido.

## Pendências funcionais da F3

1. consolidar o firewall físico e os dois testes WAN sem perder histórico;
2. migrar as três VMs classificadas como equipamento de rede;
3. reabrir o inventário somente com autenticação e origem controlada;
4. executar um único agente piloto e reconciliar o resultado, sem criação
   duplicada;
5. provar isolamento entre entidades e o ciclo completo de ticket.
