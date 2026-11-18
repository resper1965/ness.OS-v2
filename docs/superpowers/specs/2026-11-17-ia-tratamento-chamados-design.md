# IA no tratamento de chamados — design

> Data: 17/11/2026. Estado: **aprovado pelo Ricardo em 17/11/2026**.
> **F1 entregue na branch `feat/ia-chamados-f1`** (commits `37d13ae` a `44450bc`; fecha com `docs: fecha F1 da IA nos chamados`). PR: a abrir. Falta promover (aviso à operação em [ai-f1-aviso-operacao.md](../../execution/ai-f1-aviso-operacao.md) e OK do Ricardo).
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

## 4. O caminho único

```
fonte ─► adaptador ─► sinal v1 ─► cliente ─► dedup + correlação ─► atendimento (regra)
                                                                         │
                        GLPI ◄── chamado ◄── enriquecimento (IA) ◄──────┘
                                     │
                proposta de ação (IA) ─► aprovação humana ─► executor (Action1 etc.)
                                     │
                      encerramento ─► retorno do analista ─► métricas
```

**[proposta]** Toda fonte entra como **sinal v1** (`docs/specs/signal-contract-v1.md`). O Zabbix passa a
emitir o envelope internamente (`signal_type = zabbix.problem`), sem mudar o webhook nem o comportamento
de hoje. Assim correlação, IA e métricas são escritas uma vez só.

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
| Dedup e correlação | N0 para agrupar, N1 para explicar | Resume o grupo ("50 eventos, 3 hosts, mesmo switch"). | Regra determinística é auditável e resolve a maior parte da tempestade. |
| Atendimento e urgência | N1 | Marca **divergência** quando a leitura do modelo discorda da regra. Vai para revisão; não muda nada. | Regra 2. A divergência calibra a regra (entrega E1 do plano Vigil). |
| Enriquecimento do chamado | N1 | Resumo, causa provável, próximos passos e chamados parecidos do **mesmo cliente** (pgvector). Tudo marcado como IA. | Ganho direto de tempo do analista. Já existe no NOC. |
| Investigação L2 (SOC) | N1 | Linha do tempo e hipóteses (Vigil, se o ADR 0022 passar). | Só casos graves; custo controlado. |
| Proposta de ação | N3 | Propõe ação de uma **lista fechada** por executor. O analista aprova; o executor roda; o resultado volta ao chamado. | Regra 4. |
| Encerramento | N2 | Rascunho da solução e do texto ao cliente; quem fecha é o humano. O fechamento automático continua **só** pela recuperação da origem (ex.: recovery do Zabbix), sem IA. | Fechar errado esconde problema. |
| Atendimento ao técnico no GLPI | N2 | Plugin `nessai`, como está. | Já existe. |

## 6. Correlação **[proposta]**

É o maior ganho e não usa IA.

- Um **grupo** junta sinais do mesmo cliente dentro de uma janela de tempo, quando uma destas condições bate:
  - mesmo host;
  - hosts ligados pela mesma dependência cadastrada (no GLPI ou no Zabbix);
  - mesma regra ou trigger em vários hosts.
- **O grupo abre um chamado só.** Os sinais seguintes entram como acompanhamento do mesmo chamado.
- Janela e critérios ficam por cliente, em tabela editável, no padrão de contratos e SLA (#198).
- Sinal de severidade maior que a do grupo **sobe a urgência** do chamado e notifica de novo. Nunca é
  engolido em silêncio.
- **Nunca agrupa entre clientes diferentes.**
- **Fechamento automático do grupo:** só quando **todos** os sinais do grupo se recuperam na origem. Antes
  disso, cada recuperação vira acompanhamento. **[proposta — o mais seguro contra "fechar escondendo problema"]**
- **Critério de dependência:** entra na F2 só se o dado já estiver cadastrado, com fonte única no GLPI
  (cadastro mestre). Sem dado, a F2 começa com "mesmo host" e "mesma regra em vários hosts". **[proposta]**

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

## 9. Fonte nova (ferramenta de cliente) **[proposta]**

Integrar uma fonte é:

1. Escrever o **adaptador**:
   - por **push**, com webhook e chave por fonte;
   - ou por **pull**, com coleta agendada.
2. Fazer o adaptador emitir sinal v1.
3. Cadastrar o vínculo `source_id` → cliente em `n_infraops_tenant_mappings`.
4. Cadastrar o esquema de severidade da fonte e a regra de atendimento dela.
5. Montar a lista de campos permitidos para a IA.

**Nada muda no núcleo.** O adaptador é um arquivo em `integrations/`, no padrão dos que já existem.
Quando chegar o terceiro adaptador de push parecido, avaliar um adaptador genérico configurável (rule of
three).

## 10. Fases

Cada fase vale sozinha e tem gate de promoção normal do Hub.

| Fase | Entrega | Pronto quando |
|---|---|---|
| F1 | Registro de decisão de IA + retorno do analista + métricas, começando pelo Zabbix (inclui a E1 do plano Vigil). | Toda análise do NOC está no banco; a tela mostra as métricas da seção 7 com dado real. |
| F2 | O Zabbix emite sinal v1 internamente e entra a correlação. | A tempestade de teste vira um chamado; sinais ÷ chamados medidos. |
| F3 | O Wazuh entra pelo mesmo caminho até o GLPI, com chave de máquina. | Um alerta real do tenant `ness` gera chamado com enriquecimento e decisão registrada. |
| F4 | `remediators/*` do Hub aposentado (ADR 0021: o Hub não executa). Action1 em **leitura**: patch e vulnerabilidade viram sinais. A IA propõe uma ação da lista fechada; a execução N3 fica atrás da aprovação. | Homologação do ADR 0021, itens 1 a 3; uma ação aprovada roda e o resultado volta ao chamado. |
| F5 | Primeira ferramenta de cliente pela seção 9. | Integrada sem mudar o núcleo. |
| F6 | Investigação L2, se o ADR 0022 for aceito. | Conforme o plano Vigil (E2 e E3). |

Ordem: F1 vem antes de tudo, porque sem medição não dá para dizer se o resto ajuda.

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
  - N4.
- **Anti-objetivos.** Mesmo que funcione, é fracasso se:
  - a IA silenciar ou rebaixar um alerta;
  - dado de um cliente aparecer no chamado ou no prompt de outro;
  - um chamado esperar pela IA;
  - o custo crescer sem teto;
  - o analista deixar de ler porque "a IA já viu".

## 12. Fica com quem constrói

- Esquema das tabelas de decisão de IA e de grupo, e se o `SocDecision` é estendido ou generalizado.
- Valores iniciais de janela e critérios de correlação; lista fechada de ações do Action1.
- Formato do botão de retorno no GLPI: plugin `nessai` ou link para o Hub.
- Versão de prompt como arquivo versionado ou como tabela.
