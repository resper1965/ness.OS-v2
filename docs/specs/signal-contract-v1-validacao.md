# Validação do contrato de sinal v1 por consumidor independente (P1)

Consumidor escrito só a partir de [`signal-contract-v1.md`](signal-contract-v1.md), do
[esquema](signal-contract-v1.schema.json) e dos [exemplos](examples/signal-v1/). Sem ler o Hub, o v0 nem o
teste do autor. Código: `infra/tests/signal_v1_consumer.py`; prova: `infra/tests/test-signal-contract-v1-consumer.py`.

## Implementado sem ambiguidade

- Envelope: obrigatórios, tipos, padrões de `source_id`/`signal_type`, `schema_version` `1.N`, `quality`, `links` opcional.
- Instantes RFC 3339 com fuso (`Z`/`+hh:mm`); rejeita sem fuso, `+0300`, data só, `+03`. Ordem fora do esperado: aceita com aviso.
- Compatibilidade: v1.0 aceita 1.1 com campo extra e o ignora; major 2.0 rejeitada.
- Lote OT: `batch` obrigatório em `ot.batch` e proibido nos demais; `interval` com `start` < `end`; digest sha256 do JCS (RFC 8785) do `payload`, conferindo com o exemplo oficial.
- Sem `tenant_id` resolvido: `null` → pendente (`PENDING_TENANT_REVIEW`), nunca `default`.

## Ambiguidades e lacunas

1. **Onde o `tenant_id` da origem é tratado (bloqueante).** Tabela: "Nunca aceito do payload nem da origem" e obrigatório;
   esquema: "Valor enviado pela origem é ignorado"; os exemplos oficiais (`wazuh-alert`, `cloud-event`) trazem `tenant_id`
   preenchido, e o contrato não diz se eles são o envelope **da origem** ou o **registro interno** pós-Hub. Não está dito
   se envelope de origem com `tenant_id` é rejeitado ou ignorado, nem se a origem deve enviar o campo (obrigatório) e
   `received_at` (obrigatório, "valor da origem é ignorado"). Comportamento exigido, lido do texto: o valor da origem nunca é
   usado; o Hub grava o que resolve. O teste adota *ignorar e substituir* (não rejeitar). Falta um contrato separado de
   "envelope de entrada" × "registro armazenado".
2. **`severity_source.value` ausente.** Texto: "Valor ausente, `null` ou fora da escala não é rebaixado nem descartado".
   Esquema: `value` é `required`. Chave ausente é aceita (texto) ou rejeitada (esquema)? O consumidor rejeita (segue o esquema).
3. **Digest JCS fora de "inteiros/strings".** O contrato não limita o `payload` a inteiros e strings. Não diz o que fazer com
   float (JCS usa a serialização numérica ES6), inteiro > 2^53−1 (não representável em JCS), chave duplicada ou string com
   surrogate isolado; nem que "payload intacto" (bytes) e digest (valor parseado) são coisas diferentes. O consumidor sinaliza
   rejeição para float/inteiro grande: decisão minha, não do contrato.
4. **`event_count`**: contagem de quê? O contrato não define o formato do `payload` de `ot.batch`; o exemplo usa `payload.events`.
   `event_count` não é verificável por um consumidor genérico.
5. **`occurred_at`/`collected_at` do lote = início/fim do intervalo.** Descrito, mas sem dizer se divergência é erro. O consumidor só avisa.
6. **Relógio desajustado "fica visível".** Não há campo, flag ou `quality` definido para registrar a diferença; só `delayed` existe e não é associado.
7. **Idempotência.** (a) Chave inclui `tenant_id`, mas sinal pendente tem `tenant_id = null`: quando o vínculo chega a chave muda
   (duplica)? (b) "lote: `batch_id`" — substitui o `event_id` ou se soma? (c) Mesma chave com `payload` diferente: devolve a
   decisão salva ou é conflito?
8. **Evolução de enums.** Regra 6 permite campo novo opcional em minor, mas não diz se minor pode ampliar `quality` ou a escala
   de valor; um v1.0 rejeitaria `quality: "stale"` de um 1.1. O mesmo para `algorithm` (só `sha256`).
9. **Escopo das regras de instante.** Aplicam-se só aos campos do envelope e a `batch.interval`; o `payload` do exemplo Wazuh
   tem `timestamp` com `-0300` (sem dois-pontos) e deve ser aceito por ser "intacto". Dito implicitamente, não explicitamente.
10. **Regras só no esquema, não no texto:** chaves de `extensions` `^[a-z][a-z0-9_]*$` e valores objeto; `source_id` até 128
    caracteres e charset; `signal_type` com ao menos um ponto; `event_count` inteiro ≥ 0; deslocamento `+hh:mm` fora de 00–23:59
    e segundo 60 (leap second) não tratados; `schema_version` aceita `1.01`. Resolução do vínculo para nuvem/OT está "aberta"
    (Aberto), então o consumidor só injeta um resolvedor.

## Veredito: NÃO VALIDADO

Falta: resolver o item 1 (separar envelope de entrada × registro interno, e dizer se `tenant_id`/`received_at` vindos
da origem são rejeitados ou ignorados) e o item 2 (`value` ausente: texto × esquema). Os itens 3, 4, 7 e 8 devem
ser fechados antes de existir produtor/consumidor de lote OT ou deduplicação. Os demais são menores. Todo o resto do
contrato (4 exemplos, instantes, compatibilidade, lote, `links`) foi implementado e provado sem consulta ao autor.
