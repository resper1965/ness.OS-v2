# ADR 0004 — Objetivos de recuperação e backup

- Status: aceita
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

Não foi encontrada evidência de backup restaurável dos bancos das duas VPS. Existe Object Storage Contabo e sua capacidade pode crescer.

## Decisão

Adotar inicialmente RPO de 24 horas e RTO de 4 horas. Backups serão criptografados, enviados ao Contabo Object Storage por API S3 com credencial exclusiva por produtor e submetidos a testes regulares de restauração. O Object Storage não será montado como disco de bancos ou indexers. Uma segunda cópia independente será acrescentada para completar a estratégia 3-2-1.

## Consequências

- Dumps consistentes diários atendem o RPO inicial.
- A restauração completa precisa ser automatizada e demonstrada em até quatro horas.
- Retenção, versionamento, lifecycle e imutabilidade serão definidos antes do go-live AIOps.
- A cópia externa permanece bloqueada enquanto endpoint, access key, secret key e buckets reais não existirem.
