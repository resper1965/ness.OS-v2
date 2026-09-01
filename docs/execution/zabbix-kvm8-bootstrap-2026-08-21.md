# Bootstrap da KVM8 de transmutação Zabbix — 21/08/2026

## Resultado

A Hostinger KVM8 foi confirmada pela API, reinstalada e endurecida como staging temporário do ness.OS. A VM está acessível somente por `ness_admin` com chave dedicada; root e autenticação SSH por senha estão bloqueados. Nenhum componente Zabbix de produção foi alterado.

## Identificação confirmada

| Campo | Valor |
|---|---|
| VM Hostinger | `1013444` |
| IPv4 | `148.230.77.242` |
| Plano | KVM8 |
| Capacidade | 8 vCPU, 32 GB RAM, 400 GB de disco |
| Imagem final | Debian 12, template `1031` |
| Hostname aplicado | `zabbix-transmutation` |
| Papel | staging efêmero e possível ponte operacional curta |

O inventário anterior mostrou dois backups automáticos pequenos, sem snapshot útil e sem firewall associado. A chave SSH antiga divergente não foi aceita. Após a autorização explícita de descarte, houve um primeiro reimage Ubuntu para validar o bootstrap e, ao confirmar que a produção usa Debian 12, um segundo reimage para igualar o SO e eliminar uma variável da restauração. A ação final `110603037` terminou em `success` e uma nova host key foi registrada.

## Controles aplicados

- chave ED25519 dedicada de acesso, fingerprint `SHA256:P2NzlH4bzJT4xs6le/CpNvJ7jPoTRMB5hdB6wA4KPtI`;
- usuário nominal `ness_admin` com `sudo` e nova sessão validada antes do bloqueio do root;
- `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `AllowUsers ness_admin` confirmados pela configuração efetiva do sshd;
- UFW: negar entrada por padrão, permitir saída e aceitar somente TCP/22;
- firewall Hostinger dedicado `349173`, sincronizado, com apenas TCP/22 e sem associação ao grupo legado “Permissivo Total”;
- Fail2ban, auditd, UFW, SSH e sincronização de tempo ativos;
- fuso `America/Sao_Paulo`, NTP ativo;
- atualizações aplicadas e reboot no kernel `6.1.0-52-amd64`;
- swap persistente de 8 GiB com `vm.swappiness=10`;
- sysctls básicos de proteção de kernel e filesystem;
- nenhuma unit systemd falha e nenhuma porta pública de aplicação aberta.

## Evidências de consistência

- bootstrap local/remoto: `60b527893ab8098ecf826972e02f038c6358a554b6f474350ac9a86c0ff9cda6`;
- preparação do runtime local/remoto: `fffa28fef135db805e5ab6bf672712074223a9ef534efd9bdc28f623c95f9877`;
- restore nativo local/remoto após fail-closed e gravação atômica de evidência: `83bc4b519b41bad84e3d345d9afe8bdeaaa036ad54e10e0abcbfbc6f9ca82ecb`;
- verificador pós-restore local/remoto: `424e42e4d0b3cb51646055e06ef63d52464153b3a02d9d430890ec2eed324d1c`;
- smoke sintético local/remoto: `0c84517859a3529541aa608cc03901ee58e65ad1692981771da6c6ea25c5a672`;
- transporte com checksum: `b7fa349754cb793dde7c2a3e134136eaeda360162e79905d867d005d1d7192b9`;
- host key ED25519 final: `SHA256:6CkaVGeOhXVUfzDZ7IKnX3OIo72Td+ZHz5Cjj1fnhig`;
- firewall Hostinger reassociado após o reimage: VM `1013444`, grupo `349173`, sincronização `110603946` em `success`, `is_synced=true`, somente TCP/22;
- disco após baseline: 387 GiB utilizáveis, 378 GiB livres;
- memória após baseline: 31 GiB, cerca de 30 GiB disponíveis;
- zero pacotes pendentes e nenhum reboot pendente após a baseline Debian.

O código idempotente está em [`../../infra/scripts/bootstrap-zabbix-transmutation-kvm8.sh`](../../infra/scripts/bootstrap-zabbix-transmutation-kvm8.sh), [`../../infra/scripts/prepare-zabbix-transmutation-runtime.sh`](../../infra/scripts/prepare-zabbix-transmutation-runtime.sh), [`../../infra/scripts/zabbix-kvm8-native-restore.sh`](../../infra/scripts/zabbix-kvm8-native-restore.sh) e [`../../infra/scripts/transfer-zabbix-backup-to-kvm8.sh`](../../infra/scripts/transfer-zabbix-backup-to-kvm8.sh).

## Runtime de restauração preparado

- SO igual à origem: Debian 12;
- Zabbix Server, frontend, Apache conf e Agent 2 fixados em `7.0.27`;
- MariaDB fixado em `10.11.18`, escutando somente `127.0.0.1:3306`;
- buffer pool 16 GiB, redo log 2 GiB e `max_allowed_packet=1G`;
- `zabbix-server` inativo e mascarado; Apache e Agent 2 inativos/desabilitados;
- isolamento systemd do futuro processo Zabbix com `IPAddressDeny=any` e `IPAddressAllow=localhost`;
- diretórios de entrada/evidência `700 root:root`;
- restore preparado para validar SHA-256/gzip, importar `dbzabbix`, neutralizar actions/media types/connectors, criar credencial staging aleatória root-only e registrar contagens/RTO sem iniciar o servidor.
- runner endurecido antes da restauração real para recusar também processo `zabbix_server` iniciado fora do systemd ou listener TCP/10051; qualquer falha após o início do restore aciona contenção fail-closed, interrompe processo eventual, tenta neutralizar os três canais e grava evidência `FAIL_CLOSED`.

Em 22/08/2026, após instalar essa revisão com hash local/remoto idêntico, a pré-validação confirmou MariaDB `active`, Zabbix Server `inactive/masked`, nenhum processo `zabbix_server` e nenhum listener TCP/10051.

### Smoke sintético

O schema oficial Zabbix 7.0.27 foi empacotado como um dump sintético e percorreu o mesmo restore automatizado. Resultado: 203 tabelas, 408 hosts/templates, 18.388 itens, 6.879 triggers, `dbversion=7000000`, zero canal ativo depois da neutralização, server `inactive/masked` e `restore=PASS` em 14 segundos. O dump, o banco e o usuário sintéticos foram removidos; somente a evidência root-only `restore-20260821T152532-0300.txt` foi preservada. O diretório de entrada voltou a ficar vazio para a carga real.

## Segredos e ações obrigatórias

A senha root inicial e o token Hostinger foram informados pelo chat e devem ser considerados expostos. A senha não é mais aceita por SSH; o token não foi gravado em arquivo/configuração e foi removido do ambiente após as consultas, mas continua válido no provedor até revogação.

- **urgente:** revogar no hPanel o token de API exposto;
- criar um token novo somente quando Psono/SOPS estiverem disponíveis e armazená-lo fora do repositório;
- não reutilizar a senha root informada em nenhum sistema;
- ao destruir a KVM8, remover também a public key Hostinger `563082` e a chave privada local dedicada.

## Restore real e próxima etapa técnica

O backup recorrente `20260822T121154-0300` foi validado e transferido com SHA-256 idêntico. O banco real permanece restaurado na KVM8: 203 tabelas, 674 hosts/templates, 60.250 itens, 24.520 triggers e `dbversion=7000000`, com zero actions/media/connectors ativos. O Zabbix Server continua inativo/mascarado, sem processo/listener ou conexão operacional; MariaDB permanece localhost-only.

A saída final do primeiro runner sofreu SIGPIPE e acionou corretamente o fail-closed. A validação independente direta passou e está em `post-restore-verification-20260822T154232-0300.txt`; o runner agora grava evidência atomicamente antes de imprimir. O banco e o dump serão mantidos para saneamento/transmutação. Não iniciar nem desmascarar o Zabbix Server antes dos critérios GO/NO-GO do checklist pós-restore.
