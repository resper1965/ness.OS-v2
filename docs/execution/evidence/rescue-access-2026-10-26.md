# Restauração de acesso e indisponibilidade — 2026-10-26

Registro do ciclo de Rescue System que devolveu acesso administrativo às VPS,
da indisponibilidade observada durante os trabalhos e do que permanece
pendente. Não aprova gate, release ou corte.

## Motivo

Nenhuma chave privada estava disponível no host de operação, e os três hosts
recusavam autenticação por senha (`passwordauthentication no`). O acesso foi
recuperado pelo Rescue System da Contabo, que não usa o `sshd` do disco.

## Hosts

| Instância | Nome | Papel | IP | Rescue | Chave |
|---|---|---|---|---|---|
| `vmi3532557` | `ness-os-zabbix-prd-01` | UAT Zabbix | `169.58.234.9` | sim | instalada |
| `vmi3409271` | `aiops` | Hub AIOps | `144.91.115.242` | sim | **pendente** |
| `vmi3409070` | `ninfraops-zabbix` | Zabbix produção | `144.91.72.202` | sim | instalada |
| `vmi3509035` | `npentest` | fora do escopo ness.OS | `169.58.178.187` | sim | não tratar |

Instalação pelo bloco documentado em `infra/docs/agent-access-runbook.md`.
Confere com o observado: disco `/dev/sda1`, usuário `ness_admin` com UID/GID
`1000:1000`, `authorized_keys` preservando a chave anterior (212 bytes após a
inclusão).

## Indisponibilidade observada

Durante o ciclo, os hosts ficaram bootados no rescue e os serviços do disco
pararam.

**Hub AIOps.** Enquanto o host esteve em rescue, `hub`, `api`, `sso`,
`n-ticket`, `n8n` e `waba` não responderam. Após o retorno ao disco, Hub e API
subiram de imediato, mas Authentik não: `sso`, `n-ticket` e `n8n` responderam
503 e `waba` 502. A recuperação ocorreu de forma autônoma com a subida dos
containers; nenhuma intervenção manual foi necessária. Estado final verificado:
`hub` 200, `api` 401, `sso` 302, `n-ticket` 302, `n8n` 302, `waba` 200,
`cofre` 200.

**Zabbix produção.** O host ficou em rescue, com apenas a porta 22 aberta pela
imagem de rescue (`OpenSSH_9.2p1 Debian-2+deb12u7`). As portas 2222, 80, 443,
10051 e 10050 ficaram fechadas, e `zabbix.ness.com.br` não respondia. Isso
interrompeu a coleta de clientes durante o período. Após o reboot: `zabbix-server`
7.0.27 ativo, apache2 e mariadb ativos, 443 e 10051 abertas, três conexões
estabelecidas na 10051 e log corrente, confirmando retomada da coleta.

## Estado após a recuperação

| Host | Serviços | Observação |
|---|---|---|
| UAT `zbx-prd-01` | `zabbix-server` inactive/masked, agent2 ativo, mariadb ativo | isolada, sem coleta, coerente com o destino de UAT |
| Zabbix produção `zabbix-srv01` | todos ativos | 1,2 TB, 306 GB usados; timers de backup local 22:00 e Object Storage 05:30 com execução no dia |
| AIOps `vmi3409271` | stack completa respondendo | chave do agente instalada às 18h; 12 containers de pé |

## Achados

1. O `Restart=unless-stopped` dos containers foi suficiente para recuperar o
   Authentik sem intervenção, mas a janela de indisponibilidade de `sso`,
   `n-ticket` e `n8n` foi maior que a de Hub e API. Não há dependência explícita
   declarada entre eles no Compose.
2. `zabbix_server` emite `ERROR: Please change {$FGATE.API.TOKEN} macro to the
   proper value` para os hosts FortiGate. Falha pré-existente, não relacionada
   ao rescue; os itens de firewall permanecem sem coleta válida.
3. O acesso root ao MariaDB de produção exige senha e não está disponível por
   `unix_socket`, então a verificação de dados foi feita por sinais indiretos
   (conexões na 10051 e log do servidor). Não se buscou a credencial.
4. Manter uma VPS de produção em rescue por engano interrompe monitoração de
   clientes. O painel não distingue com clareza "rescue ativo" de "em execução"
   na listagem; a evidência técnica é a porta 22 com a imagem `deb12u7` e as
   portas de serviço fechadas.

5. O `authorized_keys` da AIOps não terminava em quebra de linha. O bloco de
   instalação original usava `grep -qF` e `echo >>`, então a chave nova foi
   concatenada na última linha existente: uma única linha de 210 bytes
   (`102 + 108`), inválida para o `sshd`. O sintoma engana — a chave aparece no
   arquivo, com dono e permissão corretos, e a autenticação continua recusada.
   Corrigido com `grep -qxF` e quebra de linha garantida; runbook atualizado. A
   chave foi escrita temporariamente em `root` como via de recuperação e
   removida depois, preservando as quatro chaves preexistentes.

## Pendente

- O host de origem da chave é a KVM8 da Hostinger (`148.230.77.242`), transitória
  no plano de capacidade. Antes do descomissionamento, repetir o runbook a
  partir de um host permanente.
- As entradas instaladas não têm restrição `from=`. Aplicar na rotação, junto
  com o host permanente.

## Limite

Verificação pontual realizada em 26/10/2026. Não substitui UAT nominal, não
aprova F0–F8 e não autoriza deploy ou mutação de produção.
