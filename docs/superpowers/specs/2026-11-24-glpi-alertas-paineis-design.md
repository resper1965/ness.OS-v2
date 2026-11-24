# GLPI como mesa do técnico, alertas no celular e painel por cliente

**Data:** 24/11/2026 · **Pedido por:** Esper · **Estado:** rascunho para aprovação

Marcação: **[Esper]** = decidido por ele; **[agente]** = decisão do agente, pode ser revista.

## 1. Por quê

Hoje o GLPI é um depósito, não uma mesa de trabalho. Contagem de 24/11:

- 52.973 chamados, todos com status "novo";
- 0 com técnico, 0 com solução, 0 com prazo;
- último login de técnico em 13/11.

O Hub avisa por e-mail sem filtro. O PR #290 já limitou o aviso a casos que viraram chamado, mas ainda não foi promovido. O prazo está cadastrado no Hub e no GLPI e não é medido em nenhum dos dois. O cliente não tem um painel próprio.

O objetivo é que o técnico **registre e resolva no GLPI [Esper]**, receba **alerta no celular [Esper]** e que **cada cliente tenha painel [Esper]**. A referência é o SOCFortress CoPilot: dois relógios de prazo, "aguardando cliente" e portal do cliente com prazo. Só a prática é copiada; a ferramenta não será adotada.

## 2. Metas, não-metas e anti-metas

**Metas**
- O técnico abre o GLPI e vê só a fila dos seus grupos, com prazo.
- Chamado de NOC e de SOC sobre a mesma causa aparecem ligados.
- Alertas chegam ao celular de técnicos da ness, técnicos de cliente e gestores do cliente, cada um recebendo só o que é seu.
- Cada cliente tem um painel no Hub. A ness vê o painel de todos os clientes; o cliente vê só o dele, em modo só leitura.

**Não-metas**
- Não haverá app nativo em loja. O Hub é um PWA instalável, que já existe com push.
- Não haverá fila de trabalho no Hub. A fila é do GLPI.
- Governança (dados e referências): Esper detalha depois. Este desenho só não deve impedir que ela entre (ver §9).

**Anti-metas** (falha, mesmo que funcione)
- O mesmo evento avisado por dois remetentes (GLPI e Hub).
- O cliente ver dado de outro cliente, nome de ferramenta, nome de servidor ou nome de pessoa da ness.
- Um técnico externo enxergar ou alterar chamado fora da sua entidade.
- A espera pelo cliente contar contra o prazo da ness.

## 3. Restrições

- **Produção:** toda mudança no GLPI de produção e a limpeza em massa exigem frase explícita do Esper. Fazer backup antes.
- **Cliente externo:** só leitura no Hub. Nunca recebe o perfil de operador.
- **Técnico externo:** no Hub vê só o painel; age apenas pelo chamado no GLPI e só na própria entidade **[Esper]**. Hoje existem técnicos externos só na **Cavan** e na **Alupar [Esper]**.
- **Marca:** DS 2.0.1, horário de Brasília. No que o cliente vê, o único nome de produto é `ness.OS`.
- **Ambiente:** GLPI 11.0.8, que já tem 13 entidades, 29 categorias, 8 SLAs e 6 regras de chamado.

## 4. GLPI

### 4.1 Grupos e perfis
- **Grupos por cliente [Esper].** Cada grupo reúne os técnicos da ness que atendem aquele cliente e, na Cavan e na Alupar, os técnicos do próprio cliente. Um técnico da ness pode estar em vários grupos **[Esper]**.
- **Plantão [Esper].** Vê todas as entidades e recebe:
  - chamado de entidade sem grupo;
  - chamado fora do horário do contrato, segundo o calendário do SLA **[agente]**.
- **Perfil "Técnico externo" [agente].** Derivado do perfil Technician, com acesso restrito à própria entidade e sem permissão de configuração. Os usuários externos recebem esse perfil vinculado só à entidade deles.
- Os 18 grupos de área atuais, todos vazios (`infraops/NOC`, `secops`...), devem ser arquivados, e não excluídos **[agente]**.

### 4.2 Categorias: NOC e SOC continuam [Esper]
As 29 categorias soltas passam a formar uma árvore de três ramos **[agente]**:

| Ramo | Subcategorias |
|---|---|
| **NOC** | Conectividade e links · Disponibilidade · Desempenho · Backup · Servidores |
| **SOC** | Acesso suspeito · Malware · Vulnerabilidade · Configuração e conformidade · Incidente de segurança |
| **Serviço** | Pedido · Mudança (GMUD infra/segurança/sistemas) · Acessos e identidades |

O mapa de categoria antiga para nova fica com o construtor. Nenhuma categoria em uso pode ser excluída sem antes ser migrada.

**Regras:**
- As regras "Route to NOC/SOC" deixam de **escolher grupo** e passam só a **definir a categoria**.
- O grupo sempre sai da entidade do chamado.

**Pendente:** a ness e o técnico externo podem colocar o chamado em Pendente quando dependem do usuário do cliente. O relógio pausa nos dois casos **[agente]**.

**Tier de SLA:** o tier (Bronze, Silver, Gold ou Platinum) é definido por entidade no próprio GLPI, configurado à mão nas 13 entidades, sem sincronização com o Hub **[agente]**. ponytail: duas fontes de contrato; upgrade path: sincronizar a partir de `n_infraops_contracts` quando houver muitos clientes.

### 4.3 Quando um indica o outro [Esper]
NOC e SOC continuam separados, mas um problema de um lado pode ser causa ou sintoma do outro. Exemplos:
- o link cai e o agente Wazuh desconecta;
- a CPU sobe enquanto um processo suspeito roda na mesma máquina.

**Mecanismo [agente]:** ao abrir um chamado, o decisor do Hub procura um chamado aberto do **outro ramo** que seja do mesmo cliente e da mesma máquina ou do mesmo site, aberto dentro de uma janela de tempo (valor inicial: 30 min, ajustável em `n_infraops_ticket_rules`).
- Se encontrar, liga os dois com "chamado relacionado", recurso nativo do GLPI, e escreve um acompanhamento em cada um explicando a ligação.
- **Pré-requisito:** o ramo SOC precisa abrir chamado. Hoje a integração do Wazuh está em modo observação e não abre nada. A G3 inclui ligar "nível ≥ 12 vira chamado", que já estava decidido para depois de medir o volume. Até isso entrar, a ligação só acontece com chamado SOC aberto à mão.
- Os chamados **não são fundidos**. Cada ramo resolve o seu.
- A sugestão de causa feita pela IA (spec de 17/11) pode acrescentar ligações depois, sempre marcadas como sugestão.

### 4.4 Prazo
- O SLA nativo do GLPI passa a ser **a fonte do prazo**, com dois relógios: tempo até assumir (TTO) e tempo até resolver (TTR).
- As regras Bronze, Silver, Gold e Platinum já existem, mas não pegam nenhum chamado. É preciso corrigir a condição para que cada chamado receba o SLA do contrato da sua entidade.
- O status **"Pendente"** pausa o relógio enquanto a ness espera o cliente. Só a ness pode colocar o chamado em Pendente.
- O Hub **lê** o prazo do GLPI. As tabelas de SLA do Hub (`n_infraops_sla_*`) deixam de ser fonte e são aposentadas depois que o painel estiver lendo do GLPI **[agente]**.
- Medidas copiadas do CoPilot **[agente]**:
  - cumprimento = no prazo ÷ (no prazo + vencidos);
  - o que ainda está correndo não entra na conta;
  - período sem resultado aparece como "—";
  - tempos em mediana, com p90 ao lado.

### 4.5 Conteúdo do chamado
O decisor já abre o chamado. Passa a incluir:
- resumo do Hub: o que aconteceu, a máquina, os sinais e os horários;
- link "ver no ness.OS" apontando para a máquina ou o caso;
- link para o procedimento da base de conhecimento correspondente à categoria, quando existir.

Os procedimentos ficam na base de conhecimento nativa do GLPI. O primeiro a escrever é "RDP vindo de loopback" (caso `TSRZKDTC03`). A redação dos demais é trabalho contínuo e não bloqueia a entrega.

### 4.6 Fechamento automático
Quando o Zabbix resolve o problema e nenhum técnico mexeu no chamado (sem técnico e sem acompanhamento humano), o decisor registra a solução no GLPI ("normalizado na origem") e resolve o chamado. O estado `auto_closed` já existe no decisor; falta gravar a solução no GLPI. Se um técnico já mexeu, o chamado fica aberto para ele.

### 4.7 Limpeza do acumulado
- Fazer backup do banco do GLPI.
- Resolver em massa os chamados "novos" que não têm técnico nem acompanhamento humano e que se encaixam em um destes casos:
  - foram abertos antes da regra de chamados de 23/11, mesmo sem vínculo com um incidente no Hub (todos foram abertos pelo Hub);
  - o incidente no Hub já está resolvido ou é ruído (estado `panel` ou título da lista de ruído).
- O resto vai para revisão manual. A estimativa é de dezenas. **[agente]**
- Exige a frase do Esper. Rollback: restaurar a partir do backup.

## 5. Alertas

**Um remetente só [agente]:** só o Hub avisa. As notificações do GLPI continuam desligadas, para não haver aviso duplicado.

**Canal [agente]:**
- push do PWA do Hub instalado no celular, que já existe com escalonamento;
- e-mail apenas para escalonamento e para os resumos;
- ponytail: o push da web não fura o modo silencioso. Se o plantão precisar de alarme noturno que acorde, o próximo degrau é um app nativo ou um serviço de alarme com chamada telefônica.

**Quem recebe o quê [agente]:**

| Destinatário | Push | E-mail |
|---|---|---|
| Técnico (ness ou externo) | chamado novo para um grupo dele · prazo perto de vencer · chamado relacionado novo | escalonamento |
| Plantão | toda severidade alta ou crítica de qualquer cliente · chamado sem grupo | escalonamento |
| Gestor do cliente | chamado aberto · "aguardando você" · resolvido; só o próprio cliente e sem nome de ferramenta | resumo periódico (diário ou semanal, configurável por cliente), nunca um e-mail por evento |

**Mudança no código:** hoje o destinatário sai do papel do usuário no Hub (`_recipients`). Passa a sair do **grupo do GLPI** atribuído ao chamado. Para isso, o usuário do Hub precisa ser ligado ao usuário do GLPI pelo e-mail **[agente]**. O escalonamento por contrato continua, com o passo reinterpretado **[agente]**: passo 1 = grupo do chamado, passo 2 = plantão, passo 3 = gestão da ness.

**Papéis no Hub [agente]:**
- o técnico externo e o gestor do cliente usam o papel `cliente` já existente, preso ao tenant, só leitura, e veem a versão do cliente do painel;
- quem recebe o resumo periódico é marcado por uma opção no usuário, não por um papel novo.

**Controles:**
- deduplicação por chamado;
- horário de silêncio por usuário, exceto para o plantão;
- tela "meus avisos" no Hub para silenciar ou ativar cada tipo de aviso.

## 6. Painel por cliente [Esper]

- Uma tela por cliente no Hub, que é a "ficha do cliente" da proposta de interface.
- A ness vê o painel de todos os clientes. Cliente e técnico externo veem só o painel do próprio cliente, em modo só leitura **[Esper]**.
- **Blocos [agente]:**
  - **Agora:** chamados abertos por ramo (NOC/SOC), "aguardando você" e prazo em risco;
  - **Prazo:** cumprimento do mês e tendência de 90 dias, lidos do GLPI;
  - **Disponibilidade:** sites e links fora do ar e histórico;
  - **Segurança:** alertas triados do período e principais regras;
  - **Exposição:** vulnerabilidades críticas, priorizadas por exploração conhecida (KEV/EPSS, quando entrar), e máquinas sem suporte;
  - **Cobertura:** máquinas no inventário × Zabbix × Wazuh × Action1.
- A versão do cliente pode mostrar as máquinas e os sites **do próprio cliente**. O que é proibido são os nomes de servidores e ferramentas da ness **[agente]**.
- A versão do cliente mostra os mesmos blocos, sem nome de pessoa da ness, de ferramenta ou de servidor. O bloco de prazo é ligado por cliente e começa desligado, copiando o CoPilot **[agente]**.

## 7. Fases e aceite

| Fase | Entrega | Aceite |
|---|---|---|
| G1 | Grupos, plantão, perfil externo (Cavan e Alupar), árvore de categorias, regras de atribuição e SLA corrigidas | chamado sintético por entidade cai no grupo certo, com SLA; técnico externo não vê outra entidade |
| G2 | Limpeza do acumulado e fechamento automático | fila "novos" na casa das dezenas; recuperação no Zabbix resolve chamado não tocado |
| G3 | Conteúdo do chamado e ligação NOC↔SOC | chamado com resumo e link; par sintético NOC+SOC fica relacionado |
| A1 | Destinatário pelo grupo do GLPI, push para técnico e plantão | técnico do grupo recebe; quem não é do grupo não recebe |
| A2 | Gestor do cliente: push e resumo periódico | gestor da Cavan só recebe da Cavan |
| P1 | Painel do cliente (visão ness) | blocos com dado real de 2 clientes |
| P2 | Painel na visão do cliente | usuário cliente vê só o próprio cliente, sem dado proibido |

Ordem: G1 → G2 → A1 → G3 → P1 → A2 → P2. Cada fase é um PR ou uma mudança de configuração com backup. Toda promoção segue `docs/runbooks/promocao-hub.md`.

## 8. O que fica com o construtor
- O mapa de categoria antiga para nova.
- A forma de aplicar a configuração do GLPI: API REST ou script idempotente, com rollback.
- O desenho visual dos blocos do painel, dentro do DS 2.0.1 e do kit `nx-*`.
- O ajuste fino da janela de 30 min da ligação NOC↔SOC.

## 9. Fora deste desenho
- **Governança:** dados e referências, a detalhar pelo Esper. Precisa ter espaço no painel do cliente como um bloco futuro.
- Corte de ruído no agente Wazuh, KEV/EPSS na carga de vulnerabilidades e memória de falso positivo da IA: são frentes paralelas, recomendadas na análise do SOCFortress.
- Redesenho do menu do Hub (Situação, Investigar, Exposição): vem depois e consome o prazo do GLPI.
