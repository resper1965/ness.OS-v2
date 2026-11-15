# Regra de abertura de chamados: ação, dedup e causa raiz

**Data:** 15/11/2026 · **Dono:** Ricardo · **Topologia:** Ismael (corrige o palpite inicial)

## Por quê

Hoje cada evento de problema do Zabbix vira um chamado no GLPI. Em 30 dias (até 15/11):

- **45 mil chamados, 1.500 por dia.** No GLPI havia 46 mil ativos, todos em "Novo", nenhum com técnico atribuído ou comentário humano.
- **65%** eram serviços de atualização do Windows parados (Google Updater, AppX, Dropbox, Brave). **13%** eram desempenho fino (paginação, fila de CPU, latência de disco).
- **49%** se resolveram sozinhos em menos de 30 min; até "FortiGate fora do ar" (alta) volta em menos de 5 min em 72% dos casos.
- **90%** vieram de 449 pares host+gatilho que se repetem. Um único par gerou 2.122 chamados.
- **3.298** quedas de link ou disponibilidade foram seguidas, em até 5 min, por **3.752** alertas do mesmo cliente: sintomas viraram chamados próprios.
- O volume travou o GLPI no cutover (busca por marcador no título varre a tabela).

A operação trabalha olhando o Zabbix, não o GLPI. Regra do Ricardo: **chamado só quando há necessidade de ação; o resto é dado de painel, que aparece e alerta na tela.**

## Objetivos

1. Chamado no GLPI só para problema que exige ação humana.
2. Um chamado por problema (dedup): repetição vira comentário, não chamado novo.
3. Causa e consequência: queda de link gera **um** chamado; os sintomas atrás dele entram como comentário/lista nesse chamado.
4. Todo evento continua visível e alertando no painel (Hub e Zabbix). Nada se perde.

## Não objetivos

- Mudar a tela de Monitoramento (já mostra tudo).
- Regras por contrato/cliente (a lista é a mesma para todos nesta etapa).
- Integração Wazuh (segue o mesmo princípio depois).
- Apagar dados históricos (a lixeira de 15/11 já cuidou do passado).

## Anti-objetivos (falha mesmo se "funcionar")

- Problema real e sustentado (disco enchendo, link fora, site fora) **sem** chamado.
- Sintoma suprimido cuja causa não tem chamado (supressão sem causa aberta).
- Um cliente vendo ou afetando chamado de outro (a correlação é sempre dentro do mesmo cliente).
- Voltar a abrir um chamado por evento.

## A regra

### 1. Painel (todo evento)
Todo evento do Zabbix segue entrando no Hub como hoje (incidente, severidade, cliente, host). A tela alerta. Nenhuma mudança.

### 2. Chamado (precisa de ação)
Um evento vira chamado quando **todas** valem:

- **Está na lista de ação** (abaixo) **ou** tem severidade alta/desastre (4–5).
- **Continua ativo depois de 15 min** (carência). Se o Zabbix resolver antes, não abre chamado.
- **Não é sintoma** de uma causa já aberta (regra 4).
- **Não existe chamado aberto** para o mesmo host+gatilho (regra 3).

**Lista de ação** (palpite inicial, por padrão no nome do gatilho; editável sem deploy):

| Grupo | Exemplos |
|---|---|
| Disco | espaço livre baixo, disco cheio, FS |
| Disponibilidade | host fora por ICMP, agente indisponível, sem dados |
| Rede/link | túnel caído, SD-WAN health check dead, link/interface down, BGP/OSPF |
| Capacidade sustentada | memória > 90%, CPU alta, swap — só se passar da carência |
| Serviço de negócio | serviço Windows **fora** da lista de ruído, HTTP/serviço da aplicação fora (ex.: IntraNESS) |

**Nunca abre chamado** (ruído): serviços de atualização do Windows (Google/Edge/Dropbox/Brave Updater, AppXSvc e similares), desempenho fino (Memory Pages/sec, privileged time, queue length, latência de leitura/escrita, page table), "descrição do SO mudou", "host reiniciado", "firmware não auditável/sem SNMP" (pendência de configuração).

Simulação sobre os 30 dias: só as regras 2 e 3 levam de ~1.500 para **~60 chamados/dia**; a regra 4 reduz mais.

### 3. Dedup
- Chave do chamado: **cliente + host + gatilho** (não mais o `event_id`).
- Se há chamado aberto para a chave, o novo evento vira **comentário** no chamado ("voltou a ocorrer às HH:MM"), sem chamado novo.
- O chamado guarda quantas vezes ocorreu e a última ocorrência.
- **Reabertura:** se a mesma chave voltar em até **24 h** depois de o chamado ter sido fechado automaticamente (regra 5), o Hub **reabre o mesmo chamado** com comentário, em vez de abrir outro. Depois de 24 h, chamado novo. Chamado fechado por técnico não é reaberto: abre novo, citando o anterior. O vínculo chave→chamado fica guardado no Hub com estado e data de fechamento.

### 4. Causa e consequência
Duas camadas:

**4a. No Zabbix (nativo):** dependência de gatilho "hosts do site X dependem do gatilho de disponibilidade do FortiGate do site X". Com o link fora, o Zabbix não dispara os alertas dos hosts atrás dele.
- **Palpite de topologia (Ismael corrige):** cada grupo `[ Cliente ] [ Site ]` do Zabbix é um site; o FortiGate do grupo é o gateway dos demais hosts do grupo.
- Medido em 15/11: 57 sites, 378 hosts. 12 sites têm 1 FortiGate (palpite direto). 37 têm 2+ (HA ou vários links: precisa saber qual é o pai; o palpite é depender de **todos** caírem). 8 não têm FortiGate (ficam sem dependência). 6 hosts não estão em nenhum site.
- A dependência é aplicada por script idempotente, a partir de um arquivo de topologia versionado que o Ismael revisa.
- **Entra neste plano, como entrega separada.** A primeira versão do arquivo de topologia é gerada pelo construtor a partir dos grupos e fica em `infra/zabbix/topologia-sites.yml`. Não há Zabbix de homologação no ar (`zabbix-uat` responde 521): o script tem modo simulação (lista o que criaria) e `--apply`, roda no próprio servidor do Zabbix pela API local (`127.0.0.1:8080`) com o token de `/etc/ness-os/zabbix-cutover-bootstrap.env`, marca o que cria (tag ou descrição) e tem `--rollback` que remove só o que criou. O `--apply` em produção pede frase do Ricardo, um site primeiro, depois o resto.
- **Atenção:** o token do bootstrap respondeu "Not authorized" para `action.update` em 15/11. Conferir a permissão de escrita em gatilhos antes; se faltar, usar um token de administrador dedicado.

**4b. No Hub (rede de segurança):** para o que o Zabbix não cobrir. Quando há uma **causa ativa** (evento de rede/link ou de disponibilidade de um gateway, ainda não resolvido no Zabbix, com ou sem chamado) num cliente+site, todo evento do **mesmo cliente e mesmo site** que começar entre 2 min antes da causa e enquanto ela estiver ativa vira **sintoma**: não abre chamado; quando a causa ganhar chamado, os sintomas entram como lista nele.
- **Ordem de avaliação:** o job da carência decide primeiro as causas, depois os sintomas. Sintoma cuja carência vence antes da causa espera a decisão da causa.
- **Causa resolvida antes da carência (sem chamado):** os sintomas ainda ativos voltam à regra 2, com a carência contada **a partir da resolução da causa**. Assim nenhum sintoma fica suprimido sem causa ativa (anti-objetivo).
- **Causa com chamado e resolvida:** sintomas ainda ativos após mais 15 min seguem a regra 2 normalmente.
- Site vem do grupo `[ Cliente ] [ Site ]` do host (hoje só 19% dos incidentes trazem a tag `site`; o Hub já lê os hostgroups do host).

### 5. Fechamento
- Quando o Zabbix resolve um evento com chamado: comentário no chamado ("resolvido na origem às HH:MM") e o incidente no Hub vai para `resolved`.
- **Fechar o chamado no GLPI** automaticamente quando o Zabbix resolve: palpite **sim**, com solução "resolvido na origem", se nenhum técnico tiver interagido. Se houver técnico atribuído, só comenta.

## Restrições

- Correlação e dedup sempre dentro do **mesmo cliente** (multi-tenant).
- Nada de chamado perdido por falha do GLPI: o retry atual (12 tentativas) continua.
- A busca por marcador no título deixa de ser usada para dedup: o Hub guarda o id do chamado por chave.
- Lista de ação, lista de ruído e carência configuráveis sem deploy (tabela no Hub).
- Mudanças no Zabbix (dependências, desligar gatilhos de ruído) em produção pedem frase do Ricardo e têm rollback (script remove o que criou).

## Decidido nesta conversa

- Chamado = necessidade de ação; resto = painel com alerta (Ricardo).
- Dedup e causa→consequência obrigatórios (Ricardo).
- Topologia pelo palpite dos grupos `[ Cliente ] [ Site ]`; Ismael corrige depois (Ricardo).

## Chamadas minhas (revisar)

- Carência de **15 min** (dados: acima disso a curva achata; 5 min daria ~80/dia, 30 min ~54/dia).
- Severidade 4–5 sempre entra, mesmo fora da lista, mas **também** com carência.
- Site com 2+ FortiGates: dependência de "todos fora".
- Fechar chamado automaticamente quando o Zabbix resolve e ninguém tocou.
- Reabrir o mesmo chamado se o problema voltar em até 24 h depois do fechamento automático.
- Sintoma é suprimido pela **causa ativa no Zabbix**, não pela existência do chamado; causa decidida antes dos sintomas.
- Dependências no Zabbix (4a) entram neste plano, sem homologação, com simulação, aplicação por site e rollback.
- A simulação de ~60/dia não considerou a reabertura; o número real tende a ser menor.
- Desligar no Zabbix os gatilhos de serviço de atualização (não só filtrar no Hub). Fica como passo separado, com frase.

## Deixado ao construtor

Estrutura das tabelas, onde mora a carência (job periódico vs. tarefa agendada), formato do comentário de sintoma, testes.
