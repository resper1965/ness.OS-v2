# Hub / GLPI — implantação de 08/09/2026

**Estado consolidado:** [plano executado e evidências finais](hub-glpi-work-plan-2026-09-08.md).
Inclui correção PKCE implantada, prova positiva OIDC, publicação após commit,
auditoria de 260 tickets, 255 ativos e 226 testes aprovados.

Atualização posterior: os itens 2 a 5 foram executados, com solução oficial,
deduplicação do reconhecimento, verificações de acesso, monitoramento contínuo
e 254 ativos reconciliados. Resultados e exceções em
[hub-glpi-followthrough-2026-09-08.md](hub-glpi-followthrough-2026-09-08.md).
As limitações abaixo descrevem o estado da implantação inicial.

## Escopo e situação

Por orientação do responsável, a expansão do fluxo Zabbix → hub → GLPI foi
executada diretamente, sem condicionar a operação a uma fase separada de piloto.
A validação técnica acompanhou a implantação. Isso não equivale à conclusão das
demais ondas de identidade, inventário, SecOps, recuperação ou polimento.

- Origem: Zabbix 7.0.27, `144.91.72.202`; hub: `144.91.115.242`.
- GLPI 11.0.8, API e workers operacionais; portal público retornando HTTP 200.
- Cobertura verificada: 257 hosts ativos, 256 mapeados. Host 10962 (`esper`,
  grupo `casa`) excluído da ação por não possuir cliente definido.
- Expansão para as 11 entidades de clientes e a entidade interna Ness.
- WhatsApp, push e notificações globais GLPI permanecem desativados.
- A ação recebe novos eventos; problemas históricos não foram reenviados em massa.

## Alterações implantadas

- Webhooks autenticados, configuração ausente recusada e requisição sem chave
  comprovadamente retornando HTTP 401. Segredo não incluído neste documento.
- Caddy encaminha `/v1/*` à API. Workers registram e consomem ingestão e resolução.
- Identidade de incidente inclui host, trigger e evento Zabbix. Reentrega do mesmo
  evento não deve abrir outro chamado; novo problema possui identidade distinta.
- Exclusão concorrente Redis com token de proprietário; busca no GLPI pelo
  marcador persistente antes de criar; falhas permitem retry após salvar incidente.
- Cliente resolvido pelos grupos autorizados do host; mapeamento exato de
  entidade; ambiguidade e cliente desconhecido recusados.
- Serviço GLPI 94, perfil 12: vínculos 103–113 não recursivos nas entidades 1–11.
  Direito de acompanhamento alterado de 8193 para 8197, permitindo adicionar
  acompanhamentos aos próprios tickets. Criação informa solicitante 94.
- Acompanhamentos ausentes dos tickets 2–8 reparados; tickets de clientes mantidos
  abertos. Novos tickets apresentam solicitante e acompanhamento automaticamente.
- Zabbix: mídia 72, ação 7 e usuário 35. Perfil 5 preserva métodos de leitura e
  acrescenta `event.acknowledge`, com reconhecer/adicionar comentário autorizados.
- Webhook GLPI 1 utiliza `https://hub.ness.com.br/webhook/glpi`, autenticação por
  cabeçalho e status numérico `item.status.id`. Fila nativa executada pelo cron GLPI.
- Resolução salva o incidente antes de reconhecer o evento original; falha no
  reconhecimento aciona retry. Não força a recuperação de falhas ainda presentes.
- Portal recebe fingerprint, cliente, ticket e estágio reais; exibe link ao GLPI e
  resolução, sem afirmar que notificação ou post-mortem foram realizados.
- Timeout do analisador reduzido; chave Gemini em cabeçalho, sem chave em URL.

## Evidências

- Evento Zabbix **53615770**, entrega **621030075**: ação 7, sucesso sem retry de
  entrega; incidente hub **22**, ticket GLPI **1** na entidade interna.
- Ticket 1 solucionado → webhook GLPI → hub resolvido → evento original
  reconhecido por usuário 35, ação 6 (reconhecimento e comentário).
- Trapper interno restaurado a zero. Evento de recuperação **53621739** confirmado.
- Tickets reais subsequentes em Alupar, Target, TBE e Alupar CO observados.
  Tickets 29–32 vinculados a incidentes com contador 1; listagem do portal fornece
  fingerprint, cliente correto e estágio `ticket_opened`.
- Inspeção final: 35 tickets criados pelo serviço, nenhum marcador duplicado e
  nenhum acompanhamento ausente. Entrega do webhook GLPI 1: HTTP 200.
- Backend: **189 testes aprovados**. Build local e build remoto do frontend
  aprovados; imagem atualizada e container recriado. API/worker saudáveis e dois
  nós Celery respondendo às inspeções de filas.
- Typecheck global do frontend permanece com erros preexistentes em outros
  componentes; build Vite aprovado não equivale à aprovação desse typecheck.
- Validação da listagem executada no backend instalado. Jornada gráfica completa
  com sessões humanas de diferentes clientes não foi repetida nesta implantação.

## Limitações observadas

- Gemini respondeu HTTP 429 `RESOURCE_EXHAUSTED`, cota gratuita de 20 requisições
  para `gemini-2.5-flash`. Tickets continuam com fallback de análise manual. Não
  foi ativado faturamento nem trocado de conta/modelo para contornar a cota.
- Deduplicação combina lock temporário e marcador persistente; não é uma promessa
  de entrega exatamente uma vez em toda falha possível. Callbacks repetidos de
  resolução podem repetir o comentário de reconhecimento no Zabbix.
- Webhook de resolução envia solução vazia; não comprova enriquecimento automático
  do post-mortem com o texto da solução humana.
- A publicação SSE de abertura ocorre dentro da transação existente; a consulta
  persistida é a referência de estado. Notificações externas seguem desligadas.

## Recuperação e rollback

Backup protegido: `/opt/n-infraops/rollback/hub-complete-20260908/`.
Contém `before.tar` (backend, ambiente, Caddy e compose anteriores), cópia do
ambiente da integração GLPI, logs e fonte anterior de `IncidentsPage.tsx`.
Imagem anterior do frontend: `ness-frontend:rollback-20260908`.
Perfil Zabbix anterior: `/var/lib/ness-os/hub-rollout/role-before.json`.

Para interromper novas entregas, desativar ação Zabbix 7 e webhook GLPI 1 pelas
interfaces/APIs nativas. Preservar tickets e eventos como registros de auditoria.
Restaurar os arquivos necessários do backup e recriar somente os serviços
afetados; restaurar a imagem anterior do frontend se necessário. Validar Caddy
antes de recarregar; restauração que substitua inode de bind mount exige recriar
o container para carregar o arquivo restaurado.

Se houver rollback de permissões, restaurar perfil Zabbix salvo e remover somente
a mídia adicionada ao usuário; no GLPI, reverter direito 8197 para 8193 e os vínculos
103–113 após avaliar os tickets já criados. Não remover acessos preexistentes.

O SSH recuperado e a rota específica para o Zabbix são independentes desse rollback.
A rota persistida é `/etc/netplan/60-ness-zabbix-route.yaml`; não foi executado
`netplan apply` nem alterada a autenticação SSH nesta implantação.
