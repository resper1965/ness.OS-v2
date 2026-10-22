# ness.OS

Monorepo da plataforma operacional ness.: Zabbix para monitoração, GLPI para
ativos e atendimento, Authentik para identidade, Psono para segredos e Hub para
incidentes e visões por perfil. Node-RED, Wazuh e Google Workspace integram o
programa conforme seus próprios gates. A presença de código ou configuração
não significa que a capacidade esteja liberada em produção.

O estado factual e datado está em [docs/execution/ness-os-status.md](docs/execution/ness-os-status.md).
O escopo, a sequência e os critérios de aceite estão no
[plano master](docs/superpowers/plans/2026-10-12-ness-os-plano-master.md).
Para assumir o desenvolvimento, comece pelo
[handoff de 22/10/2026](docs/execution/developer-handoff-2026-10-22.md).

## Organização

- `app/backend/`: API, workers, integrações e testes Python.
- `app/frontend/`: interface React/PWA e verificações de build/lint.
- `app/docker-compose*.yml`: stack candidata; não equivale ao runtime produtivo.
- `infra/`: automação, scripts, configuração, recuperação e runbooks.
- `docs/`: arquitetura, decisões, evidências e planos. Comece pelo indicador acima.
- `.github/`: workflows e configuração do repositório; o estado efetivo dos
  checks e da proteção da `main` deve ser conferido no GitHub.

## Fluxo pretendido

Zabbix → incidente no Hub → ativo/ticket no GLPI → atendimento e solução.
Authentik autentica; o backend valida papel e tenant; Psono guarda segredos.
Automação privilegiada requer aprovação e evidência. O canário interno é uma
primeira onda, não o fim da entrega para os clientes existentes.

## Antes de executar

Leia o [indicador](docs/execution/ness-os-status.md), o
[contexto do projeto](docs/PROJECT_CONTEXT.md) e o
[estado do gate de release](docs/execution/gate-0-status.md).
Não use este README como autorização para provisionar, subir a stack,
reativar contas técnicas ou cortar coleta. Promoções exigem identidade,
janela, evidência e rollback conforme o plano master.

Para desenvolvimento, veja [CONTRIBUTING.md](CONTRIBUTING.md) e os exemplos
de ambiente de cada componente. Nunca versionar valores de `.env`, chaves,
tokens, dumps ou saídas de testes com dados reais.

## Licença

Consulte as licenças dos componentes de terceiros; a marca ness. não altera
seus avisos ou obrigações.
