# GLPI — acompanhamento e runbooks operacionais — 08/09/2026

## Implantado

Criado o projeto interno
[ness.OS — implantação e continuidade operacional](https://n-ticket.ness.com.br/front/project.form.php?id=1)
(`Project` 1), na entidade Ness 0, sem recursão, responsável grupo infraops 13.
Possui oito tarefas: F1–F7 e revisão P, IDs 1–8. F6 e P estão novos; os demais
estão em andamento. Nenhum gate foi encerrado ou recebeu percentual estimado.
Os percentuais padrão permanecem sem apuração, conforme o texto do projeto.

Criados cinco artigos internos, sem FAQ pública e sem exposição no catálogo
de autoatendimento:

| ID | Runbook | Categoria |
| --- | --- | --- |
| 7 | operação do fluxo de incidentes | Monitoramento e observabilidade |
| 8 | falha de entrega e duplicidade | Monitoramento e observabilidade |
| 9 | reconciliação de ativos e empresas | Operação padrão MSP |
| 10 | recuperação isolada do hub | Backup e continuidade |
| 11 | aplicação de SLA e escalonamento | Operação padrão MSP |

Conteúdo e plano reproduzíveis em
`config/glpi/ness-operations-foundation-v1.json`; aplicação por modelos nativos
em `infra/scripts/glpi-operations-foundation.php`.
O script usa transação, não sobrescreve objetos existentes e exige notificações
já desabilitadas. As associações de equipe e categorias foram verificadas.
Reaplicações criaram zero objetos; os IDs originais foram preservados.

Corrigida também a URL-base GLPI de `http://localhost` para
`https://n-ticket.ness.com.br`, conforme o virtual host Caddy existente. O endereço
público foi verificado com TLS e redirecionamento ao SSO. A configuração faz
parte do manifesto e do aplicador; não foram alteradas as rotas de acesso.

## Prova de autorização

Três usuários temporários reais, perfil Read-Only 8, foram criados nas entidades
0, 1 e 8. O mesmo perfil possui leitura de projetos e base de conhecimento,
permitindo testar a entidade sem depender de ausência geral de permissão.

- Ness 0: HTTP 200 no projeto 1, tarefa 1 e artigos 7–11;
- Alupar 1: HTTP 403 nos mesmos sete objetos;
- Cavan 8: HTTP 403 nos mesmos sete objetos;
- três usuários removidos e ausência de usuários temporários confirmada;
- sessões encerradas e arquivo temporário de credenciais removido.

Verificador: `infra/scripts/glpi-foundation-access-check.py`. O fixture existente
`glpi-hub-client-check.php` ganhou a opção `--include-root`, preservando seu
comportamento anterior sem essa opção.

## SLA: pendência confirmada

Já existiam 29 categorias de ticket, um template, oito categorias de conhecimento
e oito SLAs Bronze/Silver/Gold/Platinum. Os SLAs 17–24 têm `definition_time` nulo;
o método nativo `SLA::getTime()` retornou zero para todos. Nenhum dos 407 tickets
ativos no sentido de não excluídos consultados tinha SLA de atendimento ou
resolução atribuído (`slas_id_tto=0`, `slas_id_ttr=0`).

Não foram presumidas unidades, prazos ou calendários. Foi solicitado o documento
com condições aprovadas. Não houve alteração dos SLAs ou dos tickets existentes.
As 29 categorias existentes foram preservadas, evitando duplicar a taxonomia.

## Evidência e reversão

Artefatos protegidos no servidor em
`/opt/n-infraops/rollback/recovery-20260908/`:

- `glpi-operations-applied.json`: IDs criados;
- `ness-operations-foundation-before-20260908220327.json`: estado anterior;
- `glpi-foundation-access-results.jsonl`: prova HTTP por entidade;
- `ness-glpi-url-before.json`: URL-base anterior;
- manifesto e aplicador utilizados.

Erros durante a aplicação são revertidos por transação. Para reversão posterior,
usar os IDs do manifesto e os modelos GLPI; verificar antes se houve trabalho
humano novo. Preservar histórico, retirar a visibilidade dos artigos e restaurar
a URL pelo snapshot se necessário. Não excluir registros que tenham sido
modificados por operadores desde a implantação.

Saúde às 22:06:45 UTC: Zabbix/GLPI OK, dois workers, filas vazias e zero
falhas/retries ou entregas/resoluções pendentes. Notificações permaneceram em 0.
F3 continua parcial: SLAs, consolidação/conversão do inventário e agentes ainda
não foram concluídos por esta etapa.
