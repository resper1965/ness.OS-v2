# ADR 0010 — Política open source e fronteira de integrações

- Estado: aceito
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

Foi definido que o ecossistema será open source. A auditoria encontrou componentes source-available ou com condições adicionais, além de serviços externos fechados usados hoje na operação. Chamar todo código visível de open source ocultaria risco jurídico e lock-in.

## Decisão

1. Todo componente autohospedado do núcleo deverá usar licença aprovada pela OSI e disponibilizar o código-fonte correspondente.
2. Tag flutuante é proibida em produção. Imagens serão fixadas por versão e digest, com SBOM e licença registrados por release.
3. Licença desconhecida, source-available, fair-code ou com restrição adicional bloqueia nova implantação e atualização.
4. Serviços externos inevitavelmente proprietários — como RMM e canais de terceiros — só podem existir atrás de adaptadores substituíveis. Não serão registro canônico nem dependência exclusiva para recuperar a operação.
5. Exceção temporária para legado exige inventário, risco, owner, prazo de saída e bloqueio de atualização automática; não equivale a aprovação permanente.
6. A auditoria inicial e as migrações estão em [`../execution/open-source-license-audit-2026-08-20.md`](../execution/open-source-license-audit-2026-08-20.md).

## Consequências

- Redis será substituído por Valkey.
- TimescaleDB Community será removido porque não há hypertables em uso.
- n8n será migrado inicialmente para Node-RED; Windmill só poderá ser usado a partir de build auditável da fonte AGPL sem partes enterprise.
- Evolution permanecerá congelada como fallback até substituição, pois sua licença possui condições adicionais e releases recentes introduzem ativação externa.
- SuperOps, Datto, Atera e provedores de mensagens são integrações de borda, não componentes constitutivos do núcleo.
- O Hub próprio precisa de licença explícita, SBOM e política automática de dependências.
