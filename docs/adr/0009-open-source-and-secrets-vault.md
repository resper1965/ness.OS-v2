# ADR 0009 — Open source e cofre de segredos

- Estado: aceito com emenda Community-only em 21/08/2026
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

O ecossistema ainda não possui cofre corporativo. Credenciais emergenciais rotacionadas estão temporariamente em arquivos acessíveis apenas por root nas próprias VPS. Essa contenção não resolve compartilhamento controlado, sucessão, auditoria nem recuperação após perda das máquinas.

Também foi definida a preferência obrigatória por componentes open source em todo o projeto.

## Decisão

1. Todo componente novo deve possuir licença open source compatível e código-fonte auditável.
2. O cofre humano será integralmente Community e autohospedado em uma terceira VPS, fora dos domínios de falha do Zabbix e do AIOps.
3. Psono Community foi escolhido como cofre humano do ness.OS por oferecer recovery code e emergency code sem licença comercial. A promoção depende de prova de conceito; Passbolt Community permanece somente como contingência se o PoC reprovar. A decisão comparativa está em [`../evaluations/community-vault-comparison.md`](../evaluations/community-vault-comparison.md).
4. Segredos de automação serão tratados por SOPS/age; não serão copiados indiscriminadamente para variáveis, Compose ou repositório em texto claro.
5. Não será adotado SaaS proprietário, edição Business/Enterprise nem um cofre instalado em qualquer uma das duas VPS atuais.

## Arquitetura mínima

- Debian 13 estável, 2 vCPU, 4 GB RAM e 40 GB de armazenamento.
- Banco compatível com o produto Community selecionado, NTP funcional, SMTP dedicado e TLS público válido.
- Apenas HTTPS público; HTTP somente para redirecionamento/ACME. SSH por chave e origem administrativa restrita.
- MFA local obrigatório para todos; SSO/LDAP/OIDC/SAML não será presumido porque não está disponível nas edições Community avaliadas.
- Dois responsáveis capazes de recuperar o cofre; nenhum segredo crítico depende de uma única pessoa.
- Backup diário criptografado e externo contendo banco, chaves GPG do servidor, configuração e certificados; restore testado mensalmente.
- Monitoramento externo, atualização controlada por versão e janela registrada.

## Estrutura inicial de acesso

- `infraestrutura`: VPS, DNS, firewall e provedores.
- `aplicacoes`: Zabbix, GLPI, Authentik, Hub, n8n e Evolution.
- `integracoes`: APIs, webhooks, RMM e notificações.
- `clientes`: coleções segregadas quando houver credenciais de cliente.
- `break-glass`: acesso excepcional, limitado a Ricardo e um substituto formal, com recovery/emergency material offline e procedimento registrado.

## Consequências

- O Gate 0 não fecha completamente antes do provisionamento da terceira VPS e da migração das credenciais temporárias.
- A operação terá mais um serviço crítico para atualizar, monitorar, copiar e restaurar.
- SSO/Auth­entik não pode ser o único caminho de acesso: deve existir recuperação local documentada para falha do IdP.
- As edições Community avaliadas não fornecem auditoria granular e SSO corporativo. Logs externos são controles compensatórios parciais, não equivalentes; a lacuna deve permanecer explícita no risco aceito.

## Referências

- [Passbolt CE — AGPLv3](https://github.com/passbolt/passbolt_api)
- [Comparação de edições e licença](https://www.passbolt.com/pricing/pro)
- [Requisitos mínimos](https://www.passbolt.com/docs/hosting/requirements/)
- [Backup e recuperação](https://www.passbolt.com/docs/hosting/maintenance/backup/)
