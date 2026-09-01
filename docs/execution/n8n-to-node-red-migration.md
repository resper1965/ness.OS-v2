# Migração controlada de n8n para Node-RED

## Motivo

O n8n em uso é fair-code sob Sustainable Use License e não atende à política OSI aprovada. O escopo observado é pequeno: quatro workflows, três ativos, uma credencial e nenhum histórico de execução retido. Node-RED foi selecionado como primeiro candidato por usar Apache-2.0 e cobrir webhook, HTTP, código, e-mail e agendamento sem introduzir outra edição híbrida.

## Regras

- Não instalar diretamente na produção.
- Não exportar credenciais descriptografadas para Git ou documentação.
- Não executar n8n e Node-RED simultaneamente contra o mesmo endpoint com efeitos reais.
- Cada fluxo migrado terá owner, entrada, saída, timeout, retry, idempotency key, DLQ ou tratamento equivalente, log e rollback.
- O editor Node-RED não será público: acesso por Authentik/Caddy, MFA administrativo e rede restrita.
- `projects`/Git será habilitado; `flows_cred.json`, chaves e tokens ficarão fora do repositório e serão migrados para SOPS/age.

## Etapas

1. Gerar backup consistente do volume n8n e hash do SQLite.
2. Exportar workflows sem segredos e inventariar triggers, URLs, métodos, schemas, credenciais referenciadas, efeitos externos e SLAs.
3. Classificar cada fluxo: webhook síncrono, cron, integração de e-mail ou orquestração interna.
4. Criar ambiente Node-RED em staging com versão e digest fixos, usuário não-root, filesystem somente leitura onde possível, limites de CPU/RAM e healthcheck.
5. Implementar subflows comuns para autenticação, correlação, retry exponencial, timeout, log estruturado e resposta de erro.
6. Recriar cada fluxo com fixtures anonimizadas e testes de contrato.
7. Executar modo sombra somente para operações sem efeito; para operações mutáveis, usar mocks ou sandbox do provedor.
8. Comparar resultado, latência, número de chamadas, retries e comportamento em falha.
9. Fazer cutover de um fluxo por vez, mantendo n8n parado mas restaurável. Monitorar por 48 horas.
10. Após sete dias sem regressão, remover exposição e credenciais do n8n; manter backup criptografado durante o prazo de rollback aprovado.

## Matriz obrigatória por workflow

| Campo | Registro exigido |
|---|---|
| Identificador e owner | nome estável, finalidade e responsável |
| Trigger | webhook/cron/manual, autenticação e frequência |
| Contrato de entrada | schema, tamanho máximo, dados sensíveis e validação |
| Efeitos | APIs, e-mail, ticket, banco e possibilidade de duplicação |
| Idempotência | chave, duração e reação à repetição |
| Falhas | timeout, retries, backoff, limite e destino final |
| Observabilidade | correlation ID, métrica, log e alerta acionável |
| Segredos | referência SOPS/age/Passbolt; nunca valor no flow |
| Aceite | fixture, saída esperada, latência e teste negativo |
| Rollback | como reativar o n8n sem duplicar eventos |

## Critérios de saída

- Quatro workflows inventariados e versionados sem segredos.
- Três fluxos ativos reproduzidos e aprovados por testes de contrato e falha.
- Nenhum endpoint recebe processamento duplicado durante o cutover.
- Logs permitem rastrear uma execução ponta a ponta por correlation ID.
- Backup e restauração do Node-RED foram testados em host vazio.
- n8n foi desligado, removido da borda e permaneceu recuperável pelo prazo acordado.
