# Cavan — rechecagem de monitoração em 08/09/2026

Leitura de produção por relatório SQL existente e API Zabbix, aproximadamente
18:39–18:40 BRT. Nenhum host, item, template ou histórico foi alterado.

## Inventário atual

O relatório `infra/scripts/zabbix-cavan-inventory-report.sh` encontrou **19** hosts
com `tenant=cavan` e `site=matriz-sp`. O escopo histórico de 14 não descreve mais
todo o conjunto: existem o firewall interno 10977 e quatro hosts GCP 10979–10982.
Os quatro GCP têm `site=matriz-sp`; a associação física/lógica merece conferência,
sem mover ativos ou inferir nova localização por nome.

Todos os 19 apresentam owner, role, environment, scope, tenant e site. A saída
não contém tag de criticidade. O inventário de localização é majoritariamente
limitado à cidade São Paulo; isso não prova localização física completa.
O host 10877 está desativado. Os proxies spcavprx e stacavprx reportaram acesso
atual às 18:39:04/05.

## Coleta observada

| Host | Evidência |
| --- | --- |
| 10977, FortiGate interno 172.29.0.254 | Interface SNMP disponível; 331 itens habilitados, 321 com valor e 271 atualizados em 15 minutos. Identidade FortiGate-40F v7.4.9, nome FGT40F-Cavan-SP.cavan.local. |
| 10873, AmericaNet | 331 itens habilitados, 321 com valor; identificação do mesmo FortiGate. |
| 10874, Vivo | 331 itens habilitados, 321 com valor; identificação do mesmo FortiGate. |
| 10888, Aruba 172.29.0.110 | 12 itens habilitados; apenas quatro com atualização. ICMP ping=0, perda=100%; disponibilidade SNMP=0 (desconhecida). sysDescr/sysObjectID/system.name sem coleta. |

Os números de itens recentes variam com seus intervalos; itens de 15 minutos ou
mais não devem ser classificados como atrasados apenas por esse recorte.

O firewall interno passou a coletar desde a evidência de timeout de 02/09. O
Aruba continua sem identificação; agora também apresenta perda ICMP total na
amostra atual. Modelo e template específico permanecem não comprovados. Os
antigos itens FortiGate no switch estão desativados; seus erros históricos não
foram contados como erros de itens ativos.

Nos três hosts FortiGate há um item ativo não suportado por divisão por zero
no cálculo com `vfs.fs.total[fgSysDiskCapacity.0]`. A divisão deve ser tratada
conforme a capacidade real do equipamento, sem inventar uma medida de disco.

## Pendências concretas

1. Resolver conectividade/ACL/SNMP do Aruba pelo proxy e obter sysObjectID/sysDescr.
2. Validar a capacidade de armazenamento do FortiGate e corrigir o item calculado.
3. Concluir a separação do firewall canônico e dos testes de links: AmericaNet e
   Vivo ainda mantêm centenas de itens do equipamento completo.
4. Completar criticidade e localização a partir do baseline de serviços e fontes
   autorizadas; preservar o inventário novo em vez de voltar ao número antigo.
5. Reavaliar fila, triggers, mapa e disponibilidade após as correções.

A rechecagem não encerra F1 nem autoriza inferir o modelo Aruba pelo nome.

## Correção de armazenamento preparada, ainda não aplicada

A API confirmou capacidade e uso iguais a zero nos três hosts. O percentual
livre nunca recebeu valor e está não suportado por divisão por zero. Há duas
triggers habilitadas dependentes desse percentual em cada host.

| Host | Item percentual | Triggers dependentes |
| --- | --- | --- |
| 10873 AmericaNet | 97468 | 39192, 39193 |
| 10874 Vivo | 97845 | 39307, 39308 |
| 10977 interno | 115583 | 49797, 49798 |

Correção prevista: revalidar capacidade zero e identidade do equipamento,
guardar o estado antes da mudança e desativar somente esses três percentuais
e seis triggers por API. Manter capacidade/uso brutos e todo o histórico.
Percentual de capacidade zero é indefinido; não substituir por 0% ou 100%.
Rollback: restaurar os status anteriores (todos eram 0/habilitado nesta leitura).

O token administrativo de bootstrap foi recusado com `Not authorized` em
requisição TLS validada para o endpoint local. A credencial do hub permanece
operacional para leitura/reconhecimento. Solicitado ao responsável um token
administrativo válido em arquivo protegido; nenhum segredo foi solicitado no
chat e nenhuma alteração foi aplicada por acesso direto ao banco.
