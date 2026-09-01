# Authentik como hub SSO — Google e aprovação de externos

Data: 2026-09-01

## Modelo de acesso

- Usuários Google com e-mail `@ness.com.br` podem criar a conta no Authentik no primeiro acesso.
- Usuários Google externos não podem criar uma conta espontaneamente.
- Um externo somente autentica quando existe previamente no Authentik, com o mesmo e-mail do Google, e pertence ao grupo `SSO-External-Approved`.
- O grupo `SSO-External-Approved` autoriza somente a entrada no hub. Ele não concede acesso direto a nenhuma aplicação.
- Cada aplicação deve ter seus próprios grupos, por exemplo `APP-Zabbix-Users`, `APP-GLPI-Users` e `APP-Cofre-Users`.

## Aprovar um usuário externo

1. Confirme com o responsável da aplicação qual acesso o externo deve receber e por quanto tempo.
2. No Authentik, abra **Directory > Users** e crie um usuário ativo com:
   - e-mail exatamente igual ao e-mail usado na conta Google;
   - username igual ao e-mail;
   - sem privilégios administrativos.
3. Adicione o usuário ao grupo `SSO-External-Approved`.
4. Adicione o usuário somente aos grupos das aplicações aprovadas.
5. Se o cliente OAuth do Google estiver em modo **Testing**, adicione o mesmo e-mail em **Google Auth Platform > Público-alvo > Usuários de teste**.
6. Peça ao usuário para abrir `https://sso.ness.com.br` e selecionar **Google ness.OS**.

No primeiro login, o Authentik vincula a identidade Google ao usuário preexistente pelo e-mail exato.

## Revogar um usuário externo

1. Remova o usuário dos grupos das aplicações.
2. Remova-o de `SSO-External-Approved`.
3. Desative o usuário quando o contrato ou atendimento terminar.
4. Revogue sessões e conexões da fonte Google se o desligamento exigir efeito imediato.
5. Remova-o também dos usuários de teste no Google, quando aplicável.

## Controles configurados

- Fonte Google: habilitada e visível no login.
- Correspondência de usuário: e-mail idêntico (`email_link`).
- Enrollment Google: permitido somente para `@ness.com.br`.
- Autenticação Google: permitida para `@ness.com.br` ou membros de `SSO-External-Approved`.
- Login local por senha: preservado para contingência.
- Grupo de externos: não administrativo e sem vínculo direto com aplicações.

## Regra de segurança

Nunca vincular `SSO-External-Approved` diretamente a uma aplicação. O grupo representa aprovação para usar o hub, não autorização para consumir todos os serviços conectados ao SSO.
