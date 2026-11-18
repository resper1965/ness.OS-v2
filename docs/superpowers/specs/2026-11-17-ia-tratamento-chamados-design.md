# IA no tratamento de chamados — design

> Data: 17/11/2026. Estado: **aprovado pelo Ricardo em 17/11/2026**.
> **F1 na `main` (#280).** Falta promover (aviso à operação em [ai-f1-aviso-operacao.md](../../execution/ai-f1-aviso-operacao.md) e OK do Ricardo). F2 na branch feat/ia-chamados-f2; PR: a abrir.
> **Revisado em 18/11/2026 [Ricardo]:** laço único NOC/SOC no lugar de SOAR/AIOps de regra; correlação por regra substituída por repetição + sugestão do investigador; Action1 como contexto, sinal e braço; inventário do GLPI como eixo.
> Base: `origin/main` em 17/11. Não autoriza instalação, compra nem ativação em produção.
> Marcação: **[Ricardo]** = decidido por ele (aqui ou em ADR/spec citada); **[proposta]** = decisão do autor, revisável.

## 1. Intenção

Hoje só o Zabbix gera chamado, e cada fonte nova tende a ganhar um caminho próprio. Depois vêm Wazuh,
Action1 e as ferramentas que os clientes trouxerem. Sem desenho único, cada uma vira uma integração com
regras e uso de IA diferentes, e ninguém sabe se a IA ajuda.

Objetivo: **um caminho só, do alerta ao chamado no GLPI, para qualquer fonte**. A IA entra onde poupa
trabalho do analista, sempre com medição, e nunca decide o que pode causar dano.

## 2. Estado atual (resumo)

| Fonte | Hoje | IA hoje |
|---|---|---|
| Zabbix | Webhook → `/v1/alerts` → `process_alert_v1` → GLPI. Um chamado por evento (`host:trigger:event_id`). Cliente pelo hostgroup. | `ml/analyzer.py` (Gemini 2.5 Flash via OpenRouter): texto de causa e ação no corpo do chamado; pode só **subir** a urgência da notificação. Decisão não fica no banco. |
| Wazuh | `/api/secops/triage` pronto, sem tráfego de produção, sem caminho até o GLPI. | `soc_agent.py` classifica; o atendimento é por regra (política SOC). `SocDecision` persiste. |
| Action1 | Só ADR 0021 e teste de leitura. | — |
| Ferramenta de cliente | — | — |
| GLPI | Plugin `nessai`: resumir, sugerir e traduzir quando o técnico pede. | Log em `glpi_plugin_nessai_logs`. |

Lacunas: sem correlação (uma tempestade de 50 eventos vira 50 chamados), sem medida de acerto da IA,
decisão da IA no NOC fora do banco, contrato de sinal v1 sem produtor e embedding do post-mortem fora do
contrato `AIRequestV1`.

## 3. Regras que não mudam

Já decididas em ADR ou spec, e valem para toda fonte nova:

1. **O cliente vem antes da IA.** Sinal sem vínculo ou com vínculo ambíguo não passa pela IA nem por
   enriquecimento externo (contrato de sinal v1, regra 1). **[Ricardo]**
2. **O atendimento e a urgência independem do modelo.** Quem decide é regra determinística: a severidade
   da origem e a política SOC. **[Ricardo]**
3. **Falha da IA nunca segura o chamado.** **[Ricardo]**
4. **Toda ação corretiva tem aprovação humana, registrada no Hub.** O Hub não é RMM: a execução fica no
   Action1 (ADR 0021). **[Ricardo]**
5. **O GLPI é o registro do atendimento.** O Hub é a entrada e a fonte de verdade do caso (ADR 0002 e
   ADR 0022). **[Ricardo]**
6. **Toda chamada à IA passa por `AIRequestV1`:** campos explícitos, sanitização e métrica. **[Ricardo, #99]**

## 4. O laço único (NOC e SOC) **[Ricardo, 18/11]**

O SOAR de playbook (SOC) e o AIOps de regra fixa e runbook (NOC) estão vencidos. O fluxo pré-escrito não cobre
o caso real e a manutenção não acaba. No lugar entra **um laço só para NOC e SOC**: um investigador (IA) que
lê o contexto, propõe a ação, o humano aprova e o executor roda.

```
fonte ─► adaptador ─► sinal v1 ─► cliente (regra) ─► dedup/repetição (regra) ─► atendimento e urgência (regra)
                                                                                     │
          GLPI ◄── chamado ◄── investigador (IA, ferramentas de leitura) ◄───────────┘
                     │
                     ├─► proposta de ação ─► aprovação humana ─► executor (Action1) ─► verificação ─► chamado
                     └─► encerramento ─► retorno do analista ─► métricas (F1)
```

**Fica determinístico** (controle, não automação): cliente, atendimento, urgência, dedup por evento e
repetição de sinal de estado, lista de ações proibidas, aprovação humana, teto de custo e registro de toda
decisão (F1).

**Vira trabalho do investigador (N1/N2), não regra:** dizer que alertas são o mesmo incidente, linha do tempo,
causa provável com o histórico do mesmo cliente e proposta de ação.

### 4.1 Perfil por fonte

O laço é um só; cada fonte declara um perfil. Tratar o Wazuh como um "Zabbix com outro nome" quebra o desenho.

| | Zabbix (NOC) | Wazuh (SOC) | Action1 (endpoint) |
|---|---|---|---|
| Tipo de sinal | **estado** (abre e se recupera) | **evento** (não se recupera) | **pendência** (patch, vulnerabilidade, reboot, agente sem contato) |
| Filtro antes do chamado | quase tudo vira chamado | política SOC (arquiva, atende por nível/score, amostra semanal) | agregado por cliente e por ciclo, nunca um chamado por máquina |
| Repetição | o mesmo trigger no mesmo host = o mesmo problema (acompanhamento) | a mesma regra no mesmo agente = possível ataque em curso (sinal, nunca silenciado) | a mesma pendência = a mesma linha do ciclo |
| Encerramento | recuperação na origem | veredito humano (FP/verdadeiro) | **verificação** depois da execução ("instalado" ≠ "corrigido", ADR 0021) |
| Acerto da IA | categoria ITIL no GLPI | veredito FP no Hub | verificação pós-execução |
| Dado ao modelo | trigger, métrica | `full_log` sanitizado (usuário, IP, comando) | inventário; **a chave do BitLocker nunca sai do Action1** |
| Ferramentas do investigador | histórico do Zabbix, chamados do cliente | eventos relacionados, reputação, MITRE | — (o Action1 é ferramenta dos outros) |

### 4.2 Papéis das integrações

| Integração | Papel no laço |
|---|---|
| Zabbix, Wazuh | **olhos**: fontes de sinal |
| Action1 | **contexto** (leitura do endpoint para o investigador), **sinal** (pendências) e **braço** (executor do que foi aprovado), nessa ordem de entrada |
| GLPI | **registro** do atendimento e **inventário** (cadastro mestre, ADR 0002): é a ferramenta de contexto comum a todas as fontes |
| Hub | o laço: cliente, regra, investigador, aprovação, registro e medição |

O ganho de juntar tudo no Hub é o caso cruzado no mesmo cliente e no mesmo host (ex.: o Zabbix acusa disco
caindo enquanto o Wazuh vê um processo cifrando arquivos e o Action1 mostra um software instalado ontem). Só o Hub vê os três.

## 5. Onde a IA entra, etapa por etapa

O nível de autonomia de cada etapa é fixo:

- **N0:** sem IA.
- **N1:** anota (texto ao lado; nada muda).
- **N2:** sugere (o humano aceita com um clique).
- **N3:** executa depois de aprovação humana.
- **N4:** executa sozinha.

**N4 está fora deste design.**

| Etapa | Nível máximo | O que a IA faz | Por quê |
|---|---|---|---|
| Adaptador / normalização | N0 em produção | Pode ajudar a *escrever* o mapeamento de uma ferramenta nova, em desenvolvimento, com revisão. | Mapeamento errado em tempo real é invisível. |
| Resolução de cliente | N0 | — | Regra 1. |
| Dedup e repetição | N0 | — | Identidade do sinal, não juízo. |
| Agrupamento de incidentes | N2 | Sugere "estes chamados são o mesmo incidente"; o técnico vincula no GLPI. | Agrupar errado esconde problema; sugestão errada custa um clique. |
| Atendimento e urgência | N1 | Marca **divergência** quando a leitura do modelo discorda da regra (F1). | Regra 2. |
| Investigação (NOC e SOC) | N1 | Linha do tempo, causa provável, chamados parecidos do **mesmo cliente**, com ferramentas de leitura (Zabbix, Wazuh, inventário do GLPI, Action1). | Substitui o playbook. Custo controlado pelo teto da F1. |
| Proposta de ação | N3 | Propõe a ação; o analista aprova; o executor roda; a verificação volta ao chamado. O controle é uma **lista de ações proibidas** por executor, não uma lista fechada de playbooks. | Regra 4. |
| Encerramento | N2 | Rascunho da solução e do texto ao cliente; quem fecha é o humano. O fechamento automático continua **só** pela recuperação da origem, sem IA. | Fechar errado esconde problema. |
| Atendimento ao técnico no GLPI | N2 | Plugin `nessai`, como está. | Já existe. |

## 6. Repetição e agrupamento **[Ricardo, 18/11]**

A correlação por regra fixa (mesmo host ou mesmo trigger numa janela) **sai do design**. Ela juntaria
problemas distintos do mesmo servidor e esconderia o segundo quando o técnico fechasse o primeiro, e refaz o que
o Zabbix 7.0 já faz na origem (dependência entre triggers, correlação global).

- **Repetição (N0, só sinal de estado):** um problema novo do **mesmo trigger no mesmo host**, com o chamado
  anterior ainda aberto, vira acompanhamento desse chamado (flapping). Severidade maior sobe a urgência e
  notifica de novo. Nunca entre clientes.
  **Na F2:** a repetição comenta e notifica pela regra da F1 (severidade da origem); subir a urgência do chamado raiz fica para a F3 [proposta].
- **Supressão na origem:** a dependência entre triggers fica configurada no Zabbix, não no Hub.
- **Agrupamento entre problemas distintos:** sugestão do investigador (N2), vinculada pelo técnico no GLPI.
- **Primeiro medir:** a F2 mede quantos chamados por cliente e por host caem em janelas curtas, a partir do
  histórico. Sem tempestade medida, nada além da repetição é construído.

## 7. Registro e medição **[proposta]**

Toda saída de IA vira uma linha de **decisão de IA**, no banco, ligada ao sinal, ao grupo e ao chamado.
A linha guarda:

- etapa e nível;
- modelo e versão do prompt;
- entrada já sanitizada (ou o hash dela) e resposta;
- custo e latência;
- retorno do analista.

O `SocDecision` atual vira um caso disso, ou é estendido; a escolha fica com quem constrói.

**Retorno do analista:** um clique no Hub ou no GLPI ("útil", "errado" ou "não li"). Ao encerrar, a
classificação final do humano é comparada com a da IA: **categoria ITIL do chamado no GLPI** e, no SOC, o
veredito FP/verdadeiro registrado no Hub. **[proposta]**

**Métricas** (tela no Hub, por cliente e por fonte):

| Métrica | Para quê |
|---|---|
| Sinais ÷ chamados | Ganho da correlação |
| Taxa de divergência regra × IA | Calibração |
| Taxa de "útil" e de acerto de classificação | A IA ajuda? |
| Tempo até a primeira resposta e até a solução, com e sem sugestão aceita | Ganho real |
| Custo de IA por chamado e por cliente | Teto |
| Falha ou timeout da IA | Saúde |

**Gate de subida de nível:** uma etapa só sobe de nível (por exemplo, encerramento de N2 para N3) com
métrica medida por 30 dias e OK do Ricardo.

## 8. Dados de cliente e IA

- **O que pode ir ao modelo externo:** lista de campos por fonte, no `AIRequestV1`, sem segredo. O
  payload bruto só vai quando a etapa precisa dele (ex.: `full_log` do Wazuh), e passa pela
  sanitização.
- **Por cliente:** uma opção "IA externa permitida", ligada por padrão. Para o cliente que não permite,
  a etapa de IA é pulada e o chamado segue normal. **[Ricardo, 17/11]**
- **Teto de custo:** global. Ao atingir o teto, a etapa de IA é pulada, o chamado segue normal e o Ricardo
  recebe um alerta. O valor inicial é o limite atual da chave (US$ 50/mês). **[Ricardo, 17/11]**
- **Urgência no NOC:** a F1 tira do `ml/analyzer.py` o poder de subir a urgência da notificação. A
  discordância vira só registro de divergência. Avisar a operação antes da promoção. **[Ricardo, 17/11]**
- **Ferramenta de cliente:** o dado do cliente só é usado no tenant dele. Ao contratar, o cliente
  declara se a ferramenta pode ir à IA externa.
- **O que fica fora:**
  - o modelo local (Ollama) entra só se um cliente exigir; o `AIRequestV1` já permite trocar o
    provedor;
  - o embedding do post-mortem passa a usar o `AIRequestV1`.

## 9. Fonte nova e inventário **[proposta]**

Integrar uma fonte é:

1. Escrever o **adaptador** (push com webhook e chave por fonte, ou pull agendado) que emite sinal v1.
2. Cadastrar o vínculo `source_id` → cliente em `n_infraops_tenant_mappings`.
3. Declarar o **perfil** (seção 4.1): tipo de sinal, filtro, repetição, encerramento, campos permitidos à IA.
4. Dizer se ela também é **ferramenta de contexto** (leitura para o investigador) ou **executor**.

**Nada muda no núcleo.** O adaptador é um arquivo em `integrations/`. No terceiro adaptador de push parecido,
avaliar um adaptador genérico (rule of three).

**Inventário do GLPI como eixo:** toda fonte se liga ao mesmo ativo do GLPI (cadastro mestre). Hoje só o
Zabbix tem esse elo (`Asset.zabbix_host_id` ↔ item do GLPI, `cmdb_sync`). Wazuh (agent) e Action1 (endpoint)
precisam do mesmo elo, sem casar por IP compartilhado. Explorar integrações do inventário (dono, contrato,
dependências, software) fica para depois da F3, em spec própria. **[Ricardo, 18/11]**

## 10. Fases

Cada fase vale sozinha e tem gate de promoção normal do Hub.

| Fase | Entrega | Pronto quando |
|---|---|---|
| F1 | Registro de decisão de IA, retorno do analista e métricas (inclui a E1 do plano Vigil). **Entregue (#280).** | Toda análise do NOC está no banco; a tela mostra as métricas. |
| F2 | Repetição do mesmo trigger no mesmo host vira acompanhamento; medição de tempestade (sinais ÷ chamados e consulta histórica). | Repetição testada; relatório de tempestade com dado real. |
| F3 | Investigador N1 para o NOC, com ferramentas de leitura (Zabbix, chamados e inventário do GLPI). Avaliado pela F1. O Vigil (ADR 0022) concorre a esta peça. | Metade das análises marcada como útil em 30 dias, sem dado cruzado entre clientes. |
| F4 | Sinal v1 como entrada comum (Zabbix e Wazuh; o tipo de sinal define o perfil). Wazuh no mesmo laço até o GLPI, com a triagem da política SOC na frente do chamado; o investigador ganha as ferramentas do SOC. | Um alerta real do tenant `ness` gera chamado com investigação e decisão registrada. |
| F5 | Action1: contexto → sinais de pendência → executor N3 com lista de ações proibidas. `remediators/*` aposentado. | Homologação do ADR 0021 (itens 1 a 3, credencial só de leitura, licença acima de 200 aprovada); uma ação aprovada roda e a verificação volta ao chamado. |
| F6 | Primeira ferramenta de cliente pela seção 9. Inventário do GLPI como eixo comum (spec própria). | Integrada sem mudar o núcleo. |

Ordem: medir (F1) → repetição (F2) → investigar (F3, F4) → agir (F5).

## 11. Objetivos, não-objetivos e anti-objetivos

- **Objetivos:**
  - um caminho para toda fonte;
  - menos chamados por incidente;
  - analista com contexto pronto;
  - IA medida.
- **Não-objetivos:**
  - o Hub como RMM ou SIEM;
  - novo provedor de IA;
  - cliente acessando a IA;
  - IA decidindo cliente, atendimento, urgência ou fechamento;
  - playbook pré-escrito (SOAR) ou correlação por regra fixa;
  - N4.
- **Anti-objetivos.** Mesmo que funcione, é fracasso se:
  - a IA silenciar ou rebaixar um alerta;
  - dado de um cliente aparecer no chamado ou no prompt de outro;
  - um chamado esperar pela IA;
  - o custo crescer sem teto;
  - o analista deixar de ler porque "a IA já viu".

## 12. Fica com quem constrói

- Esquema das tabelas de decisão de IA e de grupo, e se o `SocDecision` é estendido ou generalizado.
- Lista de ações proibidas por executor; ferramentas do investigador por fonte.
- Formato do botão de retorno no GLPI: plugin `nessai` ou link para o Hub.
- Versão de prompt como arquivo versionado ou como tabela.
