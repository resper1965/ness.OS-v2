# GLPI Agent — diagnóstico e plano de rollout (T07)

Estado em 04/11/2026, **somente leitura** (SELECT no GLPI 11.0.8 de produção).
Nada foi escrito, nenhum agente instalado, nenhum inventário enviado.
Relatório agregado: sem serial, IP, nome de pessoa ou valor secreto.
Política em `config/glpi/ness-agent-rollout.json`.

## 1. Diagnóstico dos sete registros "sem contato"

**Conclusão: não são agentes GLPI reais.** São resíduos de varredura criados em
julho (15/07–27/07; 100 a 112 dias sem contato) quando a entrada de inventário
aceitava POST sem autenticação.

| Evidência | Resultado |
|---|---|
| Versão, tag, porta | nulos nos 7 |
| User-Agent | navegador (Firefox), não `GLPI-Agent` |
| Nome/deviceid | 6 de 7 carregam payload `SLEEP(` (SQL injection time-based, 145–146 caracteres); 1 tem 1 caractere |
| Vínculo com ativo | 0 (`items_id = 0`) — nenhum computador criado por eles |
| Entidade | todos na raiz (Ness) |
| Tipo | `Core`; módulos: só inventário de computador marcado (6 de 7); deploy desligado |
| Equipamentos recusados | 0 |

Por item pedido:

- **Serviço instalado / tarefa agendada:** não se aplica — não há máquina por trás. Nenhum dos 110 computadores tem `last_inventory_update` nem `is_dynamic`; **nenhum agente real jamais reportou**.
- **Endpoint/TLS:** `enabled_inventory = 0` hoje (desligado depois do incidente). Externamente `n-ticket…/Inventory` responde 302 para o SSO (Authentik forward_auth), então um agente real **não chega** ao endpoint: o agente não faz SSO. Internamente (`ninf-glpi`) responde 403. Certificado de `n-ticket` expira em 07/12/2026 (renovação automática a confirmar).
- **Autenticação de inventário:** `auth_required = none` e `basic_auth_login` vazio. Se alguém religar o inventário sem mudar isto, qualquer cliente de rede cria agentes — foi exatamente o que ocorreu em julho. Não há cliente OAuth (0).
- **Regra de entidade:** 0 regras `RuleImportEntity`; `entities_id_default = 0`. Tudo que entrar cai na raiz. Isso impede declarar outro tenant via regra, mas também significa que cliente nenhum é separado hoje. As 71 regras `RuleImportAsset` são as padrão (57 ativas) — a correspondência por serial/UUID/nome pode atualizar ativo existente; ver teste isolado.
- **Higiene:** `stale_agents_delay = 0` (limpeza de agentes velhos efetivamente desligada, apesar de a tarefa `Cleanoldagents` rodar).

## 2. Cobertura e frescor por entidade (04/11/2026)

Computadores ativos (não excluídos, não-modelo). Todos cadastrados à mão; nenhum com primeiro inventário ⇒ **todos "desconhecido"**. Atrasado (>48 h): 0, pois ninguém começou.

| Entidade | Computadores | Com inventário | Agentes reais | Equip. de rede (manuais) |
|---|---:|---:|---:|---:|
| Ness (raiz) | 1 | 0 | 0 | 1 |
| Alupar Investimento | 60 | 0 | 0 | 90 |
| Alupar PE | 8 | 0 | 0 | 10 |
| Alupar CO | 4 | 0 | 0 | 13 |
| TBE | 0 | 0 | 0 | 10 |
| Target Trading | 4 | 0 | 0 | 6 |
| Leite Tosto e Barros | 0 | 0 | 0 | 5 |
| Bichara | 1 | 0 | 0 | 1 |
| Cavan | 19 | 0 | 0 | 9 |
| Nova Energia | 4 | 0 | 0 | 2 |
| Numen IT | 0 | 0 | 0 | 2 |
| TNE | 5 | 0 | 0 | 6 |
| Unimed | 4 | 0 | 0 | 0 |
| **Total** | **110** | **0 (0%)** | **0** | **155** |

(Os 7 registros-lixo ficam na raiz e não contam como cobertura.)

## 3. Política de frescor (proposta)

- Inventário **diário** (`inventory_frequency = 24 h`, já configurado).
- **Atrasado:** último contato > 48 h. **Desconhecido:** nunca houve inventário (antes da primeira entrega).
- **Exceção** para ativo intermitente (notebook, ativo de campo): registrada por ativo com motivo, responsável e prazo de revisão; sai do contador "atrasado" mas continua listada.
- Não altera SLA contratual. Medição por entidade com SELECT em `glpi_computers.last_inventory_update` / `glpi_agents.last_contact`.

## 4. Achados que exigem decisão do Ricardo

1. **Como o agente alcança o GLPI.** O host SSO bloqueia o agente. Opções: (a) caminho dedicado `/Inventory` no Caddy, fora do forward_auth, **com autenticação basic/OAuth e limite por origem**; (b) host separado só de inventário. Recomendo (a) com basic auth sobre TLS + allowlist de origem do RMM — é o menor passo. Mexer no Caddy é mudança de produção: precisa de janela e rollback.
2. **Autenticação:** `auth_required` deve sair de `none`. O GLPI aceita **uma** credencial global; ela não separa clientes.
3. **Atribuição de tenant:** enquanto houver credencial única, tag/domínio declarados pelo cliente não são confiáveis. Para o piloto interno, entidade fixa (raiz Ness). Para clientes: ou regra por origem/credencial por onda, ou manter cadastro manual até haver mecanismo aprovado. Recomendo piloto só na Ness e **não** abrir regra por tag.
4. **Sete registros-lixo:** limpar (escrita; Ricardo/PMO decide) ou deixar como evidência do incidente. Recomendo arquivar a evidência (já coletada neste relatório) e depois excluir, em janela com backup.
5. **Privacidade:** desligar `import_process`, `import_registry` (hoje 1) antes do piloto; `import_software` fica ligado.
6. **RMM:** ADR 0003 (Datto/Atera/SuperOps distribuem o agente) e ADR 0021 (Action1 alvo, em homologação) divergem. Qual RMM instala nos 5 ativos do piloto?

## 5. Piloto de 5 ativos internos — **PENDENTE (Ricardo / #79)**

Pré-requisitos (bloqueiam o piloto): decisões 1, 2 e 6; escolha dos 5 ativos; janela.
Passos: (1) baseline: contagem de agentes/computadores/duplicatas; (2) autenticação ativa no endpoint e `enabled_inventory = 1` só então; (3) instalação pelo RMM do ativo, **só módulo de inventário** (sem deploy, sem descoberta de rede, sem wake-on-lan); (4) primeiro inventário e conferência: um agente, um computador, entidade Ness, vínculo com o cadastro manual existente (sem duplicata); (5) segundo contato após 24 h, `last_contact` e `version` preenchidos; (6) consumo (CPU/RAM/rede do agente) e campos coletados revisados contra privacidade; (7) desinstalação de um ativo e verificação de que o registro não cria duplicata ao reinstalar.
Aceite: 5/5 com identidade estável, 2 contatos consecutivos, 0 duplicatas, 0 registro em outra entidade.

## 6. Teste isolado (nunca em produção)

Ambiente: cópia do banco/volume GLPI 11.0.8 em stack descartável, sem rota para produção, dados sintéticos.
1. **Sem credencial:** POST de inventário sintético → esperado 401/403, nenhum agente criado.
2. **Credencial errada** → 401, nenhum agente.
3. **Inventário forjado:** credencial válida + XML/JSON declarando tag/domínio/hostname de outra entidade → esperado cair na entidade da regra do servidor, nunca na declarada.
4. **Associação errada:** inventário com serial/UUID/nome de um computador de outra entidade → esperado criar/atualizar apenas dentro da entidade fixa; falha se atualizar o ativo do outro tenant (verificar efeito das regras `Computer update (by serial/uuid/name)` sobre sub-entidades).
5. **Payload hostil** (`SLEEP(`, nomes longos) → recusado/escapado, sem lentidão.
Critério: qualquer item 3/4 que toque outra entidade reprova a abertura do endpoint.

## 7. Rollback

- Piloto: `enabled_inventory = 0`, desinstalar agentes pelo RMM, restaurar a rota do Caddy do backup anterior (`/opt/n-infraops/rollback/…`), recarregar o Caddy.
- Registros criados pelo piloto: lista por `agents_id` anotada no passo 1; remover só estes, nunca em massa. Cadastro manual dos ativos permanece como fonte até aceite.
- Ondas seguintes: lotes aprovados; retornar ao pacote/cadastro anterior por ativo.

## Reprodução do diagnóstico

`infra/scripts/glpi-inventory-readiness-report.sh` e `glpi-inventory-security-audit.sh` (somente leitura). Neste relatório os números vêm de SELECTs equivalentes sobre `glpi_agents`, `glpi_configs`, `glpi_rules`, `glpi_computers`, `glpi_networkequipments`, `glpi_refusedequipments`.
