# ADR 0013 — Fronteira de administração da plataforma

- Status: aceita
- Data: 22/08/2026
- Decisor: Ricardo Esper

## Contexto

O ness.OS será multi-tenant e oferecerá painéis a clientes e equipes internas. Permissões somente visuais ou distribuídas por aplicação criariam risco de escalada, administração cruzada entre tenants e ações não rastreáveis sobre o provedor.

## Decisão

Criar o papel global `platform_admin`, atribuído inicialmente e exclusivamente a Ismael Araujo, Rogerio Salerno e Ricardo Esper. O papel será originado no Authentik e validado pelo backend em todas as operações privilegiadas.

Somente `platform_admin` poderá administrar tenants, papéis globais, integrações, credenciais, infraestrutura, Object Storage, políticas globais e ações da API Contabo. O acesso exigirá MFA e toda ação gerará auditoria com ator, tenant, recurso, operação, resultado e timestamp.

## Consequências

- Usuários de clientes e operadores não administram a plataforma, mesmo que conheçam um endpoint de API.
- Interfaces ocultas não contam como controle de segurança; a autorização é sempre server-side.
- Elevação, remoção e revisão trimestral do papel serão processos formais e auditáveis.
- A integração Contabo inicia somente em modo leitura; mutações futuras exigem aprovação registrada.
