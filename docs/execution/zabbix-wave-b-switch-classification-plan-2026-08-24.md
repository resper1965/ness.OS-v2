# Onda B de polimento Zabbix — classificação dos switches

> Estado: causa provável isolada; correção pendente de reconciliação GLPI e UAT

## Evidência

- 32 itens não suportados são exatamente 16 itens herdados em cada um de dois hosts.
- Hosts: `Cavan Matriz SW01-SP-Core` e `Cavan Sta Lucia SW01-SL-Core`.
- Único vínculo em ambos: `FortiGate by HTTP`.
- Os 16 itens abrangem serial, uptime, CPU, firmware, modelo, VDOM, memória, disco e descobertas SD-WAN; não é uma falha isolada de um JSONPath.
- Evidência root-only consolidada: `/var/lib/ness-os/restore-evidence/offline-polish-baseline-20260824T175248-0300.txt`.

## Decisão

Não editar os 16 preprocessamentos. Primeiro confirmar no GLPI e com o owner se os ativos são switches, FortiGates com nomes inadequados ou registros apontando para o endpoint errado.

## Execução do piloto

1. Reconciliar serial, fabricante, modelo, endereço de gestão, cliente, site e owner no GLPI.
2. Exportar via API os hosts, template, macros sem valores, triggers e gráficos.
3. Validar o endpoint em UAT sem exibir credenciais.
4. Se forem switches, selecionar o template oficial correspondente ao fabricante/modelo.
5. Usar `Unlink` sem `clear`, vincular o template correto e validar reconciliação dos itens.
6. Comparar disponibilidade, CPU, memória, interfaces, tráfego e eventos por 24–72 horas.
7. Manter o export e o vínculo antigo documentados para rollback; proibir exclusão/limpeza nesta onda.

## Gates

- classe e identidade do ativo aprovadas no GLPI;
- template compatível com fabricante, modelo e protocolo;
- 32 ocorrências eliminadas sem perda de métricas úteis;
- nenhuma macro/credencial registrada em relatório;
- nenhuma action, media type ou connector habilitado no UAT.

## Bloqueio atual

Faltam inventário confiável e API/UAT na nova VPS permanente. O banco isolado da KVM8 não será alterado por SQL.
