# Cavan Google Workspace — habilitação do coletor de auditoria

**Executor:** Ismael Araújo (ness.), autenticado como Super Admin da Cavan.
**Objetivo:** liberar auditoria somente leitura para o ness.OS.

## Limites do piloto

- Tenant: `cavan.com.br`, abrangendo Matriz e unidades fabris.
- Escopo único: `https://www.googleapis.com/auth/admin.reports.audit.readonly`.
- Não habilitar Alert Center neste piloto: o escopo disponível permite escrita.
- Não criar chave nem colar credencial no repositório, chat, e-mail ou ticket.

## Procedimento

1. Acessar o Google Cloud Console com a conta Super Admin e criar o projeto
   `ness-os-cavan-workspace` (ou confirmar um projeto Cavan já destinado a
   integrações de segurança).
2. Em APIs e Serviços, habilitar apenas **Admin SDK API**.
3. Em Contas de Serviço, criar `ness-os-workspace-reader` com descrição
   `Leitura de auditoria Google Workspace para ness.OS`.
4. Na conta de serviço, habilitar **Domain-wide delegation** e anotar apenas o
   **OAuth Client ID**. Não baixar chave JSON ainda.
5. No Admin Console, ir a Segurança → Controles de API → Gerenciar delegação
   em todo o domínio e adicionar o OAuth Client ID com o escopo único acima.
6. Criar uma chave JSON exclusivamente se a etapa 5 tiver sido concluída.
   Ela deve ir diretamente ao cofre do host AIOps, com proprietário root e
   permissão `0600`; não deve permanecer em Downloads.
7. Informar à equipe ness. somente: ID do projeto, e-mail da conta de serviço,
   OAuth Client ID e confirmação da delegação. Não informar senha, chave JSON
   ou dados pessoais.

## Validação de aceite

- O conector consegue listar auditorias de `login`, `admin` e `token`.
- O conector não possui permissão de criar, alterar ou excluir recursos do
  Google Workspace.
- Logs enviados ao SecOps contêm metadados de auditoria, não conteúdo de
  e-mail, Drive ou tokens.

## Referências

- Reports API: <https://developers.google.com/workspace/admin/reports/reference/rest/v1/activities/list>
- Escopos de auditoria: <https://developers.google.com/workspace/admin/reports/auth>
- Delegação em todo o domínio: <https://support.google.com/a/answer/162106>
