# Zabbix — coleta e classificação do piloto Cavan — 02/09/2026

## Estado observado

- `zabbix-server` ativo e habilitado;
- 18 de 18 proxies com comunicação inferior a cinco minutos;
- ações e tipos de mídia permanecem desabilitados para conter notificações;
- fila de coleta oscilando, com 260 itens persistentemente atrasados há mais de
  dez minutos;
- itens não suportados concentrados em hosts de link que executam coleta
  completa de FortiGate por SNMP;
- os 252 hosts habilitados estavam sem tags de classificação.

## Diagnóstico SNMP

Os caminhos AmericaNet do Cavan e TBE e os dois caminhos Algar da Alupar
retornam `only partial data received` durante o item mestre `net.if.walk`.
Desativar requisições SNMP em lote reduziu os erros por poucos ciclos no Cavan
e no TBE, mas a falha retornou na verificação prolongada. Nos FortiGate 200E da
Alupar, reduzir `max_repetitions` também não produziu melhora sustentada.

Todos os ajustes experimentais foram revertidos. As interfaces `116`, `117`,
`221` e `265` estão novamente no estado original: `bulk=1` e
`max_repetitions=10`.

O mecanismo provável é estrutural: os hosts nomeados como links consultam a
tabela completa do firewall através de cada WAN. No Cavan, os dois hosts de
link retornam o mesmo serial físico `FGT40FTK2209EVPQ`. A correção definitiva
deve separar monitoramento de conectividade por link da coleta completa do
appliance, preferencialmente por um host único do firewall acessado pelo proxy
local. Essa remodelagem exige confirmar o endereço interno do firewall antes
da mudança.

O switch Cavan `SW01-SP-Core` também está ligado ao template incompatível
`FortiGate by HTTP`. O template não foi alterado porque fabricante e modelo
ainda não foram comprovados.

## Classificação aplicada

Os 14 hosts do piloto Cavan — Matriz receberam tags normalizadas:

- `tenant=cavan`;
- `site=matriz-sp`;
- `environment=production`;
- `scope=customer`;
- `owner=ricardo-esper`;
- `role` conforme a função do ativo;
- `technology` somente quando comprovada pelo template ou pelo próprio ativo.

Não foi atribuída criticidade por inferência. A mudança de tags não altera a
coleta e não habilita alertas.

## Evidências e rollback

- piloto SNMP Cavan:
  `/var/lib/ness-os/restore-evidence/cavan-americanet-snmp-20260902T162609-0300`;
- onda SNMP e rollback final:
  `/var/lib/ness-os/restore-evidence/snmp-partial-data-wave-20260902T162838-0300`;
- teste Alupar e rollback:
  `/var/lib/ness-os/restore-evidence/alupar-snmp-maxrep-20260902T163109-0300`;
- tags do piloto:
  `/var/lib/ness-os/restore-evidence/cavan-host-tags-20260902T163339-0300`.

Os arquivos remotos estão restritos a root. O diretório de tags contém o
payload de rollback para restaurar exatamente as tags anteriores.

## Expansão da monitoração interna

Em continuidade, foi informado que o FortiGate Cavan — Matriz usa o endereço
LAN `172.29.0.254` e que o `SW01-SP-Core` é Aruba. Foi executada apenas a fase
de expansão da migração:

1. criado o host `10977`, `[ Cavan ] [ Matriz ] [ Firewall ]
   FGT40F-CAVAN-SP`, com template `FortiGate by SNMP`, endereço
   `172.29.0.254` e monitoramento pelo proxy Cavan `spcavprx` (`proxyid=4`);
2. preservados sem alteração os dois hosts WAN e seus históricos;
3. migrado o switch `10888` do template incompatível `FortiGate by HTTP` para
   `Network Generic Device by SNMP`, também pelo proxy Cavan;
4. adicionada ao switch a tag `technology=aruba-snmp`;
5. não aplicado o template específico `Aruba CX 8300s by SNMP`, pois o modelo
   ainda não foi coletado.

Nenhuma contração foi executada: os WANs não foram convertidos para ICMP e o
template Aruba específico não foi aplicado.

Evidências adicionais:

- criação do firewall LAN:
  `/var/lib/ness-os/restore-evidence/cavan-firewall-lan-expand-20260902T163933-0300`;
- migração do Aruba para SNMP genérico:
  `/var/lib/ness-os/restore-evidence/cavan-aruba-generic-migrate-20260902T164329-0300`.

## Reconciliação dos proxies Cavan

O campo `lastaccess` mostrava `spcavprx` e `stacavprx` online, mas os dois
proxies continuavam usando a configuração da instância anterior. O diagnóstico
em nível de protocolo comprovou que enviavam IDs de itens que não pertenciam à
base restaurada. O servidor rejeitou esses IDs; amostras verificadas não foram
gravadas em hosts de outros clientes.

Uma atualização de configuração simples não resolveu porque o banco local do
proxy manteve os itens antigos. Foi aplicada uma limpeza reversível em duas
etapas:

1. mover temporariamente os hosts para um proxy de retenção;
2. enviar uma configuração integral vazia e confirmar que cessaram os IDs
   antigos;
3. recolocar os hosts no proxy original;
4. aguardar a convergência do cache central e enviar nova configuração integral;
5. confirmar no protocolo e no histórico que somente os IDs atuais passaram a
   ser coletados.

Resultado:

- `spcavprx`: 13 de 13 hosts com histórico atual, entre 11 e 56 segundos na
  amostra final;
- `stacavprx`: 4 de 4 hosts com histórico atual, entre 18 e 69 segundos na
  amostra final;
- o objeto temporário de retenção de São Paulo foi excluído sem hosts;
- o objeto anterior de Santa Lúcia foi mantido offline, renomeado, como rollback
  até encerrar a janela de estabilização.

Evidências:

- `/var/lib/ness-os/restore-evidence/stacav-proxy-full-resync-20260902T171343`;
- `/var/lib/ness-os/restore-evidence/stacav-empty-config-test-20260902T172056`;
- `/var/lib/ness-os/restore-evidence/spcav-empty-config-flush-20260902T172446`.

## Estado do Aruba e do FortiGate interno

O `Check now` confirmou que os dois hosts respondem a ICMP e atualizam
histórico, mas as consultas SNMP básicas expiram no proxy:

- Aruba `172.29.0.110`: timeout em `sysObjectID.0` na UDP/161;
- FortiGate `172.29.0.254`: timeout em `sysObjectID.0` na UDP/161.

Portanto, a sincronização do Zabbix está resolvida, mas SNMP ainda depende de
habilitação, ACL e comunidade permitidas na LAN de cada equipamento. Sem
`sysDescr` confiável, o modelo Aruba continua intencionalmente não inferido.

No host do switch, 31 itens FortiGate órfãos já haviam sido desativados. Foram
também desativadas as cinco regras de descoberta órfãs; seus 44 protótipos
permanecem inertes e o histórico foi preservado. Evidências:

- `/var/lib/ness-os/restore-evidence/cavan-aruba-disable-orphans-20260902T165524-0300`;
- `/var/lib/ness-os/restore-evidence/cavan-aruba-disable-orphan-lld-20260902T173353`.

## Saúde do servidor, fila e alerta sintético

Após a reconciliação:

- `zabbix-server` permaneceu ativo e habilitado;
- a fila de pré-processamento permaneceu em `0`;
- a fila acima de dez minutos caiu de `260` para `163` itens;
- a fila total observada foi `868` itens;
- os maiores consumidores eram trapper (`40,7%`) e ICMP pinger (`39,9%`),
  sem saturação de histórico, banco ou pré-processamento.

Os atrasos restantes foram separados por causa. Eles se concentram em hosts
com interface realmente indisponível, principalmente agentes sem rota e
FortiGate WAN consultados integralmente por SNMP. Esses ativos não foram
desativados por inferência; a redução adicional da fila depende de validar
descomissionamento, rota ou remodelar os hosts WAN como testes de link.

O pipeline de eventos foi validado com um objeto reutilizável e isolado:

- host `uat-synthetic-alerts` (`hostid=10978`);
- item trapper `uat.synthetic.alert` (`itemid=116992`), restrito ao envio local;
- trigger `UAT: alerta sintético ativo` (`triggerid=50519`);
- evento PROBLEM `50642790` seguido da recuperação `50642791`;
- zero ações e zero tipos de mídia habilitados durante todo o teste;
- nenhum problema sintético permaneceu aberto.

Evidência:
`/var/lib/ness-os/restore-evidence/zabbix-synthetic-alert-local-20260902T173835`.
