# Avaliação de cofre Community — Psono versus Passbolt

> Data: 21/08/2026
> Regra do projeto: somente edição Community/open source; recursos Business/Enterprise não podem compor requisito ou critério de aceite.

## Conclusão

Psono Community é uma alternativa real ao Passbolt Community e passa a ser o candidato recomendado para prova de conceito do ness.OS. A vantagem decisiva para o cenário atual é oferecer recuperação por código e acesso de emergência com espera, recursos relevantes para sucessão e break-glass sem depender de edição comercial.

O Passbolt Community permanece tecnicamente forte para compartilhamento de equipe, grupos, RBAC, API e CLI, mas a recuperação organizacional/escrow e o activity log pertencem à edição paga. Sem esses recursos, a perda da chave privada/recovery kit ou da passphrase de um usuário pode causar perda de segredos privados não compartilhados.

Nenhum dos dois atende integralmente a governança corporativa na edição Community: SSO com Authentik, provisionamento LDAP/OIDC/SAML e auditoria detalhada são recursos pagos. O projeto deve aceitar essa lacuna explicitamente ou selecionar no futuro outro produto integralmente comunitário que a cubra.

## Comparação Community-only

| Critério | Psono Community | Passbolt Community |
|---|---|---|
| Licença do núcleo | Apache 2.0 | AGPLv3 |
| Usuários | Ilimitados | Ilimitados |
| Self-hosted | Sim | Sim |
| Criptografia no cliente | Sim | Sim, OpenPGP/E2EE |
| Compartilhamento de equipe | Sim | Sim, com grupos/pastas e permissões granulares |
| MFA local | Sim, incluindo TOTP e opções de hardware conforme cliente/configuração | Sim |
| Aplicativos/browser | Web, extensões, desktop/mobile | Web, extensões, iOS/Android e desktop beta |
| API/automação | API disponível; CLI comunitária de terceiros | Open API e CLI oficial |
| Recuperação individual | Recovery code | Recovery kit/chave do usuário; escrow organizacional não está na CE |
| Acesso de emergência | Emergency code com espera e aviso | Não equivalente na CE; exige processo de compartilhamento/break-glass |
| SSO Authentik/OIDC/SAML | Não na CE | Não na CE |
| LDAP/diretório | Não na CE | Não na CE |
| Auditoria detalhada | Não na CE | Não na CE |
| Políticas/compliance central | Não na CE | Limitadas; políticas avançadas ficam na edição paga |
| Banco | PostgreSQL | MariaDB/MySQL ou PostgreSQL conforme implantação suportada |
| Implantação pequena | Pode usar combo CE, mas a arquitetura de produção oficial recomenda separar aplicação e banco | Uma VPS pequena é o desenho oficial mais simples |

## Riscos e controles compensatórios

1. Logs de Caddy, sistema, autenticação e Wazuh não substituem auditoria de leitura/alteração de cada segredo.
2. Sem SSO, o desligamento de usuário deve incluir checklist manual no cofre, revisão de grupos e rotação dos segredos acessados.
3. MFA local será obrigatório para todos; contas não podem reutilizar senha corporativa.
4. Psono recovery codes/emergency codes ou Passbolt recovery kits devem ser entregues e testados em cerimônia controlada, com cópia offline protegida.
5. Segredos críticos devem pertencer a grupos, nunca exclusivamente a uma pessoa.
6. Backups precisam incluir banco, configuração e todas as chaves estáveis do servidor; restauração deve ser testada antes de uso real.
7. O servidor permanece dedicado e fora dos domínios Zabbix, AIOps, Wazuh e phishing.

## Prova de conceito recomendada — Psono Community

- uma VPS dedicada de 2 vCPU, 4 GB RAM e 40 GB;
- Psono combo CE e PostgreSQL em contêineres/redes separados, sem fileserver inicialmente;
- Caddy/TLS, SMTP, NTP, MFA obrigatório e SSH nominal;
- quatro usuários descartáveis representando owner, administrador, operador e substituto;
- grupos `infraestrutura`, `aplicacoes`, `integracoes`, `clientes` e `break-glass`;
- testes de compartilhamento read/write, revogação, saída de usuário, recovery code e emergency code;
- backup criptografado externo e restauração em host vazio;
- teste de atualização e rollback;
- registro formal de que não existe auditoria granular nem SSO na CE.

## Critério para substituir Passbolt no plano

Psono Community será escolhido se a prova de conceito demonstrar recuperação, emergência, compartilhamento, revogação, mobile/browser, backup/restore e atualização sem perda de dados. Se falhar, o fallback permanece Passbolt Community com recovery kits obrigatórios e conta/grupo de custódia para todos os segredos críticos.

## Fontes oficiais consultadas

- Psono: página de edições, documentação de instalação, recovery codes, emergency codes, arquitetura e auditoria.
- Passbolt: comparação Community/Business, documentação de backup, OpenPGP, grupos e account recovery.
