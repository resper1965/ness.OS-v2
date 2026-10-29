# Contrato de sinal v0 (rascunho)

**Estado:** proposta para validação com os consumidores. Nomes finais ainda abertos
(spec v2, §5). Nada aqui autoriza ativação em produção.

Vale para Wazuh, nuvem/SaaS e OT. Entrada de evento só muda depois deste contrato.

## Sinal

| Campo | Regra |
|---|---|
| `source_id` | Identificador estável da origem (agente, integração ou sonda). Chave do vínculo de cliente. |
| `tenant_id` | **Resolvido pelo Hub** a partir do vínculo administrativo de `source_id`. Nunca aceito do payload. |
| `type`, `schema_version` | Tipo do sinal e versão do contrato. |
| `event` | Evento original, intacto (evidência). |
| `occurred_at`, `collected_at`, `received_at` | Três horários; o último é do Hub. |
| `quality` | Completo, parcial ou atrasado. Sinal degradado não é descartado. |
| `source_severity` | Severidade de origem, sem reinterpretação (ex.: nível Wazuh). |
| `links` | Ativo, serviço, cluster: opcionais; ausência não descarta o sinal. |

Lote (OT): acrescenta `batch_id` estável, `rules_version`, intervalo coberto e integridade.

## Regras

1. **Cliente antes de enriquecimento.** Sem vínculo, ou com vínculos para clientes
   diferentes, o sinal fica `PENDING_TENANT_REVIEW`: persistido, sem enriquecimento
   externo, sem IA, sem tenant `default`. Grupo, label, nome e IP recebidos são chave de
   busca, não autorização.
2. **Fonte do vínculo:** `n_infraops_tenant_mappings` (`external_platform`,
   `external_customer_id` → `internal_customer_id`); para Wazuh, `external_platform='wazuh'`.
   A tabela existe em produção com 0 linhas e nenhum fluxo a lê hoje: o vínculo precisa
   ser cadastrado antes de qualquer alerta ser atendido.
3. **Atendimento independe do score e do modelo.** A política SOC decide quais sinais
   exigem atendimento. Provisório: severidade de origem ≥ 12
   (`NINF_SOC_ATTENDANCE_MIN_LEVEL`), a substituir pela política aprovada. Abaixo do piso,
   o score continua decidindo, como antes. Falha da IA não bloqueia o despacho.
4. **Idempotência:** chave inclui `tenant_id`, `source_id` e identificador do evento.
   Replay não repete ticket, notificação nem ação concluída. (Ainda não implementada
   para `/secops/triage`.)

## Aberto

Nomes finais; política SOC de atendimento; duração da janela, banda, capacidade e
retenção OT (spec v2, §12).
