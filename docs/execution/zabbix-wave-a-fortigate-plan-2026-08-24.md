# Onda A de polimento Zabbix — FortiGate

> Estado: diagnóstico offline concluído; mudança funcional pendente de UAT na nova VPS permanente

## Resultado do diagnóstico

- 58 hosts de link WAN herdaram do template completo `FortiGate by SNMP` o item calculado `vfs.fs.pfree`.
- Os nomes representam interface/provedor; fabricante e modelo estão vazios no inventário.
- A normalização do trecho anterior a ` Link ` indica 35 appliances candidatos. Dezoito candidatos possuem dois ou mais hosts de link e, portanto, coleta de sistema potencialmente duplicada.
- A fórmula é idêntica à do template oficial Zabbix 7.0 e fica não suportada quando `fgSysDiskCapacity.0` resulta em zero.
- Evidência root-only: `/var/lib/ness-os/restore-evidence/offline-polish-baseline-20260824T174752-0300.txt` na KVM8.

## Decisão técnica

Não será criada uma fórmula que converta capacidade ausente em percentual fictício. A correção tem duas camadas:

1. modelar um host canônico por appliance FortiGate e monitorar seus links por descoberta de interfaces;
2. para modelos que comprovadamente não expõem capacidade de disco, usar um template ness.OS versionado sem `vfs.fs.pfree` e sem seu trigger associado.

Se alguma visão ou permissão exigir host por link durante a transição, ele receberá somente um template de interface; não uma cópia integral do template de appliance.

## Execução suportada e reversível

1. Exportar via API o template, os 58 hosts, vínculos, macros sem valores e dependências.
2. Selecionar um appliance piloto que possua ao menos dois links.
3. Promover ou criar seu host canônico e preencher fabricante, modelo, cliente, site e owner.
4. Vincular o template de appliance, habilitar descoberta das interfaces necessárias e manter os hosts legados ativos durante a comparação.
5. Comparar por 24–72 horas disponibilidade, perda, latência, tráfego, eventos e carga SNMP.
6. Se a capacidade de disco continuar ausente, aplicar ao canônico o template versionado sem disco.
7. Após aceite, desabilitar — sem excluir — os hosts de link legados por 30 dias.
8. Repetir por lote pequeno; exclusão e limpeza de histórico ficam fora desta onda.

Para migrar templates, usar `Unlink` sem `clear`, preservando entidades/histórico, e então vincular o template substituto. O Zabbix reconcilia itens existentes pela chave; o export prévio é o rollback. `Unlink and clear` fica proibido nesta onda.

## Gates

- redução do grupo de 58 ocorrências sem aumento em outras classes de `unsupported`;
- nenhuma coleta duplicada de sistema no piloto após o aceite;
- métricas dos links com paridade por 24–72 horas;
- inventário e tags mínimos preenchidos;
- nenhum valor sintético para capacidade ausente;
- rollback testado por relink/export;
- nenhuma action, media type ou connector habilitado no UAT.

## Bloqueio atual

A KVM8 permanece banco isolado, com `zabbix-server` inativo e mascarado. A mudança será aplicada somente na nova VPS Contabo permanente, após restore e API/UAT disponíveis; não haverá SQL direto no banco restaurado.
