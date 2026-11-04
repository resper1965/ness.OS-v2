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
- Com o contrato corrigido (2ª rodada): entrada com `tenant_id` preenchido rejeitada; `severity_source.value` ausente/`null` aceito; chave de idempotência sem tenant; payload `ot.batch` fora de inteiros/strings rejeitado; enums fechados; `v1.0` aceita `1.1` e rejeita `2.0`.

## Ambiguidades e resolução

Primeira rodada: NÃO VALIDADO, 10 ambiguidades. Resolvidas no contrato (decisões do Ricardo; **envelope inalterado**, sem campo novo):

1. **`tenant_id` (era bloqueante).** Resolvido: contrato separa *envelope de entrada* × *registro armazenado* (mesmo esquema; raiz = armazenado, `#/$defs/input` = entrada). Na entrada, `tenant_id` é `null` ou ausente; valor preenchido é **rejeitado** com erro (campo, valor, `source_id`/`event_id`) — não é mais "ignorado". O Hub preenche o registro armazenado após resolver o vínculo; `received_at` da origem é substituído. Exemplos: sem sufixo = entrada (`tenant_id: null`), `-stored` = registro.
2. **`severity_source.value` ausente.** Resolvido: esquema alinhado ao texto — só `scheme` é obrigatório; `value` pode faltar ou ser `null`. Atende pela regra 7 da política SOC.
3. **Digest/JCS.** Resolvido: em `ot.batch`, payload com float, inteiro fora de ±(2^53−1), chave duplicada ou surrogate isolado é rejeitado; o digest só cobre inteiros e strings (e estruturas/bool/null).
4. **`event_count` e formato do payload de `ot.batch`.** **Lacuna aberta**, declarada no contrato: depende do piloto de OT, que não existe. Não inventado; o consumidor só valida `event_count` como inteiro ≥ 0.
5. **`occurred_at`/`collected_at` do lote vs intervalo.** Mantido como aviso, não erro (sem mudança de decisão; o contrato já descreve o significado e não pede rejeição).
6. **Relógio desajustado.** Resolvido: derivado de `received_at − collected_at` no registro armazenado; sem campo novo (`clock_skew` no consumidor).
7. **Idempotência.** Resolvido: chave `(source_id, event_id)`; lote `(source_id, batch_id)` (substitui `event_id`); `tenant_id` fora da chave, então o vínculo tardio não duplica. Mesma chave + payload diferente = conflito registrado, sem sobrescrever (`Store` no consumidor).
8. **Evolução de enums.** Resolvido: minor não amplia enum (`quality`, `algorithm`); ampliar = major. v1.0 rejeita `quality: "stale"` de um 1.1 por contrato.
9. **Instantes no payload.** Resolvido: isentos explicitamente; o envelope não valida instantes dentro do `payload`.
10. **Regras só no esquema** (charset de `source_id`, `signal_type` com ponto, chaves de `extensions`, `+hh:mm` 00–23:59, `schema_version` `1.01`). Menores, sem mudança de decisão; o esquema é a referência. O esquema agora aceita só `1.0`, `1.1`, … sem zero à esquerda.

## Ainda aberto

- Formato do `payload` e significado de `event_count` em `ot.batch` (piloto de OT).
- Chaves de `external_platform` para nuvem e OT (já listado em *Aberto* do contrato).

## Veredito: VALIDADO

O consumidor, escrito sem consulta ao autor e lendo só contrato, esquema e exemplos, passa nos documentos corrigidos
(`python3 infra/tests/test-signal-contract-v1-consumer.py`, 13 testes) e o teste do autor também
(`python3 infra/tests/test-signal-contract-v1.py`, 10 testes). Casos novos: `tenant_id` preenchido na entrada rejeitado,
`value` ausente/`null` aceito, mesma chave com payload diferente = conflito, instantes sem fuso rejeitados, `v1.0`
aceita `1.1` e rejeita `2.0`. A validação cobre o envelope; o payload de `ot.batch` segue como lacuna aberta e não
bloqueia o contrato de envelope, mas bloqueia ativar produtor/consumidor de lote OT.
