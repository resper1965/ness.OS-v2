# ADR 0012 — Arquitetura oficial do ness.OS

- Status: aceita
- Data: 22/08/2026
- Decisor: Ricardo Esper

## Contexto

O projeto passou a reunir observabilidade, segurança, governança, projetos e indicadores executivos, mas os desenhos existentes destacavam partes isoladas e permitiam interpretar o Wazuh como centro de toda a plataforma.

## Decisão

Adotar `docs/architecture/ness-os-official-architecture.md` como arquitetura oficial. Zabbix é o plano canônico de disponibilidade; Wazuh, o plano canônico de segurança; GLPI, o plano canônico de governança/ITSM; e ness.OS, a camada de experiência, contexto, correlação e indicadores.

A API Contabo será uma fonte de plano de controle, não substituto da telemetria do Zabbix. Contabo Object Storage será o destino S3 primário dos backups externos e não será montado como armazenamento ativo. CDN permanece opcional e condicionada a teste de ganho mensurável em conteúdo web estático.

A VPS Wazuh na Hostinger e a KVM8 de transmutação são transitórias e não compõem o estado final.

## Consequências

- Zabbix aparece como componente de primeira classe em diagramas, indicadores e capacidade.
- Cada indicador preserva sua origem e o sistema canônico responsável.
- Diagramas divergentes anteriores tornam-se históricos.
- Mudanças futuras no desenho oficial exigem nova ADR ou revisão explícita desta decisão.
