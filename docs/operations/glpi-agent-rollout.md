# GLPI Agent — diagnóstico e plano de rollout (T07)

Estado em 04/11/2026, **somente leitura** (§8 acrescenta o preparo aprovado, ainda não aplicado) (SELECT no GLPI 11.0.8 de produção).
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
- **Endpoint/TLS:** `enabled_inventory = 0` hoje. Externamente `n-ticket…/Inventory` responde 302 para o SSO (Authentik forward_auth), então um agente real **não chega** ao endpoint: o agente não faz SSO. Internamente (`ninf-glpi`) responde 403. Certificado de `n-ticket` expira em 07/12/2026 (renovação automática a confirmar).
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

## 8. Preparo aprovado (T07) — NÃO aplicado

Decisões do Ricardo: (1) rota `/Inventory` dedicada no Caddy, fora do SSO, básica sobre TLS + lista de origens; (2) piloto só na Ness, entidade fixa, sem regra por tag; (3) excluir os 7 registros de varredura, com backup e rollback; (4) desligar `import_process` e `import_registry`; (5) RMM = Action1 (ADR 0021).

Duas etapas independentes. A 8.1 não expõe nada; a 8.2 só roda quando o piloto começar.

### 8.1 GLPI — `infra/scripts/glpi-t07-inventory-prepare.php`

Faz, numa transação: `import_process=0`, `import_registry=0`, `auth_required=basic_auth` com login/senha de inventário, e exclui definitivamente os agentes de varredura. **Nunca toca `enabled_inventory`** (aborta se não for 0; continua 0 até o gate do piloto). Não usa `callAsSystem`.

Critério dos 7 agentes (todos juntos): entidade raiz, `Computer` sem ativo (`items_id=0`), sem versão/porta/tag, User-Agent `Mozilla/%`, sem contato há mais de 100 dias, e payload `SLEEP(` ou `deviceid` de 1 caractere. Se o conjunto não for exatamente os ids `1..7`, aborta. Também aborta se houver referência em `rulematchedlogs`, `unmanageds` ou `refusedequipments`.

```bash
A='sudo -n docker exec -i -u www-data ninf-glpi php --'
S=infra/scripts/glpi-t07-inventory-prepare.php
$A < $S                      # dry-run: só SELECT; mostra ids, linhas de log e estado atual
```

Aplicar (janela). A senha é gerada na hora e vai para um env-file 0600 (nunca em argv: apareceria no log do `sudo` e no `ps`) e para o cofre; nunca para arquivo versionado. O login pode ficar no argv.

```bash
set -o pipefail; umask 077
R=/opt/n-infraops/rollback/glpi-t07; S=infra/scripts/glpi-t07-inventory-prepare.php
sudo -n install -d -m 700 $R
PW=$(openssl rand -hex 24)     # 48 caracteres; guardar no Psono antes de aplicar
sudo -n install -m 600 /dev/null $R/.env
printf 'GLPI_INVENTORY_BASIC_PASSWORD=%s\n' "$PW" | sudo -n tee $R/.env >/dev/null; unset PW
F=$R/rollback-$(date +%F-%H%M%S).json; sudo -n install -m 600 /dev/null $F
sudo -n docker exec -i -u www-data -e GLPI_INVENTORY_BASIC_LOGIN=glpi-inventory --env-file $R/.env \
  ninf-glpi php -- --apply < $S | sudo -n tee $F >/dev/null; echo "pipeline rc=$?"
sudo -n shred -u $R/.env       # sempre, com sucesso ou falha
```

Leia o **stderr** antes de seguir: sucesso termina com `{"applied":true,...}`; qualquer `FAIL: ...` antes do commit significa que nada foi escrito (validação prévia e transação com rollback). Um `FAIL: ... readback mismatch` vem **depois** do commit: a escrita ficou aplicada; investigue e, se preciso, use o rollback abaixo. Não prossiga para o Caddy sem `applied:true`. O nome do arquivo de rollback leva hora para que um segundo `--apply` não sobrescreva o primeiro.

O JSON de rollback é gravado **antes** da escrita e contém: linhas completas dos 7 agentes (inclui `remote_addr`, `useragent`, `name`, `deviceid` — IPs e metadados de terceiros que varreram o serviço), linhas de `glpi_logs` e `restore_sql`; e a configuração anterior. Num segundo `--apply` a "configuração anterior" já é a nova: traz o login e a senha de inventário **cifrada** (chave do GLPI). Trate como sensível: diretório 700 e arquivo 600 só na VPS, **fora do Git**, descarte em 30 dias (`sudo -n shred -u`) depois do aceite do piloto.

Rollback (caminho absoluto; `$R` não existe em shell nova; leitura com `sudo` porque o diretório é 700 de root):

```bash
J=/opt/n-infraops/rollback/glpi-t07/rollback-AAAA-MM-DD-HHMMSS.json
sudo -n cat $J | python3 -c "import json,sys;print('START TRANSACTION;');print('\n'.join(json.load(sys.stdin)['restore_sql']));print('COMMIT;')" \
  | sudo -n docker exec -i ninf-glpi-db sh -c 'mariadb -uroot -p"$MYSQL_ROOT_PASSWORD" glpi'
```

Se algum comando do restore falhar, o `COMMIT` não roda e a conexão encerra com rollback implícito. O restore recoloca `auth_required`, `import_*` e os agentes; `basic_auth_login`/`basic_auth_password` voltam ao valor anterior (vazio no primeiro `--apply`). Reexecutar o dry-run depois do rollback volta a listar os mesmos 7 ids. Validado em lab sintético (MariaDB 10.11 + GLPI 11.0.11): dry-run, `--apply` sem credencial (recusa), `--apply`, leitura de volta, restauração por `restore_sql`.

### 8.2 Caddy — `infra/caddy/glpi-inventory-route.example.Caddyfile`

Exemplo, **não aplicado**. Entra no `route {}` de `n-ticket.ness.com.br` em `app/Caddyfile` antes do `forward_auth`. Só `POST /Inventory` exato passa; demais métodos recebem 405 e subcaminhos (`/Inventory/Configuration`) continuam atrás do SSO. Ordem: origem (`remote_ip`, 403) → básica (401) → proxy, removendo cabeçalhos de identidade SSO/`Remote-User`. O GLPI valida a mesma credencial (`auth_required=basic_auth`). Variáveis lidas do ambiente do Caddy (hash `bcrypt` via `caddy hash-password`; nada no repo); lista de origens vazia nega tudo.

Verificado em Caddy 2 isolado (sem credencial 401, errada 401, correta 200, GET 405, `/Inventory/Configuration` e `/` seguem para o SSO, origem fora da lista 403).

Procedimento (só no início do piloto, depois de 8.1 e do teste isolado do §6):
1. Backup: `cp app/Caddyfile /opt/n-infraops/rollback/glpi-t07/Caddyfile.$(date +%F)` e `caddy validate` do candidato com as variáveis.
2. Definir `GLPI_INVENTORY_BASIC_LOGIN`, `GLPI_INVENTORY_BASIC_HASH` (hash da senha de 8.1) e `GLPI_INVENTORY_ORIGINS` (saída do Action1/rede da Ness) no ambiente do `ninf-caddy`.
   **Nunca definir só uma das duas** (`..._BASIC_LOGIN` sem `..._BASIC_HASH` ou o inverso): o `basic_auth` fica vazio, o Caddyfile deixa de adaptar e **derruba todos os sites** do `ninf-caddy`. Defina as duas no mesmo passo.
3. Inserir o trecho e rodar `caddy validate` **com as variáveis reais** (`docker exec ninf-caddy caddy validate --config /etc/caddy/Caddyfile`, no ambiente do contêiner que vai carregar). Só se válido: `caddy reload` (nunca restart do contêiner: derruba os demais sites).
4. Pré-requisitos da conferência (antes de liberar o piloto): (a) o cabeçalho `Authorization` chega ao PHP do GLPI (o 401 do GLPI com senha errada e 200/resposta de inventário com a correta provam; se o GLPI responder "Authorization header required" mesmo com credencial, o proxy/PHP está descartando o cabeçalho); (b) `remote_ip` enxerga o IP real do cliente e não o do proxy/Cloudflare (teste de fora com origem permitida → passa, origem fora da lista → 403; se tudo vier do mesmo IP interno, a lista não está restringindo nada — configurar `trusted_proxies`/`client_ip_headers` antes). Conferir de fora: sem credencial 401; do IP permitido com credencial, resposta do GLPI com `enabled_inventory` ainda 0 (inventário desligado). Só então `enabled_inventory=1`, pelo gate do §5.

Rollback: restaurar o `Caddyfile` do backup, `caddy reload`, e `enabled_inventory=0`. A rota fora do ar volta a responder 302 do SSO.
