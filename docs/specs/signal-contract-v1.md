# Contrato de sinal v1

**Estado:** proposta para validação com os consumidores (P1). Substitui o [v0](signal-contract-v0.md).
Nada aqui autoriza ativação em produção, conector, sonda ou ingestão.
**Esquema:** [`signal-contract-v1.schema.json`](signal-contract-v1.schema.json) (JSON Schema 2020-12).
**Exemplos sintéticos:** [`examples/signal-v1/`](examples/signal-v1/). Nunca dado real. Sem sufixo = documento de
**entrada**; `-stored` = **registro armazenado**.

Vale para Wazuh, nuvem/SaaS e OT. Entrada de evento só muda depois deste contrato.

## Envelope

O envelope é fechado: `source_id`, `tenant_id`, `signal_type`, `occurred_at`, `collected_at`, `received_at`,
`severity_source`, `payload` (mais `schema_version` e os opcionais abaixo). Dois usos do **mesmo** esquema, com regra
diferente só em `tenant_id`:

| | Envelope de **entrada** (origem → Hub) | Registro **armazenado** (depois do Hub) |
|---|---|---|
| `tenant_id` | `null` ou ausente. Valor preenchido é **rejeitado** com erro explícito (campo, valor e `source_id`/`event_id`). | Obrigatório: texto (vínculo resolvido) ou `null` (pendente). Preenchido só pelo Hub. |
| `received_at` | Valor da origem é ignorado. | Atribuído pelo Hub. |
| Esquema | `#/$defs/input` | raiz do esquema |

Obrigatório = presente em todo sinal. Opcional = pode faltar sem impedir o registro.

| Campo | Obrig. | Tipo | Regra |
|---|---|---|---|
| `schema_version` | sim | texto `1.N` | Versão do contrato. Minor só acrescenta campos opcionais. |
| `source_id` | sim | texto | Identificador **estável e único** da integração (agente, manager, sonda). Chave do vínculo de cliente. Nunca reutilizado para outra origem. |
| `tenant_id` | entrada: `null`/ausente; armazenado: sim | texto ou `null` | **Resolvido pelo Hub** a partir do vínculo administrativo. Nunca aceito do payload nem da origem (entrada com valor é rejeitada). `null` = pendente de vínculo. |
| `signal_type` | sim | texto | Tipo, com prefixo da origem: `wazuh.alert`, `cloud.event`, `ot.batch`. |
| `occurred_at` | sim | instante | Horário do fato na origem. |
| `collected_at` | sim | instante | Horário em que a coleta leu o fato. |
| `received_at` | sim | instante | Horário de recepção no Hub. Atribuído pelo Hub; o valor da origem é ignorado. |
| `severity_source` | sim | `{scheme, value}` | Severidade declarada pela origem, sem reinterpretação. `scheme` é obrigatório; `value` aceita número, texto, `null` ou pode faltar. |
| `payload` | sim | objeto | Evento original, intacto (evidência). |
| `links` | não | `{asset, service, cluster}` | Cada chave é opcional. Ausência não descarta o sinal. |
| `event_id` | não | texto | Id do evento na origem; entra na chave de idempotência (regra 4). Sem ele não há deduplicação. |
| `quality` | não | `complete` \| `partial` \| `delayed` | Sinal degradado não é descartado. Enum fechado na v1 (regra 6). |
| `batch` | só em `ot.batch` | objeto | Obrigatório em `ot.batch`; proibido em qualquer outro `signal_type`. Ver abaixo. |
| `extensions` | não | objeto | Extensão por origem, ver regra 5. |

### Instantes

`occurred_at`, `collected_at` e `received_at` são três instantes distintos, em RFC 3339 **com fuso
explícito** (`Z` ou `+hh:mm`). Instante sem fuso é inválido. A ordem esperada é
`occurred_at` ≤ `collected_at` ≤ `received_at`, mas relógio desajustado de origem não é motivo de
rejeição: o sinal é aceito. O desajuste é **derivado** de `received_at − collected_at` no registro armazenado;
não existe campo nem flag para isso. Nunca copie um instante sobre outro.

A regra vale só para os campos do envelope e `batch.interval`. Instantes **dentro do `payload`** (ex.: o `timestamp`
Wazuh com `-0300`) não são validados pelo envelope: estão isentos, o payload é evidência intacta.

### Severidade

`severity_source` carrega o que a origem disse, com o esquema que dá sentido ao valor
(ex.: `wazuh.level`). O contrato **não** define piso, tabela de equivalência entre origens nem
nível de atendimento. Valor ausente (chave `value` omitida), `null` ou fora da escala não é rebaixado nem
descartado: o sinal é atendido pela regra 7 da [política SOC](soc-attendance-policy.md).

### Lote OT (`signal_type = ot.batch`)

`batch` é obrigatório (e só existe) neste tipo e traz:

| Campo | Regra |
|---|---|
| `batch_id` | Estável e único por lote. Reenvio do mesmo lote repete o mesmo `batch_id`. |
| `rules_version` | Versão das regras OT aplicadas na coleta. |
| `interval` | `{start, end}`: intervalo coberto, instantes com fuso, `start` < `end`. |
| `integrity` | `{algorithm: "sha256", digest, event_count?}`. `digest` = sha256 (hex minúsculo) dos bytes UTF-8 da forma canônica do `payload` segundo a [RFC 8785 (JCS)](https://www.rfc-editor.org/rfc/rfc8785). Produtor e consumidor usam JCS, não a serialização padrão da linguagem. `event_count`: ver Aberto. |

**Payload de `ot.batch`:** o digest só cobre inteiros e strings (mais objetos, listas, booleanos e `null`).
Payload com **float**, inteiro fora de ±(2^53−1), **chave duplicada** (no JSON de entrada) ou **surrogate isolado**
em string/chave é **rejeitado** em `ot.batch`. Em outros `signal_type` o payload segue intacto, sem esta restrição
(não há digest). O digest cobre o valor parseado, não os bytes recebidos.

`occurred_at` do lote é o início do intervalo coberto; `collected_at`, o fechamento do lote na sonda.
O atraso até `received_at` é esperado (transmissão em janelas) e não é erro.

## Regras

1. **Cliente antes de enriquecimento.** Sem vínculo, ou com vínculos para clientes diferentes, o
   sinal fica `PENDING_TENANT_REVIEW` (`tenant_id = null`): persistido, sem enriquecimento externo,
   sem IA, sem tenant `default`. Grupo, label, nome de host e IP recebidos são chave de busca, não
   autorização.
2. **Fonte do vínculo:** `n_infraops_tenant_mappings` (`external_platform`, `external_customer_id`
   → `internal_customer_id`); para Wazuh, `external_platform='wazuh'`, hoje por grupo do agente.
   O vínculo de nuvem e OT usa o `source_id`; as chaves de `external_platform` para essas origens
   ficam abertas.
3. **Atendimento independe do score e do modelo.** A [política SOC](soc-attendance-policy.md)
   decide; o contrato só transporta `severity_source`. Severidade ausente ou inválida não é
   rebaixada: o sinal é atendido. Falha da IA não bloqueia o despacho.
4. **Idempotência:** a chave é `(source_id, event_id)`; em `ot.batch`, `(source_id, batch_id)` (o `batch_id`
   substitui o `event_id`). `tenant_id` **não** faz parte da chave: assim o sinal pendente não duplica quando o vínculo
   chega. Mesma chave + mesmo `payload`: replay, não repete ticket, notificação nem ação concluída e devolve a decisão
   salva. Mesma chave + `payload` diferente: **conflito registrado**, o salvo não é sobrescrito. Em `/secops/triage`
   (Wazuh) a chave é sha256 de tenant + `manager.name` + `id` do alerta, ou agente + regra +
   `timestamp`; sem `id` nem `timestamp`, sem chave e sem deduplicação.
5. **Extensão por origem:** campos próprios de uma origem vão em `extensions.<origem>` (ex.:
   `extensions.wazuh`). Extensão nunca muda o significado de campo do envelope nem é exigida por
   consumidor genérico.
6. **Evolução:** campo novo entra como **opcional** e não quebra consumidor da versão anterior.
   Remover, renomear, tornar obrigatório, mudar o significado de campo ou **ampliar um enum** (`quality`,
   `integrity.algorithm`) exige nova major (`v2`): minor não amplia enum, um v1.0 rejeitaria o valor novo.

## Compatibilidade

- O esquema não usa `additionalProperties: false` no envelope: consumidor v1.0 aceita documento
  v1.N sem erro e ignora o que não conhece (exceto enums fechados, regra 6).
- `schema_version` aceita `1.N`; uma major diferente é rejeitada com erro explícito.
- Diferenças em relação ao v0: `type` → `signal_type`; `event` → `payload`;
  `source_severity` → `severity_source` (agora `{scheme, value}`); `quality` passa a opcional;
  campos de lote ficam em `batch`; `event_id` e `extensions` são novos e opcionais.
  Nenhum produtor existe ainda fora de `/secops/triage`, que hoje recebe o alerta Wazuh cru e
  **não** emite este envelope: o mapeamento do alerta para o envelope é trabalho futuro (P2).

## Verificação

`python3 infra/tests/test-signal-contract-v1.py` valida os exemplos (campos obrigatórios, instantes
com fuso, lote e digest) sem dependência externa. O esquema também valida com qualquer
implementação de JSON Schema 2020-12. O consumidor independente
(`infra/tests/test-signal-contract-v1-consumer.py`) prova o contrato só pelo texto, esquema e exemplos;
resultado em [signal-contract-v1-validacao.md](signal-contract-v1-validacao.md).

## Aberto

Dependem do Ricardo; nada foi preenchido por suposição:

- Prazos de resposta por nível (SLA, T08).
- OT: duração da janela, banda, capacidade e retenção (spec v2, §12).
- Quem revisa a amostra semanal de arquivados, e quando.
- Piso de severidade para origens além do Wazuh (o piso 12 vale só para nível Wazuh).
- Formato do `payload` de `ot.batch` e o significado de `integrity.event_count` (o que se conta): dependem do
  piloto de OT, que ainda não existe. Sem isso, `event_count` não é verificável por consumidor genérico.
- Nomes finais dos campos e chaves de vínculo de `external_platform` para nuvem e OT.
