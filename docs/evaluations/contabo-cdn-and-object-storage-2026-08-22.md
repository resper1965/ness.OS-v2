# Avaliação — CDN e Object Storage Contabo

- Data: 22/08/2026
- Resultado: Object Storage aprovado; CDN externa apenas condicional

## Conclusão

Contabo Object Storage atende ao destino S3 primário de backup do ness.OS. Não foi encontrado produto de CDN nativo na oferta/API oficial consultada; a própria documentação da Contabo exemplifica Cloudflare quando se deseja domínio/proxy diante de objetos públicos. Isso não justifica inserir uma CDN na arquitetura-base.

## Object Storage

Capacidades relevantes confirmadas: API S3, credenciais próprias, versionamento, lifecycle, Object Lock e uso por AWS CLI/rclone. Existem diferenças em relação ao AWS S3 e limites operacionais; por isso o desenho usa cópia direta, checksum e restore, e não montagem POSIX.

Padrão operacional:

1. bucket privado por domínio de serviço;
2. identidade/credencial exclusiva por produtor;
3. criptografia do artefato antes do envio;
4. upload do dump, manifesto, SHA-256 e `COMPLETED`;
5. retenção por lifecycle e imutabilidade quando aplicável;
6. validação periódica de restore;
7. futura segunda cópia fora da mesma conta/provedor para completar 3-2-1.

Usar operação de cópia de artefatos imutáveis; evitar `sync` destrutivo como mecanismo principal. O Gate 0 permanece bloqueado para a cópia externa até a contratação e entrega de endpoint, access key, secret key e buckets.

## CDN

Um piloto somente será aprovado se medir redução relevante de latência e carga para a PWA pública. Escopo permitido: JavaScript, CSS, fontes, imagens e documentação pública. Escopo proibido: ingestão Zabbix/Wazuh, API administrativa, GLPI/Authentik autenticados, conteúdo específico de tenant e backups.

Critérios do piloto: p95 por região, cache-hit ratio, redução de banda no origin, comportamento de sessão, purge, logs, custo e impacto de segurança. Sem ganho material, não adotar.

## Fontes oficiais consultadas

- Contabo API: <https://api.contabo.com/>
- Compatibilidade S3: <https://help.contabo.com/en/support/solutions/articles/103000275459-is-contabo-object-storage-compatible-with-s3-storage->
- Versionamento: <https://help.contabo.com/en/support/solutions/articles/103000282907-does-object-storage-support-versioning->
- Lifecycle: <https://help.contabo.com/en/support/solutions/articles/103000282913-does-contabo-object-storage-support-lifecycle-policies->
- Limites: <https://help.contabo.com/en/support/solutions/articles/103000275478-what-limits-are-there-on-object-storage->
- Domínio/proxy para objetos públicos: <https://help.contabo.com/en/support/solutions/articles/103000282942-can-i-setup-a-custom-domain-for-my-object-storage->
