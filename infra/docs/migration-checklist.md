# Checklist de Migração — Zabbix Azure → Contabo

> **Projeto:** Migração Zabbix 6.4 → 7.0 LTS  
> **Origem:** Azure (2 VMs)  
> **Destino:** Contabo Storage VPS 40  
> **Data planejada:** ____/____/________  
> **Responsável técnico:** _________________________  

---

## 1. Verificações Pré-Migração

### 1.1 Infraestrutura de Origem (Azure)

- [ ] Acesso SSH confirmado ao VM-Zabbix-01 (DB - 20.127.231.106)
- [ ] Acesso SSH confirmado ao VM-Zabbix-02 (App - 52.146.5.10)
- [ ] Inventário de hosts atualizado (esperado: 374 hosts)
- [ ] Inventário de items documentado (esperado: 59.031 items)
- [ ] Inventário de triggers documentado (esperado: 25.716 triggers)
- [ ] Versão do Zabbix confirmada: 6.4.13
- [ ] Versão do MariaDB confirmada: 10.5
- [ ] Tamanho do banco verificado: ~452 GB
- [ ] Todos os templates exportados/documentados
- [ ] Media types e ações documentadas
- [ ] Manutenções agendadas verificadas

### 1.2 Infraestrutura de Destino (Contabo)

- [ ] Servidor Contabo Storage VPS 40 provisionado
- [ ] Debian 12 instalado e atualizado
- [ ] MariaDB 10.11 instalado e configurado
- [ ] Zabbix 7.0 LTS instalado (server, frontend, agent2)
- [ ] Apache2 instalado e configurado
- [ ] PHP configurado para Zabbix (timezone, memory_limit, etc.)
- [ ] UFW configurado (portas: 22, 80, 443, 10050, 10051)
- [ ] Certificado SSL configurado (Let's Encrypt ou outro)
- [ ] Espaço em disco suficiente (mínimo 800 GB livres)
- [ ] Swap configurado (mínimo 4 GB)
- [ ] Chave SSH configurada para acesso

### 1.3 Comunicação e Planejamento

- [ ] Janela de manutenção aprovada pelos stakeholders
- [ ] Equipe técnica notificada sobre a migração
- [ ] Usuários finais notificados sobre a indisponibilidade
- [ ] Procedimento de rollback revisado
- [ ] Contatos de emergência confirmados
- [ ] Canais de comunicação definidos (Teams, Slack, etc.)

### 1.4 Ferramentas e Scripts

- [ ] Scripts de migração clonados no servidor
- [ ] pigz instalado no servidor de origem
- [ ] pigz/unpigz instalado no servidor de destino
- [ ] pv instalado no servidor de destino
- [ ] rsync instalado em ambos os servidores
- [ ] puttygen disponível (se necessário converter chave SSH)

---

## 2. Procedimento do Dia da Migração

### Janela de Manutenção Sugerida

| Item | Valor |
|------|-------|
| **Início** | Sexta-feira, 22:00 (horário local) |
| **Duração estimada** | 8-12 horas |
| **Término máximo** | Sábado, 10:00 |
| **Rollback deadline** | Sábado, 08:00 |

> **Nota:** Escolher um horário de baixo impacto. Preferencialmente iniciar na sexta à noite para ter o fim de semana como buffer.

---

### Passo 1: Housekeeping Pré-Migração
**Horário estimado:** T+0h  
**Duração estimada:** 1-4 horas  
**Executar em:** VM-Zabbix-02 (52.146.5.10)

```bash
cd /caminho/dos/scripts
./01-pre-migration-housekeeping.sh
```

- [ ] Políticas de retenção configuradas (90d history, 365d trends/events)
- [ ] Housekeeping executado
- [ ] Tamanho do banco reduzido confirmado
- [ ] Tamanho registrado: ______ GB (antes) → ______ GB (depois)

**GO/NO-GO:** O housekeeping reduziu o tamanho significativamente?
- [ ] ✅ GO — Continuar para o próximo passo
- [ ] ❌ NO-GO — Avaliar situação, considerar prosseguir com banco maior

---

### Passo 2: Dump do Banco de Dados
**Horário estimado:** T+4h  
**Duração estimada:** 2-4 horas  
**Executar em:** VM-Zabbix-01 (20.127.231.106)

```bash
DB_PASSWORD=<senha> ./02-dump-database.sh
```

- [ ] Zabbix Server parado no VM-Zabbix-02
- [ ] Dump iniciado
- [ ] Dump concluído com sucesso
- [ ] Checksum MD5 calculado e salvo
- [ ] Tamanho do dump: ______ GB
- [ ] MD5: ________________________________

**GO/NO-GO:** O dump foi criado com sucesso e tem tamanho razoável?
- [ ] ✅ GO — Continuar para a transferência
- [ ] ❌ NO-GO — Investigar falha, tentar novamente

---

### Passo 3: Transferência de Dados
**Horário estimado:** T+8h  
**Duração estimada:** 2-6 horas (depende da banda)  
**Executar em:** Qualquer máquina com acesso SSH a ambos

```bash
./03-transfer-data.sh --target-ip <IP_CONTABO>
```

- [ ] Conectividade verificada (origem e destino)
- [ ] Transferência iniciada
- [ ] Transferência concluída
- [ ] Checksum verificado e confere
- [ ] Velocidade média: ______ Mbps

**GO/NO-GO:** Checksums conferem?
- [ ] ✅ GO — Continuar para a importação
- [ ] ❌ NO-GO — Retransmitir dados

---

### Passo 4: Importação no Contabo
**Horário estimado:** T+14h  
**Duração estimada:** 2-6 horas  
**Executar em:** Servidor Contabo

```bash
DB_PASSWORD=<senha> ./04-import-database.sh
```

- [ ] Integridade do dump verificada (MD5)
- [ ] Banco criado e usuário configurado
- [ ] Importação iniciada
- [ ] Importação concluída
- [ ] Contagem de tabelas: ______ (esperado: ~180)
- [ ] Upgrade de schema executado (6.4 → 7.0)
- [ ] Versão do schema verificada: ________

**GO/NO-GO:** Importação bem-sucedida e upgrade concluído?
- [ ] ✅ GO — Continuar para validação
- [ ] ❌ NO-GO — Avaliar rollback

---

### Passo 5: Validação Pós-Migração
**Horário estimado:** T+20h  
**Executar em:** Servidor Contabo

```bash
ZABBIX_PASSWORD=<senha> ./05-validate-migration.sh
```

- [ ] Todos os serviços ativos (mariadb, zabbix-server, apache2, zabbix-agent2)
- [ ] API do Zabbix respondendo
- [ ] Contagem de hosts: ______ (esperado: 374)
- [ ] Contagem de items: ______ (esperado: 59.031)
- [ ] Contagem de triggers: ______ (esperado: 25.716)
- [ ] Frontend acessível via HTTPS
- [ ] Certificado SSL válido
- [ ] Firewall (UFW) ativo
- [ ] Backup configurado no cron
- [ ] Disco com espaço suficiente
- [ ] Sem erros críticos no log

**Resultado do script:** PASS / WARN / FAIL  
**Detalhes:** _________________________________________________

---

### Passo 6: Verificações Manuais

- [ ] Login no frontend com sucesso
- [ ] Dashboards carregando corretamente
- [ ] Gráficos exibindo dados históricos
- [ ] Mapa de rede/topologia correto
- [ ] Últimos dados de hosts sendo recebidos
- [ ] Disparar alerta de teste e verificar notificação
- [ ] Verificar se e-mails/Telegram/etc. estão sendo enviados

---

### Passo 7: Atualização de DNS/Rede

- [ ] DNS atualizado para apontar ao IP do Contabo
- [ ] TTL do DNS reduzido previamente (se aplicável)
- [ ] Propagação DNS verificada
- [ ] Agentes Zabbix reconfigurados (se necessário)
- [ ] Proxy Zabbix reconfigurado (se aplicável)

---

### Passo 8: Monitoramento Pós-Go-Live (primeiras 2 horas)

- [ ] Hosts começando a reportar ao novo servidor
- [ ] Sem flood de alertas falsos
- [ ] Performance do servidor estável (CPU, RAM, disco)
- [ ] Nenhum erro novo nos logs
- [ ] Equipe de plantão notificada que a migração foi concluída

---

## 3. Validação Pós-Migração (Dias Seguintes)

### Dia 1 (D+1)

- [ ] Verificar se todos os 374 hosts estão reportando
- [ ] Verificar se não há hosts "unreachable"
- [ ] Revisar alertas gerados nas últimas 24h
- [ ] Confirmar que backups estão funcionando
- [ ] Verificar uso de disco

### Dia 3 (D+3)

- [ ] Revisar performance do servidor
- [ ] Verificar crescimento do banco de dados
- [ ] Confirmar funcionamento de relatórios agendados
- [ ] Validar integridade dos gráficos de tendência

### Dia 7 (D+7)

- [ ] Avaliação geral de estabilidade
- [ ] Decisão sobre descomissionamento do Azure
- [ ] Executar script 06-cleanup-azure.sh (se tudo OK)

---

## 4. Procedimento de Rollback

### Quando Acionar Rollback

Acionar rollback se **qualquer** das seguintes condições ocorrer:

- ❌ Importação do banco falhou e não pode ser corrigida
- ❌ Upgrade de schema falhou
- ❌ Mais de 20% dos hosts não reportando após 4 horas
- ❌ Perda de dados detectada
- ❌ Falha crítica no servidor Contabo

### Procedimento de Rollback

```bash
# 1. Parar serviços no Contabo
ssh ness_admin@<IP_CONTABO> 'sudo systemctl stop zabbix-server zabbix-agent2 apache2'

# 2. Reiniciar serviços no Azure (App Server)
ssh ness_admin@52.146.5.10 'sudo systemctl start zabbix-server zabbix-agent2 apache2'

# 3. Reiniciar MariaDB no Azure (DB Server) - se foi parado
ssh ness_admin@20.127.231.106 'sudo systemctl start mariadb'

# 4. Verificar que o Zabbix Azure está funcionando
curl -s http://52.146.5.10/api_jsonrpc.php

# 5. Reverter DNS (se foi alterado)
# [Comandos específicos do seu provedor DNS]

# 6. Notificar stakeholders sobre o rollback
```

### Checklist Pós-Rollback

- [ ] Serviços Azure funcionando normalmente
- [ ] Frontend acessível
- [ ] Hosts reportando dados
- [ ] Causa do rollback documentada
- [ ] Plano de ação para próxima tentativa definido

---

## 5. Sign-Off (Aprovação)

### Aprovação da Migração

| Campo | Valor |
|-------|-------|
| **Data/Hora de início** | ____/____/________ às ____:____ |
| **Data/Hora de conclusão** | ____/____/________ às ____:____ |
| **Duração total** | ____h ____m |
| **Resultado** | ☐ Sucesso ☐ Sucesso com ressalvas ☐ Rollback |
| **Downtime total** | ____h ____m |

### Assinaturas

| Papel | Nome | Assinatura | Data |
|-------|------|-----------|------|
| Responsável Técnico | | | |
| Gerente de TI | | | |
| Representante Operações | | | |

### Observações

```
_____________________________________________________________________________

_____________________________________________________________________________

_____________________________________________________________________________

_____________________________________________________________________________
```

### Pendências Pós-Migração

| # | Item | Responsável | Prazo | Status |
|---|------|------------|-------|--------|
| 1 | | | | ☐ |
| 2 | | | | ☐ |
| 3 | | | | ☐ |
| 4 | | | | ☐ |
| 5 | | | | ☐ |

---

> **Documento gerado em:** 2026-06-29  
> **Versão:** 1.0  
> **Próxima revisão:** Antes da execução da migração
