# ness.os — trilha dinâmica de entregas

Decisão de 12/10/2026: entregar Zabbix por completo antes de trocar de ferramenta.
Esta trilha governa a ordem de execução; os critérios de segurança e corte dos
planos aprovados continuam válidos. Backup deixa de ser a tarefa inicial padrão.

## Ritmo de execução

### Escopo ampliado — autorização de 12/10/2026

Todos os hosts cadastrados na origem entram na trilha de qualidade, inclusive
os desativados no inventário; desativados não serão ativados automaticamente.
A aplicação permanece em ondas de até cinco hosts, com export anterior,
precondição, teste e rollback. Não remover histórico, substituir templates em
massa ou inferir tenant/owner/criticidade sem evidência. Cavan continua sendo
o piloto obrigatório para o corte; ampliar o escopo não dispensa os gates.

Fotografia em leitura da origem nesta execução: 325 hosts (323 habilitados,
2 desabilitados); 21 sem template diretamente vinculado; 1.850 itens
habilitados não suportados em 149 hosts habilitados. Tenant: 19 Cavan e 306
sem tag. Ausências de tags: criticality 325, service 311, tenant/site/owner/
technology 306, environment/role/scope 305. Ausência de template diretamente
vinculado exige investigação, não comprova erro por si só. Valores são uma
baseline datada, não indicadores de saúde permanentemente atuais.

Ordem: classificar todos os hosts; corrigir causas comprovadas de coleta em
ondas pequenas; reconciliar metadados com cadastro existente; medir cada onda;
ampliar dashboards de qualidade para o inventário completo. Lacunas de negócio
seguem em issues, sem impedir correções técnicas independentes.

- Uma entrega funcional em implementação por vez. Observação, backup e ações
  humanas seguem em trilhas auxiliares, sem ocupar a entrega ativa.
- Cada retomada lê o cartão ativo, verifica somente suas precondições e executa
  o próximo passo. Não refazer inventários e testes já comprovados sem motivo.
- Toda entrega termina com artefato utilizável/revisável, teste proporcional,
  commit, destino aplicado e próximo passo. Documento sozinho não equivale a
  funcionalidade entregue.
- Estados: preparado, implementado, validado em UAT, produtivo e aceito.
  Nenhum desses estados será confundido com outro.
- Dependência humana: issue existente ou nova, owner, passos e e-mail; continuar
  a próxima tarefa independente. Não cobrar novamente sem mudança acionável.
- Falha técnica: diagnosticar causa, corrigir e retestar o escopo afetado.
  Evitar mudar de ferramenta para contornar a falha.

## Entregas Zabbix

| Cartão | Resultado concreto | Aceite proporcional | Dependência |
| --- | --- | --- | --- |
| Z1 — cinco ativos prontos | Pacote de correção de tags, owner e templates; export anterior, delta e rollback por ativo | Cinco ativos identificados; origem de cada atributo; nenhum template incompatível; API em dry-run recusa estado divergente | Baseline offline existente; dúvidas de negócio viram issue |
| Z2 — coleta corrigida | Primeira onda FortiGate/links; depois switches, VMs e sistemas | Separar appliance de interface; corrigir causa dos itens; preservar histórico com Unlink; medir antes/depois | Aplicação e observação só no ambiente autorizado |
| Z3 — NOC utilizável | Dashboard de disponibilidade, problemas, fila e saúde da plataforma | Valores reconciliados, sem filtros indevidos; widgets legíveis e sem sobreposição; export e rollback | Preparação pode ocorrer durante observação Z2 |
| Z4 — qualidade e capacidade | Dashboard de unsupported, cobertura/tag/template, atraso e capacidade | Indicadores têm fonte, escopo e frescor; distinguir histórico, indisponível e atual | Reutilizar a baseline; validação corrente na janela |
| Z5 — serviços e mapas | Cavan Matriz e visão de conectividade por tenant | Links balanceados representados; serviço/owner/localidade rastreáveis; perfil cliente não acessa outro tenant | Cadastro desconhecido não será inventado |
| Z6 — experiência ness. | Marca, pt-BR, títulos e layout por camada reversível | Montserrat 500, preto/branco, ponto #00ade8; sem alterar core; contraste, móvel e rollback | Aplicação após estabilidade funcional |
| Z7 — migração preparada | Release Zabbix revisável, checklist de corte, DNS/proxies e retorno | Snapshot final previsto; allowlist; ausência de dupla coleta; abort criteria; backup atual validado uma vez | G0/G1/G2 e homologação Cavan para corte |
| Z8 — operação definitiva | Corte autorizado e observação D+1/D+3/D+7 | API/UI/SSO, queue/NVPS/busy, backup e alertas controlados; origem preservada 7–14 dias | Janela e GO; ações humanas em issues |

Z1 começa com o piloto interno de 5–10 ativos previsto no MVP; a primeira
unidade de trabalho contém cinco. Cavan Matriz segue obrigatório para o corte.
Lotes iniciais de correção: no máximo cinco ativos, sem exclusão de histórico.
Ausência de resposta humana permite preparar/testar, não inventar atributos ou
marcar homologação como concluída.

## Verificação que protege a entrega

1. Mudança de tags/template: testar transformação, precondição, idempotência e
   rollback; exportar apenas os objetos afetados.
2. Dashboard/branding: validar payload/layout, renderização e rollback. Não
   executar restore de banco para uma mudança de texto ou widget.
3. Mudança de banco, ingestão, identidade ou deploy: testes de integração e
   negativos adequados, backup/reversão aplicáveis e smoke test.
4. Suíte completa: na release candidata ou quando mudança transversal justificar.
   O resultado já obtido de 411 testes não será repetido a cada documento.
5. Evidência reutilizada conserva data e limite; estado histórico não vira
   saúde atual. Na promoção, renovar somente as provas exigidas pelo gate.

## Trilha auxiliar de backup

O job iniciado em 12/10 às 11:28 BRT no destino é acompanhado pelo mesmo serviço
systemd até estado terminal. Fazer uma validação de COMPLETED, SHA256SUMS e gzip
ao terminar; não iniciar outro dump porque uma consulta expirou. Restore já
comprovado só se repete por mudança relevante, falha ou aceite de release que
exija evidência atual. RPO de 24h continua obrigatório para promoção/produção.

## Cartão ativo e próxima retomada

**Ativo: Z1 — pacote de cinco ativos.**

Execução de 12/10: ferramenta de onda implementada, cinco testes aprovados,
dry-run do host interno 10084 preparado com templates preservados. Cadastro
dos outros quatro ativos e atributos de negócio aguardam issue #70; instruções
enviadas a Ismael com cópia a Ricardo. Z1 permanece parcial, não aceito.
Próxima tarefa independente: Z3, preparar/reconciliar o dashboard NOC existente,
sem regressar ao backup ou aguardar resposta da #70.

Z3: payload NOC nativo preparado em `config/zabbix/noc-uat-dashboard.json`,
privado e explicitamente identificado como UAT sem coleta. Teste de geometria
sem sobreposição aprovado; publicação API e renderização ainda pendentes.
API UAT rejeitou a credencial técnica existente; acesso mínimo na issue #71,
com instruções por e-mail. Próximo cartão independente: preparar Z4 com itens
reais de capacidade/fila identificados no banco restaurado, sem inventar IDs.

1. Reutilizar `zabbix-offline-quality-2026-10-12.md` e o relatório restaurado.
2. Identificar os ativos internos da plataforma e sua configuração existente
   no destino; selecionar cinco sem alterar produção.
3. Produzir export sanitizado e proposta com valores comprovados; lacunas
   viram issues de cadastro, não impedem o restante do pacote.
4. Implementar/verificar aplicação controlada e rollback por API no escopo
   autorizado; nenhuma edição direta de tabelas de configuração.
5. Publicar pacote/commit e avançar para Z2 ou Z3 se a aplicação aguardar gate.

**Não iniciar a retomada pelo backup.** A origem Zabbix mantém a janela
22:00–00:00 BRT para ações e leitura intensiva. Destino continua isolado até
aprovação dos gates; esta trilha não autoriza unmask, DNS ou dupla coleta.

Exceção autorizada em 12/10: janela de 24h e Cavan liberada para piloto,
conforme `zabbix-production-window-2026-10-12.md`. A leitura corrente da origem
mostrou que as tags Cavan já existem e que a UAT está desatualizada; prioridade
é sincronizar essa configuração antes de aplicar candidatos. A evidência nova
substitui a inferência de ausência de tags produtivas feita sobre o restore.

## Reporte de progresso

Em cada entrega informar: resultado funcional, ambiente, teste, commit,
limite restante e cartão seguinte. Medir progresso por cartões e critérios
aceitos, não por número de comandos ou quantidade de documentação.

Após Z8, aplicar o mesmo ritmo a GLPI, Hub/AIOps e demais ferramentas, mantendo
as dependências do plano completo e o Wazuh/Workspace após aceite do MVP.
