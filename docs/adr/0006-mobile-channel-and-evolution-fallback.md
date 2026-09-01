# ADR 0006 — Canal mobile técnico e Evolution como fallback

- Status: aceita
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

Evolution/WhatsApp não foi aprovado como canal operacional primário. Técnicos SOC/NOC precisam receber e tratar incidentes em dispositivos móveis. O frontend existente já possui fundamentos de PWA e Web Push.

## Decisão

A experiência mobile do produto será o canal técnico primário. A primeira entrega será uma PWA instalável para Android e iOS, voltada majoritariamente a BYOD e sem exigência inicial de app stores. Evolution permanecerá como fallback somente de saída.

## Consequências

- O fluxo técnico não pode depender do WhatsApp para reconhecimento ou aprovação.
- Push, autenticação, revogação de sessão/dispositivo e jornadas críticas precisam ser testados em Android e iOS.
- Notificações e caches não podem armazenar detalhes sensíveis; o usuário autentica para consultar o incidente.
- Ações de alto impacto exigem aprovação em duas etapas, allowlist, auditoria e rollback.
- Aplicativo nativo só será considerado após medir limitações e adoção da PWA.
