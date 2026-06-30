# Runbook Operacional - Zabbix 7.0 LTS (Contabo)

> **Servidor:** Contabo Storage VPS 40 — Debian 12  
> **Zabbix:** 7.0 LTS  
> **Banco de Dados:** MariaDB 10.11  
> **Última atualização:** 2026-06-29

---

## Índice

1. [Informações de Acesso](#informações-de-acesso)
2. [Gerenciamento de Serviços](#gerenciamento-de-serviços)
3. [Verificação de Logs](#verificação-de-logs)
4. [Backup e Restauração](#backup-e-restauração)
5. [Banco de Dados](#banco-de-dados)
6. [Gerenciamento de Hosts](#gerenciamento-de-hosts)
7. [Troubleshooting](#troubleshooting)
8. [Portas e Firewall](#portas-e-firewall)
9. [Cron Jobs](#cron-jobs)
10. [Contatos e Escalação](#contatos-e-escalação)

---

## Informações de Acesso

### SSH

```bash
# Acesso ao servidor
ssh ness_admin@<IP_CONTABO> -i ~/.ssh/zabbix_ness

# Com chave PuTTY (Windows)
# Use PuTTY ou converta a chave:
puttygen ~/.ssh/zabbix_ness.ppk -O private-openssh -o ~/.ssh/zabbix_ness
```

### Frontend Web

| Item | Valor |
|------|-------|
| URL | `https://<IP_CONTABO>` ou `https://<domínio>` |
| Usuário padrão | `Admin` |
| Porta HTTPS | 443 |
| Porta HTTP (redirect) | 80 → 443 |

### Banco de Dados

| Item | Valor |
|------|-------|
| Host | localhost |
| Porta | 3306 |
| Banco | `dbzabbix` |
| Usuário | `usrzabbix` |

---

## Gerenciamento de Serviços

### Iniciar Serviços

```bash
# Iniciar todos os serviços na ordem correta
sudo systemctl start mariadb
sudo systemctl start zabbix-server
sudo systemctl start zabbix-agent2
sudo systemctl start apache2
```

### Parar Serviços

```bash
# Parar na ordem inversa
sudo systemctl stop apache2
sudo systemctl stop zabbix-agent2
sudo systemctl stop zabbix-server
# MariaDB geralmente fica rodando
# sudo systemctl stop mariadb
```

### Reiniciar Serviços

```bash
# Reiniciar serviço específico
sudo systemctl restart zabbix-server
sudo systemctl restart zabbix-agent2
sudo systemctl restart apache2
sudo systemctl restart mariadb

# Reiniciar todos
sudo systemctl restart mariadb zabbix-server zabbix-agent2 apache2
```

### Verificar Status

```bash
# Status de todos os serviços
for svc in mariadb zabbix-server zabbix-agent2 apache2; do
    echo "=== $svc ==="
    sudo systemctl status $svc --no-pager -l
    echo ""
done

# Verificação rápida (apenas ativo/inativo)
for svc in mariadb zabbix-server zabbix-agent2 apache2; do
    status=$(systemctl is-active $svc)
    echo "$svc: $status"
done
```

### Habilitar/Desabilitar no Boot

```bash
# Habilitar serviços para iniciar automaticamente
sudo systemctl enable mariadb zabbix-server zabbix-agent2 apache2

# Verificar se estão habilitados
systemctl is-enabled mariadb zabbix-server zabbix-agent2 apache2
```

---

## Verificação de Logs

### Logs do Zabbix Server

```bash
# Log principal do Zabbix Server
sudo tail -f /var/log/zabbix/zabbix_server.log

# Últimas 100 linhas
sudo tail -100 /var/log/zabbix/zabbix_server.log

# Filtrar erros
sudo grep -i "error\|warning\|fatal" /var/log/zabbix/zabbix_server.log | tail -50

# Via journalctl
sudo journalctl -u zabbix-server -f
sudo journalctl -u zabbix-server --since "1 hour ago"
sudo journalctl -u zabbix-server --since today
```

### Logs do Zabbix Agent

```bash
sudo tail -f /var/log/zabbix/zabbix_agent2.log
sudo journalctl -u zabbix-agent2 -f
```

### Logs do Apache

```bash
# Log de acesso
sudo tail -f /var/log/apache2/access.log

# Log de erros
sudo tail -f /var/log/apache2/error.log

# Erros recentes
sudo grep -i "error\|fatal" /var/log/apache2/error.log | tail -20
```

### Logs do MariaDB

```bash
sudo tail -f /var/log/mysql/error.log
sudo journalctl -u mariadb -f

# Slow queries (se habilitado)
sudo tail -f /var/log/mysql/mariadb-slow.log
```

---

## Backup e Restauração

### Backup Manual

```bash
# Backup completo do banco de dados
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/zabbix"
BACKUP_FILE="${BACKUP_DIR}/dbzabbix_${TIMESTAMP}.sql.gz"

# Criar diretório se não existir
sudo mkdir -p "${BACKUP_DIR}"

# Executar dump com compressão
sudo mysqldump \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --quick \
    --max_allowed_packet=1G \
    dbzabbix | pigz > "${BACKUP_FILE}"

# Calcular checksum
md5sum "${BACKUP_FILE}" > "${BACKUP_FILE}.md5"

# Verificar tamanho
ls -lh "${BACKUP_FILE}"
echo "Backup criado: ${BACKUP_FILE}"
```

### Restauração de Backup

> **⚠️ ATENÇÃO:** A restauração sobrescreve TODOS os dados atuais!

```bash
# 1. Parar Zabbix Server
sudo systemctl stop zabbix-server

# 2. Identificar o backup a restaurar
ls -lht /backup/zabbix/*.sql.gz

# 3. Verificar checksum
BACKUP_FILE="/backup/zabbix/dbzabbix_XXXXXXXX_XXXXXX.sql.gz"
md5sum -c "${BACKUP_FILE}.md5"

# 4. Dropar e recriar banco
sudo mysql -e "DROP DATABASE IF EXISTS dbzabbix;"
sudo mysql -e "CREATE DATABASE dbzabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;"

# 5. Importar
unpigz -c "${BACKUP_FILE}" | sudo mysql dbzabbix

# 6. Reiniciar Zabbix Server
sudo systemctl start zabbix-server

# 7. Verificar
sudo systemctl status zabbix-server
```

### Verificar Backups Existentes

```bash
# Listar backups
ls -lht /backup/zabbix/*.sql.gz 2>/dev/null

# Espaço usado por backups
du -sh /backup/zabbix/

# Verificar integridade do backup mais recente
LATEST=$(ls -t /backup/zabbix/*.sql.gz | head -1)
echo "Último backup: ${LATEST}"
md5sum -c "${LATEST}.md5" 2>/dev/null && echo "Checksum OK" || echo "Checksum FALHOU"
```

---

## Banco de Dados

### Verificar Tamanho do Banco

```bash
# Tamanho total do banco
sudo mysql -e "
SELECT 
    ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2) AS 'Tamanho (GB)'
FROM information_schema.tables 
WHERE table_schema = 'dbzabbix';
"

# Tamanho por tabela (top 15)
sudo mysql -e "
SELECT 
    table_name AS 'Tabela',
    ROUND((data_length + index_length) / 1024 / 1024 / 1024, 2) AS 'Tamanho (GB)',
    table_rows AS 'Linhas (aprox)'
FROM information_schema.tables 
WHERE table_schema = 'dbzabbix' 
ORDER BY (data_length + index_length) DESC 
LIMIT 15;
"
```

### Verificar Performance do Banco

```bash
# Status geral do MariaDB
sudo mysqladmin status
sudo mysqladmin extended-status | grep -E "Threads|Queries|Slow|Opens"

# Processos ativos
sudo mysql -e "SHOW PROCESSLIST;"

# Variáveis importantes
sudo mysql -e "
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
SHOW VARIABLES LIKE 'max_connections';
SHOW VARIABLES LIKE 'query_cache%';
"

# Buffer pool usage
sudo mysql -e "
SHOW STATUS LIKE 'Innodb_buffer_pool%';
"
```

### Queries Úteis

```bash
# Contagem de hosts
sudo mysql dbzabbix -e "SELECT COUNT(*) AS 'Total Hosts' FROM hosts WHERE status=0;"

# Contagem de items
sudo mysql dbzabbix -e "SELECT COUNT(*) AS 'Total Items' FROM items WHERE status=0;"

# Contagem de triggers
sudo mysql dbzabbix -e "SELECT COUNT(*) AS 'Total Triggers' FROM triggers;"

# Housekeeping status
sudo mysql dbzabbix -e "SELECT * FROM config WHERE configid=1\G" | grep -i hk

# Versão do schema
sudo mysql dbzabbix -e "SELECT * FROM dbversion;"

# Eventos recentes
sudo mysql dbzabbix -e "
SELECT FROM_UNIXTIME(clock) AS 'Data', 
       name AS 'Evento', 
       severity 
FROM events 
ORDER BY clock DESC 
LIMIT 20;
"
```

---

## Gerenciamento de Hosts

### Adicionar Host via Frontend

1. Acesse `https://<IP_CONTABO>`
2. Vá em **Data collection** → **Hosts**
3. Clique em **Create host**
4. Preencha:
   - **Host name:** Nome do servidor
   - **Groups:** Selecione o grupo adequado
   - **Interfaces:** Adicione Agent (IP + porta 10050)
5. Associe os **Templates** desejados
6. Clique em **Add**

### Adicionar Host via API

```bash
# Autenticação
AUTH_TOKEN=$(curl -s -X POST \
    -H "Content-Type: application/json-rpc" \
    -d '{
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"username": "Admin", "password": "SUA_SENHA"},
        "id": 1
    }' http://localhost/api_jsonrpc.php | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")

echo "Token: ${AUTH_TOKEN}"

# Criar host
curl -s -X POST \
    -H "Content-Type: application/json-rpc" \
    -d "{
        \"jsonrpc\": \"2.0\",
        \"method\": \"host.create\",
        \"params\": {
            \"host\": \"novo-servidor\",
            \"groups\": [{\"groupid\": \"2\"}],
            \"interfaces\": [{
                \"type\": 1,
                \"main\": 1,
                \"useip\": 1,
                \"ip\": \"192.168.1.100\",
                \"dns\": \"\",
                \"port\": \"10050\"
            }],
            \"templates\": [{\"templateid\": \"10001\"}]
        },
        \"auth\": \"${AUTH_TOKEN}\",
        \"id\": 2
    }" http://localhost/api_jsonrpc.php | python3 -m json.tool
```

---

## Troubleshooting

### Zabbix Server Não Inicia

```bash
# 1. Verificar log de erro
sudo journalctl -u zabbix-server --since "5 min ago" --no-pager
sudo tail -50 /var/log/zabbix/zabbix_server.log

# 2. Verificar se MariaDB está rodando
sudo systemctl status mariadb

# 3. Testar conexão com o banco
sudo mysql -u usrzabbix -p dbzabbix -e "SELECT 1;"

# 4. Verificar configuração
sudo cat /etc/zabbix/zabbix_server.conf | grep -v "^#" | grep -v "^$"

# 5. Verificar permissões
ls -la /var/log/zabbix/
ls -la /var/run/zabbix/

# 6. Verificar porta
sudo ss -tlnp | grep 10051

# 7. Tentar iniciar em foreground para ver erros
sudo zabbix_server -c /etc/zabbix/zabbix_server.conf -f
```

### Frontend com Erro 500

```bash
# 1. Verificar log do Apache
sudo tail -50 /var/log/apache2/error.log

# 2. Verificar log do PHP
sudo tail -50 /var/log/php*.log 2>/dev/null

# 3. Verificar configuração PHP
php -i | grep -E "memory_limit|max_execution|post_max|upload_max|date.timezone"

# 4. Verificar permissões do frontend
ls -la /usr/share/zabbix/conf/

# 5. Verificar conexão do frontend com o banco
sudo cat /etc/zabbix/web/zabbix.conf.php | grep -v "^//"

# 6. Testar PHP
php -r "echo 'PHP OK'; echo PHP_VERSION;"

# 7. Reiniciar Apache
sudo systemctl restart apache2
```

### Agente Não Conecta

```bash
# No servidor Zabbix:
# 1. Verificar se o agente está sendo alcançado
zabbix_get -s <IP_AGENTE> -k system.hostname

# 2. Verificar firewall
sudo ufw status | grep 10050

# No host com o agente:
# 3. Verificar se agente está rodando
sudo systemctl status zabbix-agent2

# 4. Verificar configuração do agente
grep -E "^Server|^ServerActive|^Hostname" /etc/zabbix/zabbix_agent2.conf

# 5. Verificar se a porta está aberta
sudo ss -tlnp | grep 10050

# 6. Verificar log do agente
sudo tail -50 /var/log/zabbix/zabbix_agent2.log

# 7. Testar conectividade
nc -zv <IP_SERVIDOR_ZABBIX> 10051
```

### Banco de Dados Lento

```bash
# 1. Verificar processos longos
sudo mysql -e "SELECT * FROM information_schema.processlist WHERE time > 30 ORDER BY time DESC;"

# 2. Verificar slow queries
sudo mysql -e "SHOW GLOBAL STATUS LIKE 'Slow_queries';"

# 3. Verificar InnoDB status
sudo mysql -e "SHOW ENGINE INNODB STATUS\G" | head -80

# 4. Verificar uso de memória do InnoDB
sudo mysql -e "
SELECT 
    ROUND(@@innodb_buffer_pool_size/1024/1024/1024, 2) AS 'Buffer Pool (GB)',
    ROUND((SELECT VARIABLE_VALUE FROM information_schema.global_status WHERE VARIABLE_NAME='Innodb_buffer_pool_pages_data') * @@innodb_page_size / 1024/1024/1024, 2) AS 'Dados em Cache (GB)';
"

# 5. Verificar tabelas grandes sem índice
sudo mysql dbzabbix -e "
SELECT table_name, engine, table_rows,
    ROUND(data_length/1024/1024/1024,2) AS 'Dados (GB)',
    ROUND(index_length/1024/1024/1024,2) AS 'Índices (GB)'
FROM information_schema.tables 
WHERE table_schema='dbzabbix' AND data_length > 1073741824
ORDER BY data_length DESC;
"

# 6. Otimizar tabela específica (usar com cuidado, bloqueia)
# sudo mysql dbzabbix -e "OPTIMIZE TABLE history;"
```

### Disco Cheio

```bash
# 1. Verificar uso de disco
df -h

# 2. Encontrar maiores diretórios
sudo du -sh /var/lib/mysql/ /var/log/ /backup/ /tmp/ 2>/dev/null

# 3. Verificar logs antigos
sudo find /var/log -name "*.gz" -mtime +30 -exec ls -lh {} \;

# 4. Limpar logs antigos do Zabbix
sudo find /var/log/zabbix/ -name "*.old" -delete
sudo journalctl --vacuum-size=500M

# 5. Limpar backups antigos (manter últimos 7)
ls -t /backup/zabbix/*.sql.gz | tail -n +8 | xargs rm -f

# 6. Verificar housekeeping do Zabbix
sudo mysql dbzabbix -e "SELECT * FROM config\G" | grep -i hk

# 7. Executar housekeeping manual se necessário
# Isso remove dados antigos de history/trends
```

### Certificado SSL Expirado

```bash
# 1. Verificar validade atual
echo | openssl s_client -connect localhost:443 2>/dev/null | openssl x509 -noout -dates

# 2. Renovar com certbot (Let's Encrypt)
sudo certbot renew

# 3. Renovar forçado
sudo certbot renew --force-renewal

# 4. Verificar configuração do certbot
sudo certbot certificates

# 5. Testar renovação automática
sudo certbot renew --dry-run

# 6. Reiniciar Apache após renovação
sudo systemctl restart apache2
```

---

## Portas e Firewall

### Portas Utilizadas

| Porta | Protocolo | Serviço | Direção |
|-------|-----------|---------|---------|
| 22 | TCP | SSH | Entrada |
| 80 | TCP | HTTP (redirect) | Entrada |
| 443 | TCP | HTTPS (frontend) | Entrada |
| 3306 | TCP | MariaDB | Local only |
| 10050 | TCP | Zabbix Agent | Saída (ativo) / Entrada (passivo) |
| 10051 | TCP | Zabbix Server | Entrada |

### Gerenciamento do UFW

```bash
# Status do firewall
sudo ufw status verbose

# Adicionar regra
sudo ufw allow 22/tcp comment "SSH"
sudo ufw allow 443/tcp comment "HTTPS"
sudo ufw allow 10050/tcp comment "Zabbix Agent"
sudo ufw allow 10051/tcp comment "Zabbix Server"

# Remover regra
sudo ufw delete allow 8080/tcp

# Recarregar
sudo ufw reload
```

---

## Cron Jobs

### Jobs Configurados

```bash
# Listar cron jobs
sudo crontab -l

# Cron jobs esperados:
# - Backup diário do banco de dados
# - Limpeza de backups antigos
# - Renovação de certificado SSL (certbot)
```

### Exemplo de Cron de Backup

```cron
# Backup diário às 02:00
0 2 * * * /opt/scripts/backup-zabbix.sh >> /var/log/zabbix-backup.log 2>&1

# Limpeza de backups > 30 dias (às 03:00)
0 3 * * 0 find /backup/zabbix -name "*.sql.gz" -mtime +30 -delete

# Renovação SSL (2x ao dia, recomendação certbot)
0 0,12 * * * certbot renew --quiet --post-hook "systemctl restart apache2"
```

---

## Contatos e Escalação

| Nível | Contato | Responsabilidade |
|-------|---------|-----------------|
| L1 | Equipe de Operações | Monitoramento, reinício de serviços |
| L2 | Administrador Zabbix | Configuração, troubleshooting |
| L3 | ness. (Consultoria) | Arquitetura, problemas complexos |

### Em caso de indisponibilidade

1. Verificar status dos serviços (seção "Gerenciamento de Serviços")
2. Verificar logs (seção "Verificação de Logs")
3. Consultar troubleshooting específico
4. Se não resolver, escalar para L2/L3

---

> **Nota:** Este runbook é um documento vivo. Atualize-o sempre que houver mudanças na infraestrutura ou nos procedimentos.
