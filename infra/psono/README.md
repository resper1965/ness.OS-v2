# Psono Community — stack de PoC do ness.os

Domínio aprovado: `cofre.ness.com.br`.

O registro legado `vault.ness.com.br` não faz parte desta implantação. Ele deve
permanecer sem uso até sua retirada ser autorizada separadamente; não há redirect
automático entre os dois endereços.

## Branding

O cliente usa os ativos aprovados em `branding/` e gera `logo`, `logo_inverse`
e tema Material UI no `config.json`. A assinatura visual segue a skill
`ness-branding`: caixa baixa, lettering preto ou branco, BlueDot `#00ade8`, grid
8 px, sombra suave, easing e fallback para movimento reduzido.

O favicon original do Psono permanece ativo até existir um favicon oficial
aprovado. Não substituir os ativos por imagens geradas, redesenhadas ou com
fontes substitutas.

O serviço web também participa da rede externa indicada por
`PSONO_SHARED_EDGE_NETWORK`. Essa rede é administrada pelo stack do proxy e
precisa existir antes de executar o Compose.

Esta stack é isolada e opt-in. Ela não deve ser executada nas VPS atuais do
Zabbix ou do Hub e não pode receber credenciais reais antes do gate descrito em
`docs/execution/psono-community-poc.md`.

Exceção temporária aprovada em 31/08/2026: a composição
`docker-compose.aiops.yml` conecta somente o serviço Psono ao Caddy da AIOps e
aplica limites de recursos. O estado e o rollback estão registrados em
`docs/execution/psono-aiops-temporary-2026-08-31.md`. Esta exceção não autoriza
a entrada de credenciais reais antes dos gates da PoC.

## Dependências antes do primeiro deploy

- VPS dedicada aprovada e provisionada;
- subdomínio e DNS definidos;
- domínio verificado no Resend e chave runtime disponível;
- dois responsáveis por recovery/emergency access;
- credencial S3 exclusiva ou prefixo formalmente aprovado;
- `/etc/ness-os/psono.env` root:root 0600;
- `/etc/ness-os/backup-s3.env` root:root 0600.

## Implantação expand-only

1. Copiar esta pasta para `/opt/ness-os-psono`.
2. Instalar Docker, Compose, Restic, PostgreSQL client e Caddy via a stack.
3. Gerar as chaves pelo comando oficial `generateserverkeys` do Psono.
4. Preencher `/etc/ness-os/psono.env` sem registrar valores em shell history.
5. Executar `sudo scripts/render-config.sh`; ele cria `settings.yaml`, `config.json`
   e um `postgres.env` mínimo, todos com modo `0600`.
6. Validar `docker compose config --quiet` e `caddy validate`.
7. Subir banco e Psono; somente depois subir Caddy.
8. Criar quatro usuários descartáveis e executar todo o checklist da PoC.
9. Executar backup, restore em host vazio e teste de atualização/rollback.

Não há contração automática: arquivos root-only antigos e credenciais existentes
somente serão revogados depois que dois custodians comprovarem recuperação e o
restore do cofre passar.
