# PoC Psono Community — checklist de implantação

> Decisão: aprovada em 21/08/2026
> Escopo: somente Psono Community; imagens, licença e recursos Business/Enterprise são proibidos.

## Dependências externas

- [ ] VPS corporativa dedicada: 2 vCPU, 4 GB RAM e 40 GB.
- [x] Subdomínio do cofre definido: `cofre.ness.com.br`.
- [x] Provedor SMTP definido: Resend.
- [ ] Verificar `ness.com.br` no Resend; DNS é administrado pela Cloudflare.
- [x] Endereço `From` aprovado: `ness.OS <notificacoes@ness.com.br>`.
- [ ] Chave Resend temporária mantida por decisão do owner somente durante implantação/homologação, fora do Git e de logs; rotação é gate obrigatório antes de produção.
- [x] Object Storage disponível para backup criptografado.
- [x] Dois responsáveis formais por recuperação e emergency access: Ricardo
  Esper (`resper@ness.com.br`) e Ismael Araujo (`iaraujo@ness.com.br`).

## Implantação

- [x] Debian estável atualizado e endurecido.
- [x] Usuário administrativo nominal, SSH por chave e root remoto bloqueado.
- [x] Psono combo CE e PostgreSQL fixados por versão/digest.
- [x] Redes de borda/aplicação/dados separadas; PostgreSQL não publicado.
- [x] Caddy/TLS público, NTP, firewall, Fail2ban e healthchecks.
- [ ] SMTP funcional sem segredos no repositório: `smtp.resend.com`, usuário `resend`, STARTTLS/587 como baseline; API key somente como senha no segredo runtime.
- [ ] MFA local obrigatório para todos os usuários.
- [x] Backup diário criptografado incluindo banco, configuração e chaves estáveis do servidor.

## Cenários de aceite

- [ ] Quatro identidades descartáveis: owner, administrador, operador e substituto.
- [ ] Criar os grupos `infraestrutura`, `aplicacoes`, `integracoes`, `clientes` e `break-glass`.
- [ ] Compartilhar segredo como leitura e como escrita; provar negação fora do grupo.
- [ ] Remover usuário e confirmar revogação de acesso e sessões.
- [ ] Gerar e testar recovery code.
- [ ] Gerar e testar emergency code com tempo de espera e notificação.
- [ ] Validar browser, Android e iOS nos dispositivos previstos.
- [ ] Executar atualização controlada e rollback.
- [ ] Restaurar backup em host vazio e comprovar acesso aos segredos de teste.
- [x] Registrar explicitamente a ausência de SSO, LDAP e auditoria granular na CE.

## Gate de promoção

O Psono Community somente receberá credenciais reais quando todos os cenários passarem, o restore for demonstrado, dois responsáveis comprovarem recuperação independente e não houver componente Enterprise na composição. Se o gate falhar, executar PoC equivalente com Passbolt Community.
