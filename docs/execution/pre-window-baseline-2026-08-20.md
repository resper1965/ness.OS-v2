# Baseline pré-janela — 20/08/2026

## Backup e capacidade

- Zabbix: script com sintaxe válida, `root:root` modo `700`, MariaDB com aproximadamente 37 GB e cerca de 1,1 TB livres. Timer transitório de execução única programado para 22:00 BRT.
- AIOps: script com sintaxe válida, `root:root` modo `700`, timer diário persistente às 23:00 BRT e execução anterior concluída com código zero. Backups locais ocupavam aproximadamente 136 MB.
- AIOps Docker: cerca de 15 GB de build cache recuperável; não removido por não haver pressão de capacidade.

## Borda e disponibilidade

- `api`, `hub`, `n-ticket`, `n8n`, `sso` e `waba` responderam externamente por HTTPS com certificado válido.
- AIOps: 22, 80 e 443 abertas; 8082/8085 fechadas.
- Zabbix: 22 fechada; 2222, 80, 443 e 10051 abertas.
- Os 17 proxies cadastrados usam PSK e estavam ativos, com último acesso entre três e cinco segundos no momento da inspeção.
- A porta 10051 não será limitada por snapshot de IP. Estado-alvo: WireGuard entre proxies e servidor, seguido de allowlist da sub-rede privada.

## AIOps

- Nenhum processo suspeito, cron malicioso, executável temporário ou unit systemd falha.
- Fail2ban ativo; a pressão observada foi de 1.281 falhas SSH em duas horas, três origens bloqueadas no momento e 15 no total.
- Nenhum contêiner privilegiado; somente Caddy publica portas no host.
- Filesystem somente leitura e `no-new-privileges` ainda não foram aplicados e exigem teste por serviço.
- Um `.venv` Windows de 133 MB, sem referência ou mount, foi movido para `/root/security-quarantine/20260820-aiops-artifacts/backend-dot-venv`.
- Quatorze arquivos `666` e três diretórios `777` foram normalizados para `644/755`; checksums de conteúdo permaneceram iguais e não restou objeto world-writable no escopo operacional.
- `ness_admin` foi criado com uma única chave nominal e `sudo`; login foi testado antes e depois do reload do SSH. Novas sessões root foram bloqueadas.
