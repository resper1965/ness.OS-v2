# Arquitetura oficial do ness.OS

- Estado: oficial
- Versão: 1.0
- Data: 22/08/2026
- Responsável: Ricardo Esper
- Decisões: ADR 0012 e ADR 0013

Este documento e a apresentação `docs/presentations/ness-os-infrastructure-5000-endpoints.html` formam a referência visual oficial do ness.OS. Diagramas anteriores permanecem apenas como histórico.

## Visão oficial

```mermaid
flowchart LR
    subgraph ORIGENS[Origens da coleta]
        END[Endpoints de clientes]
        INF[Servidores, redes e aplicações]
        CLOUD[Nuvem e SaaS]
        RMM[SuperOps / Atera]
        CAP[API Contabo — plano de controle]
    end

    subgraph DISP[Disponibilidade — Zabbix]
        ZA[Agentes e proxies Zabbix]
        ZS[Zabbix 7.0 LTS existente]
    end

    subgraph SEC[Segurança — Wazuh hub-spoke]
        IN[Entrada HA]
        W1[Spoke / worker 1]
        W2[Spoke / worker 2]
        W3[Spoke / worker 3]
        W4[Spoke / worker 4]
        WM[Master / hub]
        IDX[(Cluster de 3 indexers)]
        WD[Dashboard e API Wazuh]
    end

    subgraph GOV[Governança — GLPI]
        GA[GLPI Agent]
        GLPI[GLPI — ITSM, inventário, catálogo e projetos]
    end

    subgraph CORE[Experiência e inteligência — ness.OS]
        API[API e integrações]
        DATA[(Modelo normalizado de indicadores)]
        PWA[PWA operacional e painel executivo]
        AUTH[Authentik]
    end

    subgraph PROTECAO[Proteção e recuperação]
        S3[(Contabo Object Storage privado — S3)]
        COPY[(Segunda cópia independente — futura)]
    end

    END --> ZA --> ZS
    INF --> ZA
    END --> IN
    INF --> IN
    CLOUD --> IN
    IN --> W1 & W2 & W3 & W4
    W1 & W2 & W3 & W4 --> WM --> IDX --> WD
    END --> GA --> GLPI
    RMM --> GLPI
    ZS --> API
    WD --> API
    GLPI --> API
    CAP --> API
    CAP --> GLPI
    AUTH --> API
    API --> DATA --> PWA
    ZS -. backup .-> S3
    IDX -. backup/configuração .-> S3
    GLPI -. backup .-> S3
    API -. backup .-> S3
    AUTH -. backup .-> S3
    S3 -. regra 3-2-1 .-> COPY
```

## Estado da implantação — 13/10/2026

Este diagrama mostra **estado comprovado**, não o desenho-alvo acima. Verde significa operação observada; amarelo, entrega parcial ou isolada; vermelho, gate bloqueado; cinza, expansão ainda não aceita. Uma seta indica dependência, não integração aprovada.

```mermaid
flowchart LR
    ZO["Zabbix origem<br/>única coletora ativa"] --> ZD["Zabbix destino<br/>restore e UAT aprovados; coleta e DNS bloqueados"]
    ZO --> H["Hub / AIOps<br/>runtime promovido; G0 e fluxo completo parciais"]
    A["Authentik<br/>SSO e marca ativos; MFA/recuperação pendentes"] --> H
    A --> G["GLPI<br/>UI/SSO e volume operantes; aceite funcional pendente"]
    H --> B["Integração GLPI T03<br/>isolamento direto não aprovado; conta 106 inativa"] --> G
    G --> D["Logins GLPI<br/>1 colisão inativa corrigida; 33 pares aguardam decisão RBAC"]
    G --> P["Plugins GLPI<br/>sem código carregado; dados residuais preservados"]
    S["Backup externo Contabo<br/>cópia única; G1 parcial"] --> ZD
    S --> G
    W["Wazuh e Google Workspace<br/>expansão não aceita"] -.-> H
    V["Psono dedicado e G2<br/>custódia/MFA ainda pendentes"] -.-> A

    classDef operando fill:#dcfce7,stroke:#166534,color:#14532d;
    classDef parcial fill:#fef3c7,stroke:#b45309,color:#78350f;
    classDef bloqueado fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d;
    classDef planejado fill:#e5e7eb,stroke:#6b7280,color:#374151;
    class ZO operando;
    class H,A,G,S,P parcial;
    class ZD,B,D,V bloqueado;
    class W planejado;
```

O destino Zabbix não está em produção; a origem segue coletando. No GLPI, a migração do volume e o retorno da rota pública não aprovam login nominal, ticket/anexo nem isolamento entre entidades. Os 33 pares de login ativos têm perfis divergentes, portanto a deduplicação em massa permanece suspensa. Os plugins não foram removidos. Evidências e próximos gates: [contexto canônico](../PROJECT_CONTEXT.md) e [plano master](../superpowers/plans/2026-10-12-ness-os-plano-master.md).

## Responsabilidade canônica

| Domínio | Sistema canônico | O que entrega ao ness.OS |
|---|---|---|
| Disponibilidade e capacidade | Zabbix | hosts, problemas, SLO, tendências, mapas e localização |
| Segurança | Wazuh | agentes, eventos qualificados, incidentes e postura |
| Governança e serviço | GLPI | ativos, tickets, catálogo, contratos, projetos e runbooks |
| Plano de controle do provedor | API Contabo | inventário de VPS, estado, ações, snapshots/backups e Object Storage |
| Experiência e indicadores | ness.OS | contexto unificado, correlação, PWA e visão executiva |
| Identidade | Authentik | SSO, MFA, grupos e sessões |

## Administração da plataforma

O papel `platform_admin` é o único autorizado a administrar tenants, integrações, credenciais, infraestrutura, políticas globais e ações do provedor. A atribuição inicial é nominal e restrita a:

- Ismael Araujo;
- Rogerio Salerno;
- Ricardo Esper.

O grupo deve nascer no Authentik, ser consumido pelo backend e nunca ser inferido apenas pelo menu da interface. Toda ação privilegiada deve exigir autorização no servidor, MFA e trilha de auditoria. Clientes e demais equipes recebem papéis de consumo ou operação delegada por tenant, sem herdar `platform_admin`.

## CDN

Não foi identificado um serviço de CDN nativo da Contabo no catálogo/API consultados. CDN é opcional e fica somente diante dos ativos estáticos públicos da PWA e, se comprovado em piloto, como proteção HTTP. Não recebe tráfego de agentes Zabbix/Wazuh, APIs internas, sessões do GLPI/Authentik ou backups. Não entra na compra-base do projeto.

## Backup S3

O Contabo Object Storage será a primeira cópia externa, acessada diretamente pela API S3 — nunca montada como disco do banco ou dos indexers. Padrão inicial de buckets privados:

- `ness-os-zabbix-prod`;
- `ness-os-aiops-prod`;
- `ness-os-glpi-prod`;
- `ness-os-wazuh-prod`;
- `ness-os-auth-prod`;
- `ness-os-evidence`.

Cada produtor terá credencial exclusiva, criptografia antes do envio, manifesto, SHA-256, marcador `COMPLETED`, versionamento/imutabilidade e lifecycle. A implantação continua bloqueada até existirem endpoint, access key, secret key e buckets reais; credenciais não serão inventadas nem documentadas no repositório.
