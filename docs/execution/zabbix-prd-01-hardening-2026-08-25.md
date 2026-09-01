# Zabbix PRD-01 — hardening e UAT local (2026-08-25)

## Controles comprovados

- UFW ativo, política padrão `deny incoming`; somente SSH/TCP 22 permitido.
- MariaDB limitado a `127.0.0.1:3306`.
- Frontend Apache limitado a `127.0.0.1:8080`; não há HTTP/HTTPS público.
- `zabbix-server` inativo e mascarado; `zabbix-agent2` desabilitado.
- Fail2ban e auditd ativos.
- SSH com root, senha e teclado interativo desabilitados; acesso apenas para
  `ness_admin` por chave.
- SSH endurecido para UAT: X11 e agent forwarding desabilitados; somente
  encaminhamento local para `127.0.0.1:8080` permitido.
- Frontend e configuração Restic protegidos por permissões de menor privilégio.

## Backup externo

O Restic 0.19.1 validado foi instalado e o repositório exclusivo
`zbx-prd-01/zabbix` foi inicializado com `restic check` sem erros. Os timers de
backup local e de cópia externa estão instalados, porém deliberadamente
desabilitados enquanto a UAT mantém o Zabbix Server mascarado. O primeiro
conjunto offline `COMPLETED` será usado para comprovar o ciclo completo.

## Controle externo confirmado

A VNC da instância foi desabilitada no painel Contabo em 26/08/2026, após a
comprovação do acesso SSH nominal. O canal de recuperação permanece pela
console do provedor mediante nova habilitação controlada, se necessária.
