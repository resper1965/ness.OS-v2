# Zabbix PRD-01 — UAT local segura (2026-08-25)

## Estado aprovado

- Frontend Zabbix configurado contra o banco restaurado.
- Apache ativo somente em `127.0.0.1:8080`; UFW não possui regra HTTP/HTTPS.
- Configuração do frontend protegida como `root:www-data` e modo `0640`.
- `zabbix-server` permanece inativo e mascarado; não há listener em `10051`.
- Ações, mídias e conectores permanecem neutralizados na base UAT.

## Acesso para UAT

Em estação autorizada, usar túnel SSH, sem expor a porta web:

```bash
ssh -N -L 8080:127.0.0.1:8080 ness_admin@169.58.234.9
```

Depois, abrir `http://127.0.0.1:8080/zabbix/` localmente. A autenticação deve
ser feita apenas com uma identidade de UAT autorizada; não registrar senhas,
tokens ou sessões em documentação.

## Gates ainda pendentes

1. Homologar identidade centralizada (Authentik), MFA, logout e revogação.
2. Exportar rollback antes de alterações de templates/hosts.
3. Executar piloto FortiGate sem habilitar ações, mídias ou conectores.
4. Somente depois decidir o início temporário e restrito do Zabbix Server para
   coleta UAT; não há autorização de corte para produção neste documento.

## Ajuste pós-acesso (2026-08-26)

O locale `pt_BR.UTF-8` foi instalado e gerado no web host; Apache foi
reiniciado apenas na interface local. Isso remove o alerta de tradução sem
iniciar o Zabbix Server ou alterar a coleta.
