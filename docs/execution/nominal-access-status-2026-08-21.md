# Acessos nominais — estado em 21/08/2026

## Resultado comprovado

As duas VPS aceitam chave SSH para `ness_admin`, com UID/GID próprios e participação no grupo `sudo`. `sudo -n` passou. A configuração efetiva do SSH retorna `PermitRootLogin no`, `PasswordAuthentication no` e `KbdInteractiveAuthentication no` em ambas.

No Authentik existem e estão ativas as identidades:

| Pessoa | Identidade | Grupos atuais | Decisão |
|---|---|---|---|
| Ricardo Esper | `resper` | `admin` | administração cotidiana limitada; break-glass separado |
| Rogério Salerno | `rsalerno` | `gestao`, `noc`, `usuarios` | administração por domínio, sem superadmin global |
| Ismael Araujo | `iaraujo` | `gestao`, `noc`, `usuarios` | administração por domínio, sem superadmin global |
| Agnaldo Silva | `agsilva` | `gestao`, `noc`, `usuarios` | manter sem promoção global durante observação |

A conta `akadmin` ainda pertence ao grupo superusuário `authentik Admins`. Ela deve ser tratada como contingência até a definição e o teste das duas identidades break-glass; não deve ser usada no cotidiano.

## Pendências que exigem ação humana

- Cada responsável deve concluir um login real e cadastrar MFA; não é correto o operador cadastrar o segundo fator em nome da pessoa.
- O Hub provisiona o usuário local no primeiro login OIDC. Hoje a tabela nominal contém apenas a conta local genérica, que permanece como contingência até dois logins OIDC serem testados.
- O GLPI tem duplicatas para as quatro identidades, decorrentes de fontes de autenticação distintas. A reconciliação deve preservar histórico e ser feita pela interface/API suportada, nunca por `UPDATE`/`DELETE` direto.
- O Zabbix ainda possui 14 Super Admins. A redução ocorrerá na janela, após owners e duas identidades break-glass serem confirmados, conforme [`zabbix-security-access-audit-2026-08-21.md`](zabbix-security-access-audit-2026-08-21.md).

## Aceite por pessoa

Para considerar uma identidade concluída em cada aplicação, registrar: login, MFA, papel positivo esperado, tentativa negativa de uma função não permitida, logout, revogação de sessão e recuperação/break-glass. Evidências não devem conter senha, token, QR code ou código de recuperação.
