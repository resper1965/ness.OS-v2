# Ação requerida — Contabo Object Storage

## Descoberta no painel — 24/08/2026

Não é necessária nova contratação. O painel confirmou:

- storage `ninfraops - Zabbix Store` em estado **Pronto**;
- região **European Union**;
- capacidade adquirida **250 GB**;
- autoscaling **desativado**;
- bucket `zabbix-storage` existente e vazio;
- acesso público do bucket estava marcado como **Ativo**;
- na inspeção inicial, não havia usuário no novo gerenciamento de usuários Contabo.

## Ações autorizadas e concluídas

Em 24/08/2026, Ricardo Esper autorizou e a interface confirmou:

1. bucket privado `ness-os-backup-eu-2026` criado no storage existente; acesso público `Inativo`;
2. acesso público do bucket vazio `zabbix-storage` desativado; estado final `Inativo`;
3. usuário `resper@bekaa.eu` registrado como `S3 Read and Write`, sem funções de faturamento/administração e com 2FA; a conta já existia e o painel agora a mostra como **Habilitado**;
4. usuário nominal `iaraujo@ness.com.br` criado como `S3 Read and Write`, sem funções de faturamento/administração, ativo e com 2FA obrigatório.

O usuário de Ismael foi ativado e o painel o mostra como **Habilitado**, com 2FA **Habilitado**. Em sessão isolada como `iaraujo@ness.com.br`, o segredo S3 foi regenerado com autorização explícita, capturado sem exibição e armazenado fora do repositório em arquivos locais `0600`. A credencial administrativa de Ricardo não foi reutilizada. A conta `resper@bekaa.eu` será mantida até a credencial nominal de Ismael ser validada por upload e restore; sua remoção será uma mudança posterior e explícita.

O e-mail para definição de senha foi reenviado pelo painel em 24/08/2026, com confirmação **Email enviado com sucesso para definir a senha**; Ismael concluiu a ativação posteriormente.

### Hardening identificado

A conta administrativa principal usada na inspeção aparece com 2FA inativo. A ativação deve ser feita em uma etapa assistida, preservando códigos de recuperação no cofre, antes de considerar o acesso administrativo regularizado. Nenhuma alteração de autenticação foi feita automaticamente.

Não é necessário copiar senha, token ou chave para o chat.

## O que o Codex fará depois

1. [Concluído] Ativar Ismael com MFA e obter a credencial S3 dedicada sem reutilizar credencial administrativa principal.
2. [Preparado localmente] Gerar uma senha Restic forte e armazenar os valores em `/etc/ness-os/backup-s3.env`, `root:root`, modo `0600` em cada host:

   - `CONTABO_S3_ENDPOINT`;
   - `CONTABO_S3_BUCKET`;
   - `AWS_ACCESS_KEY_ID`;
   - `AWS_SECRET_ACCESS_KEY`;
   - `RESTIC_PASSWORD`.

3. Instalar Restic oficial e o tooling versionado nas VPS Zabbix e AIOps. AIOps está bloqueada porque nenhuma chave nominal disponível autentica `ness_admin`; Zabbix aguarda a janela 22:00–00:00 BRT.
4. Inicializar prefixos separados `ness-os/<host>/zabbix` e `ness-os/<host>/aiops`.
5. Enviar somente backups `COMPLETED` com `SHA256SUMS` válido.
6. Executar `restic check`, restaurar uma amostra em isolamento e comparar checksums.
7. Ativar os timers recorrentes e atualizar as evidências do Gate 0.

## Alternativa por API

Se for preferível não usar o painel, fornecer uma nova credencial OAuth da API Contabo por arquivo local protegido. A API de gestão já consegue identificar o Object Storage existente; as credenciais de dados S3 são diferentes e são obtidas na API de usuários. As credenciais OAuth preservadas atualmente não autenticam e não devem ser reutilizadas.

A documentação atual confirma que a credencial S3 é vinculada a um usuário e consultada por `GET /v1/users/{userId}/object-storages/credentials`. A criação do usuário não permite definir senha ou segredo: o próprio usuário precisa concluir essa etapa. Não foi encontrada uma credencial de serviço independente do usuário que preserve o mesmo modelo nominal; portanto, o Gate 0 não usará a conta antiga como atalho.

## Critério de encerramento

O Gate 0 fecha somente quando houver, para Zabbix e AIOps: upload criptografado, `restic check`, restauração isolada, checksum aprovado e timer habilitado. A simples contratação do espaço não encerra o gate.
