# Wazuh R3a: provisionamento da VPS (single-node)

**Estado:** só código. Nada aplicado, nenhuma credencial usada, nenhum servidor tocado. A VPS `homol` **não é tocada** por nada aqui: segue como origem dos agentes até o GO da migração.
Base: [dimensionamento](../specs/wazuh-r3a-dimensionamento.md) (opção B aprovada em 06/11/2026: Cloud VPS 12, 12 vCPU / 48 GB / 400 GB, 24 meses), [política SOC](../specs/soc-attendance-policy.md), [runbook Wazuh](../../infra/docs/runbooks/wazuh.md).

## Peças

- Terraform: `contabo_instance.wazuh_r3a` (`infra/terraform/main.tf`), criado só quando `var.wazuh_r3a != null`; `prevent_destroy`, sem senha nem `user_data`; output `wazuh_r3a_ipv4`.
- Ansible: `playbooks/wazuh-hub.yml` = role `common` (SSH key-only, UFW, fail2ban) + role `wazuh` (`infra/ansible/roles/wazuh`): instalador oficial `wazuh-install.sh -a` da versão 4.14.10 com sha256 fixado, pacotes em `hold`, UFW, retenção ISM.
- Portas: 1514/1515 só das origens em `wazuh_agent_sources`; 55000 (API) e 443 (dashboard) só da tailnet (`100.64.0.0/10`); indexer 9200 só em `127.0.0.1`.

## Passos (nesta ordem)

1. **Descobrir os ids, só leitura** (sem escrever na conta): `product_id` de "Cloud VPS 12" na tabela da documentação da API (<https://api.contabo.com/>, `Product IDs`; em 06/11 constava `V156`, que é o mesmo da `zabbix_uat`, **confirmar antes de usar**); `image_id` do Ubuntu 24.04 e o `secretId` da chave pública (**tem de ser a chave que corresponde a `NESS_AGENT_KEY`, isto é, `admin_ssh_key` em `group_vars/all.yml`**, senão o Ansible não entra) no CLI `app/cli/contabo` ou `GET /v1/compute/images` e `GET /v1/secrets`.
2. Criar `infra/terraform/environments/wazuh-r3a.tfvars` (local, não versionar) com `wazuh_r3a = { product_id, image_id, ssh_key_ids = [<secretId>], period = 24 }`. Só ids, nenhum segredo; o `period` não tem default (escolha deliberada). O arquivo está no `.gitignore`. A documentação do provider lista prazos 1/3/6/12 e a API da Contabo lista 1/12/24: a aceitação de `period = 24` **não está verificada**; se o apply for rejeitado, nada é criado (e nada é cobrado).
3. `infra/bin/tf plan -var-file=environments/prod.tfvars -var-file=environments/wazuh-r3a.tfvars -out=prod.tfplan`; guard: `infra/bin/tf show -json prod.tfplan | infra/scripts/tf-plan-guard.sh -`. O plano deve mostrar **só** `contabo_instance.wazuh_r3a` a criar e as outras 3 VPS sem mudança.
4. **Pedir o OK explícito do Ricardo** com o plano à vista (custo recorrente, 24 meses). Sem OK, parar aqui.
5. `infra/bin/tf apply prod.tfplan`; anotar o IP (`wazuh_r3a_ipv4`) e preencher o host em `wazuh_hubs` no inventário (PR próprio).
6. Baseline + Wazuh (1ª vez como `admin`, depois só `ness_admin`): comando no cabeçalho de `playbooks/wazuh-hub.yml`, com `--check` antes. Exige `NESS_AGENT_KEY` no ambiente e as duas decisões abaixo por `-e`.
6b. Entrar a VPS na tailnet (manual, auth key do Psono; o código não instala o Tailscale). Sem isso, 443 e 55000 ficam inacessíveis (só a tailnet tem regra).
7. Guardar no Psono a senha do `admin` do Wazuh, que o instalador gera em `/root/wazuh-install/wazuh-install-files.tar` (root, 0600). Sem imprimir: `ssh ... 'sudo tar -xOf /root/wazuh-install/wazuh-install-files.tar wazuh-install-files/wazuh-passwords.txt'` direto para o cofre/clipboard, ou, para o passo 8, `read -rs WAZUH_ADMIN_PASSWORD; export WAZUH_ADMIN_PASSWORD` (cole do cofre). Depois de salvar e conferir no cofre, **apagar o tar da VPS** (`sudo shred -u /root/wazuh-install/wazuh-install-files.tar`); ele guarda também os certificados, então só apague com o cofre confirmado.
8. Retenção: com `WAZUH_ADMIN_PASSWORD` no ambiente, rodar o playbook com `--tags retention`.
9. **Primeira migração de agente: pedir o OK do Ricardo.** Piloto com 1 agente interno, em observation mode (sem ticket, IA ou notificação), antes de qualquer lote. A integração Wazuh → Hub continua desligada.

## Validação

- `terraform plan` seguinte sem diferença; `ansible-playbook ... --check` com `changed=0` na segunda execução, **exceto** a tag `retention` (o PUT da política sempre reporta `changed`).
- Na VPS: `ufw status` só com SSH, 1514/1515, 55000 e 443 (tailnet); `ss -tlnp` com 9200 em `127.0.0.1`; de fora da tailnet, 443/55000/9200 fecham.
- `systemctl is-active wazuh-manager wazuh-indexer wazuh-dashboard` = `active`; `/var/ossec/bin/wazuh-control status`; dashboard responde pela tailnet.
- `GET _plugins/_ism/policies/ness-wazuh-retention` devolve os dias decididos.
- Agente piloto aparece em `agent_control -l` e gera alerta; regras de `infra/wazuh/local_rules_noise.xml` aplicadas pelo [runbook Wazuh](../../infra/docs/runbooks/wazuh.md).

## Atualizar pacotes em hold

`wazuh-manager`, `wazuh-indexer`, `wazuh-dashboard` e `filebeat` ficam em `hold`, para o `apt upgrade` não mexer no Wazuh. Para subir de versão: ler as notas da versão, fazer snapshot/backup, `sudo apt-mark unhold <pacotes>`, `sudo apt-get install --only-upgrade <pacotes>` (ordem: indexer, manager, filebeat, dashboard) e `apt-mark hold` de novo. Atualizar também `wazuh_version`/`wazuh_install_sha256` no código, em PR.

## Rollback

- Antes do apply: nada a desfazer. Depois: o `prevent_destroy` impede `destroy` acidental; para retirar, PR próprio que remove `prevent_destroy`, `plan -destroy`, `tf-plan-guard.sh` confirmando só `wazuh_r3a`, e OK do Ricardo ([safe destruction](../../infra/docs/iac.md)). Contrato de 24 meses: cancelar não devolve o que já foi pago.
- Falha no Ansible: `wazuh-install.sh -u` na VPS nova (apaga só ela). Agentes migrados: apontar de volta para a `homol`, que não foi alterada.

## Decisões ainda pendentes (do Ricardo; sem default no código)

- **Retenção** pesquisável do indexer (`wazuh_indexer_retention_days`: 30, 90 ou outra) e do bruto arquivado.
- **Origem dos agentes** (`wazuh_agent_sources`): internet, VPN ou sonda por cliente.
- **OT:** janela retrospectiva (teto de 24 h), banda, capacidade e retenção; sem dado de OT na `homol`.
- **Capacidade:** nº de agentes (624 é premissa), limpeza dos desconectados, disco extra se o volume voltar a 6 M alertas/dia.
- **Modalidade/operador** dos 9 vínculos de grupo; revisor da amostra semanal.
- Backup/snapshot do indexer (destino e frequência): não definido aqui.

## Não verificado

`product_id` e `image_id` reais; SO da imagem Ubuntu 24.04 na Contabo; aceitação de `period = 24` (provider 1/3/6/12 vs. API 1/12/24); execução real do Ansible (só `--syntax-check` e `ansible-lint`).
