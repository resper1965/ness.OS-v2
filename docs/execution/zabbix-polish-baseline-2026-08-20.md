# Baseline de polimento operacional do Zabbix

> Data: 20/08/2026
> Estado: baseline somente leitura concluída; mudanças funcionais pendentes de janela e validação por lote

## Resumo mensurável

| Dimensão | Estado observado | Alvo inicial |
|---|---:|---:|
| Hosts monitorados | 311 | inventário e owner definidos para 100% |
| Templates | 362 | versionados, com owner e sem duplicidade material |
| Itens ativos | 60.110 | cobertura acordada por classe de ativo |
| Itens ativos não suportados | 1.393 (2,32%) | menos de 0,5% |
| Triggers ativos desconhecidos | 634 | nenhum por mais de 24 h sem exceção |
| Hosts sem inventário | 60 | zero no escopo gerenciado |
| Inventário manual | 247 | negócio via GLPI; técnico automático quando coletável |
| Inventário automático | 4 | expandir por template sem sobrescrever GLPI |
| Hosts sem nenhuma tag | 274 | zero após migração gradual |
| Mapas de rede | 1 mapa / 1 elemento | mapas úteis por cliente/site |
| Dashboards globais | 4 | por função e cliente, sem duplicidade |

## Inventário e localização

- 245 hosts possuem latitude/longitude e todos os pares analisados estão em faixa válida.
- Existem 24 pares distintos; 147 hosts compartilham um mesmo par, o que pode representar concentração em um site, mas requer reconciliação.
- Existem 247 hosts com cidade preenchida, distribuídos em 27 valores distintos.
- Campos técnicos estão quase vazios: apenas um nome de inventário e um sistema operacional; nenhum modelo ou serial principal preenchido.
- Contato aparece em 235 hosts, indicando cadastro parcial/manual.
- Há 1.518 itens ativos ligados a 25 campos de inventário, mas somente quatro hosts usam modo automático; essa divergência precisa ser revisada antes de ativação em massa.

### Dependência GLPI observada

O GLPI ainda não possui dados suficientes para alimentar o Zabbix como fonte canônica:

- uma localização cadastrada, com endereço e coordenadas;
- 12 entidades com endereço/cidade, mas sem latitude/longitude;
- 84 computadores e 155 equipamentos de rede ativos;
- nenhum desses 239 ativos ligado a localização, com serial preenchido ou inventário recebido;
- sete registros de agente, nenhum com contato nos últimos sete dias, vínculo a ativo ou módulo de inventário habilitado.

Consequentemente, não será feita sincronização GLPI → Zabbix ainda. A sequência correta é:

1. definir o cliente/site piloto;
2. normalizar entidades e localizações do piloto no GLPI;
3. instalar/ativar GLPI Agent nos ativos selecionados pelo RMM presente;
4. validar deduplicação, serial, UUID, última coleta e vínculo de localização;
5. geocodificar e homologar coordenadas;
6. somente então publicar inventário/tags/Geomap no Zabbix.

## Taxonomia

As tags-alvo `cliente`, `site`, `servico`, `ambiente`, `tecnologia`, `scope` e `owner` não existem nos hosts atuais. A hierarquia está codificada nos nomes dos grupos, por exemplo cliente → matriz/país → tecnologia/equipamento.

Não haverá renomeação em massa. A migração seguirá:

1. extrair cliente/site/tecnologia dos grupos atuais;
2. comparar com entidades/localizações do GLPI;
3. gerar proposta de tags por host;
4. homologar com amostra;
5. aplicar por cliente em lotes reversíveis;
6. manter grupos necessários a permissões e navegação.

## Qualidade da coleta

Distribuição inicial dos 1.393 itens não suportados:

| Classe | Quantidade |
|---|---:|
| Timeout | 404 |
| Chave/metric não suportada | 225 |
| Cálculo/expressão | 166 |
| Autenticação | 159 |
| Conectividade/DNS | 112 |
| Preprocessamento | 32 |
| Tipo de valor | 4 |
| Outros ainda a classificar | 173 |

Prioridade de correção:

1. templates/chaves não suportadas e cálculos, pois tendem a permitir correção única para muitos hosts;
2. autenticação, validando macros/credenciais sem expor valores;
3. timeouts por disponibilidade, intervalo e timeout adequado;
4. conectividade/DNS e, por fim, casos isolados.

## Mapas e dashboards

- Usar o GLPI como fonte canônica de ativo, cliente, site, endereço e coordenadas.
- Alimentar `location_lat`/`location_lon` no Zabbix por integração controlada.
- Criar Geomap executivo por cliente/site, filtrado por grupo/tag e severidade.
- Criar mapas de rede separados por cliente/site; não concentrar todos os 311 hosts em um único mapa.
- Manter dashboards distintos para NOC geral, cliente, disponibilidade, capacidade, proxies/coleta e qualidade da monitoração.
- Todo elemento deve apontar para host, problema, gráfico ou runbook útil; mapa decorativo não atende o Gate 4.1.

## Critério de avanço

O primeiro piloto deve conter um cliente e dois sites representativos, com GLPI reconciliado, agentes ativos, tags propostas, Geomap, um mapa lógico, dashboard operacional e redução comprovada de itens não suportados. Somente depois o modelo será replicado.

## Revalidação offline na KVM8 — 22/08/2026

A cópia restaurada permaneceu em quarentena durante a auditoria: `zabbix-server` inativo e mascarado, sem listener TCP/10051, MariaDB somente em `127.0.0.1:3306` e actions, media types e connectors ativos zerados. Os dados de runtime abaixo são snapshots do backup, não telemetria viva.

| Indicador | Cópia restaurada | Gate antes do corte |
|---|---:|---:|
| Itens ativos em hosts monitorados | 41.806 | — |
| Itens não suportados | 1.204 (2,88%) | menor que 0,5% ou exceção formal por onda |
| Triggers habilitadas `unknown` | 584 | redução comprovada e causas críticas tratadas |
| Escalations históricas vencidas | 1.829 | revisão das actions 3–6; nenhuma limpeza direta por SQL |
| Hosts monitorados sem template | 14 | validar `esper` e `vmware04`; confirmar os 12 APs descobertos |
| Hosts com coordenadas | 245/249 | homologar centróides e origem GLPI no piloto |
| Cobertura das tags-alvo | 0/249 | completar um cliente e dois sites no piloto |
| Mapas úteis | 1 mapa, 1 elemento | Geomap e mapa lógico separados |

O corte permanece **NO-GO**. A ordem de saneamento aprovada para laboratório é:

1. timeout/OID SNMP compartilhado do FortiGate Numen Matriz (344 ocorrências);
2. compatibilidade das chaves do template VMware Hypervisor;
3. parâmetros inválidos do template Windows e macros/credenciais vazias de VMware, HTTP e HPE;
4. cálculos resistentes a zero ou ausência de dados;
5. itens locais e descobertos remanescentes, sem desativação em massa.

Cada onda exige export/diff e rollback, redução mensurável de `unsupported` e `unknown` antigas e preservação do isolamento antes e depois da análise. Os 17 proxies só serão reconectados um por vez após registrar owner, cliente/site, endereço, TLS, allowlist e compatibilidade de versão.

## Baseline automatizada e ondas — 24/08/2026

Foi implantado na KVM8 o relatório somente leitura [`../../infra/scripts/zabbix-offline-polish-report.sh`](../../infra/scripts/zabbix-offline-polish-report.sh). Antes de consultar o banco, ele exige MariaDB ativo, `zabbix-server` inativo/mascarado e ausência do listener 10051. O relatório é gravado `0600 root:root` em `/var/lib/ness-os/restore-evidence/` e não inclui erros brutos, macros ou valores de segredos.

Evidência aprovada mais recente: `offline-polish-baseline-20260824T175248-0300.txt`.

| Indicador | Resultado |
|---|---:|
| Hosts monitorados | 311 |
| Templates | 362 |
| Itens ativos em hosts monitorados | 41.806 |
| Itens não suportados | 1.204 |
| Triggers habilitadas `unknown` | 584 |
| Escalations vencidas | 1.829 |
| Hosts sem template | 20 |
| Hosts sem tags | 274 |
| Hosts com coordenadas | 245 |
| Banco restaurado | 34.574.450.688 bytes |
| Actions/media/connectors ativos | 0/0/0 |

### Decomposição segura

| Origem/causa | Quantidade | Tratamento |
|---|---:|---|
| itens locais/descobertos — timeout | 342 | depende de conectividade/proxy real; não alterar no staging apenas para zerar estado histórico |
| Windows by Zabbix agent — outros | 284 | gerar assinaturas de erro root-only e revisar por item/template antes de propor mudança |
| VMware Hypervisor — outros | 150 | revisar compatibilidade de chaves/objetos; não assumir autenticação |
| VMware Hypervisor + VMware — autenticação | 126 | validar URL/macros pelo cofre; nunca copiar valores para evidência |
| FortiGate by SNMP — cálculos/divisão por zero | 58 | não alterar a fórmula: o template oficial 7.0 usa a mesma expressão; corrigir primeiro o modelo de ativos/coleta |
| HPE MSA HTTP — autenticação | 33 | owner/credencial e teste de API necessários |
| FortiGate by HTTP — preprocessamento | 32 | dois ativos `SW01-...-Core` usam somente o template FortiGate; validar classe/vendor e substituir o template, sem remendar 16 preprocessamentos |

### Ordem de execução

1. **Onda A — FortiGate:** os 58 itens pertencem a hosts de link WAN, com fabricante/modelo vazios, que representam 35 candidatos a appliances. Consolidar um host por firewall e interfaces por descoberta; depois separar equipamentos sem métrica de disco por template específico, sem fabricar valor quando o total for zero.
2. **Onda B — classificação de switches:** reconciliar no GLPI os dois ativos `SW01-...-Core`, confirmar fabricante/modelo e trocar o template FortiGate HTTP pelo template correto em piloto reversível.
3. **Onda C — VMware/HPE:** somente após Psono/SOPS-age, validar macros e credenciais sem exibição; separar autenticação de incompatibilidade de objeto/chave.
4. **Onda D — Windows:** 288 itens atingem 76 hosts; separar compatibilidade de item da disponibilidade do agente antes de qualquer alteração de template. Na cópia restaurada, 48 interfaces aparecem disponíveis, 13 indisponíveis e 15 sem estado; esses estados históricos exigem revalidação viva.
5. **Onda E — conectividade:** revalidar timeouts e itens locais/descobertos apenas no UAT com proxy/host de laboratório; estado histórico não autoriza desativação.

Nenhuma onda será aplicada por SQL direto. O mecanismo aceito é export/API/interface suportada, com diff, backup e rollback. O Zabbix Server permanece mascarado na KVM8.

### Decisão da Onda A — FortiGate

- O item afetado é `vfs.fs.pfree` (`itemid` de template 46220), com 58 heranças em estado não suportado.
- A fórmula restaurada é idêntica à do template oficial Zabbix 7.0; importar novamente o upstream não corrige o caso.
- Os 58 hosts têm nomes de links/provedores e inventário de fabricante/modelo vazio. A normalização por nome indica 35 appliances candidatos, incluindo 18 grupos com mais de um host de link.
- Retornar `100%`, `0%` ou outro valor sintético quando a capacidade total é zero foi rejeitado: isso transformaria ausência de métrica em dado operacional falso.
- A execução suportada será por export/API: promover um host canônico por appliance, descobrir as interfaces nesse host, provar paridade e manter os hosts legados apenas como rollback desabilitado. Onde o appliance realmente não expuser disco, usar template versionado sem a métrica e seu trigger.

O plano de mudança e os gates estão em [`zabbix-wave-a-fortigate-plan-2026-08-24.md`](zabbix-wave-a-fortigate-plan-2026-08-24.md).

### Decisão da Onda B — classificação/template

Os 32 erros de preprocessamento são 16 itens em cada um de apenas dois hosts: `Cavan Matriz SW01-SP-Core` e `Cavan Sta Lucia SW01-SL-Core`. Ambos possuem somente `FortiGate by HTTP` vinculado, apesar da nomenclatura de switch. A onda foi reclassificada de “corrigir JSONPath” para “confirmar o ativo e aplicar o template correto”. O plano está em [`zabbix-wave-b-switch-classification-plan-2026-08-24.md`](zabbix-wave-b-switch-classification-plan-2026-08-24.md).
