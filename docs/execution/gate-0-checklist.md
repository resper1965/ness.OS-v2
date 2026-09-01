# Checklist de execução — Gate 0

> Plano aprovado em: 20/08/2026
> Aprovador: Ricardo Esper
> Escopo: VPS Zabbix/NOC e VPS AIOps
> Objetivo: conter riscos imediatos antes de qualquer expansão funcional

## Regras da execução

- Não registrar senhas, tokens, chaves privadas ou dumps no Git.
- Toda alteração terá responsável, evidência anterior/posterior e rollback.
- Mudanças com possível impacto no Zabbix, proxies, banco ou ingestão ocorrerão entre 22:00 e 00:00 em `America/Sao_Paulo`.
- Ativos sem vínculo direto com a operação Zabbix podem ser tratados fora dessa janela após avaliação de impacto.
- Não revogar o acesso atual antes de validar ao menos um acesso nominal e um caminho break-glass.
- Não considerar backup concluído antes de verificar checksum e leitura/restauração mínima.

## 1. Abertura da mudança

- [ ] Criar identificador da mudança e registrar data/hora.
- [ ] Nomear executor e aprovador.
- [ ] Classificar impacto em Zabbix, AIOps, GLPI, Authentik e integrações.
- [ ] Confirmar se a janela 22:00–00:00 é obrigatória.
- [ ] Registrar critérios de sucesso, abortagem e rollback.
- [ ] Suspender deploy automático e novas features durante o Gate 0.

**Evidência:** registro da mudança, responsáveis e confirmação do freeze.

## 2. Baseline anterior

- [ ] Registrar serviços systemd ativos/falhos nas duas VPS.
- [ ] Registrar contêineres, imagens, healthchecks e portas publicadas na VPS AIOps.
- [ ] Registrar espaço em disco, memória, carga e inodes.
- [ ] Registrar regras UFW/iptables/DOCKER-USER sem valores sensíveis.
- [ ] Registrar versões dos bancos e aplicações críticas.
- [ ] Confirmar acesso SSH por chave com conta nominal ou conta temporária controlada.

**Critério:** existe evidência suficiente para comparar o ambiente antes e depois.

## 3. Backup emergencial

- [ ] Gerar dump consistente do MariaDB Zabbix.
- [ ] Gerar dump consistente do PostgreSQL/TimescaleDB do Hub.
- [ ] Gerar dump consistente do MariaDB GLPI.
- [ ] Copiar configurações e dados necessários de Authentik, GLPI, n8n, Evolution e Caddy.
- [ ] Criptografar os artefatos antes do envio externo.
- [ ] Enviar para o Object Storage com credencial exclusiva.
- [ ] Calcular e registrar checksums.
- [ ] Testar leitura dos arquivos e restauração mínima em ambiente isolado.
- [ ] Registrar horário do backup para medir o RPO.

**Abortar se:** dump apresentar erro, arquivo vazio, checksum divergente ou Object Storage indisponível.

## 4. Acesso administrativo e segredos

- [ ] Criar/validar contas nominais para Ricardo, Rogério, Ismael e Agnaldo.
- [ ] Aplicar MFA onde suportado.
- [ ] Separar conta diária de conta break-glass.
- [ ] Confirmar que pelo menos dois administradores conseguem autenticar por chave.
- [ ] Inventariar credenciais de root, bancos, JWT, OIDC, GLPI, Authentik, n8n, Evolution, webhooks e APIs.
- [ ] Provisionar Psono Community em terceira VPS independente, com MFA, grupos e pelo menos dois responsáveis pela recuperação; Passbolt Community é somente contingência se a PoC falhar.
- [ ] Definir coleções por domínio e migrar as credenciais temporariamente mantidas em arquivos `root-only`.
- [ ] Implantar SOPS/age separadamente para segredos de automação que precisem acompanhar o Git.
- [ ] Rotacionar credenciais em ordem que preserve rollback.
- [ ] Atualizar secrets do CI e runtime sem gravar valores no repositório.
- [ ] Revogar credenciais antigas somente após smoke tests.
- [ ] Desabilitar SSH por senha e root remoto somente depois dos testes nominais/break-glass.

**Critério:** nenhum segredo conhecido como exposto continua válido, não há perda de acesso administrativo e a recuperação do cofre foi validada por dois responsáveis.

## 5. Borda e proteção das VPS

- [ ] Corrigir Fail2ban na VPS AIOps e validar o backend `systemd`.
- [ ] Fechar exposição externa das portas 8082 e 8085.
- [ ] Confirmar que Caddy é a única borda web pública do Hub.
- [ ] Aplicar regras DOCKER-USER para impedir bypass do firewall.
- [ ] Restringir a porta 10051 do Zabbix às origens aprovadas.
- [ ] Verificar externamente as portas abertas nas duas VPS.
- [ ] Confirmar que os serviços continuam acessíveis pelos caminhos aprovados.

**Abortar se:** houver perda de SSH, interrupção da ingestão Zabbix ou indisponibilidade sem rollback imediato.

## 6. CI/CD inseguro

- [ ] Desabilitar temporariamente o workflow de produção atual.
- [ ] Remover credencial explícita de smoke test.
- [ ] Revogar a credencial correspondente.
- [ ] Registrar host key SSH correta.
- [ ] Proibir deploy como root e `StrictHostKeyChecking=no`.
- [ ] Confirmar que nenhum deploy automático poderá usar `/root/app` ou sobrescrever produção.

**Critério:** produção não pode ser alterada pelo workflow inseguro conhecido.

## 7. Validação posterior

- [ ] Confirmar saúde do Zabbix server, banco, frontend e Agent 2.
- [ ] Confirmar ingestão recente e fila dentro do limite normal.
- [ ] Confirmar saúde dos contêineres AIOps.
- [ ] Confirmar acesso ao Hub, Authentik, GLPI e n8n pelos domínios aprovados.
- [ ] Confirmar que portas 8082/8085 não respondem externamente.
- [ ] Confirmar Fail2ban sem serviço falho.
- [ ] Executar scanner de segredos no estado atual do Git.
- [ ] Registrar desvios e incidentes encontrados.

## 8. Fechamento do Gate 0

O Gate 0 somente poderá ser marcado como concluído quando:

- [ ] nenhum segredo conhecido como comprometido permanece válido;
- [ ] backups externos possuem checksum e teste de leitura/restauração;
- [ ] a borda pública contém apenas portas aprovadas;
- [ ] acesso administrativo nominal e break-glass foram comprovados;
- [ ] o deploy inseguro foi bloqueado;
- [ ] Zabbix e AIOps passaram nos smoke tests;
- [ ] evidências e pendências foram anexadas ao registro da mudança.

## Rollback mínimo

1. Interromper a execução no primeiro critério de abortagem.
2. Restaurar regras de rede anteriores a partir da sessão SSH ainda aberta.
3. Reaplicar a credencial anterior apenas se ela ainda não tiver sido revogada e se isso for indispensável para recuperação.
4. Restaurar configuração/serviço afetado usando o backup anterior à mudança.
5. Validar Zabbix, ingestão e acesso administrativo.
6. Registrar a falha e reagendar; não continuar acumulando mudanças.
