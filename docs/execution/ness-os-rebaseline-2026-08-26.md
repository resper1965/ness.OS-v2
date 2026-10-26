# ness.OS — rebaseline de implantação (26/08/2026)

## Norte único

Entregar primeiro uma operação confiável para a Cavan: saúde geral do cliente
e visão por serviços. O ness.OS consome e contextualiza as fontes; não substitui
Zabbix, GLPI ou Wazuh como sistemas especializados.

## Estado factual

| Componente | Estado | Papel agora |
|---|---|---|
| Zabbix origem `144.91.72.202` | Server ativo; produção atual | continua sendo a coleta canônica |
| Zabbix destino `169.58.234.9` | frontend e banco restaurado; Server mascarado | UAT de transmutação, sem coleta |
| Backup Zabbix | cópia externa já foi comprovada; backup noturno recente está falhando por timeout | bloqueador de corte |
| Authentik + SAML Zabbix UAT | homologado | identidade pronta para UAT |
| GLPI | instalado | ITSM/CMDB a regularizar e conectar ao piloto |
| ness.OS | backend testado e frontend compilado | portal ainda não é fonte operacional canônica |
| Wazuh / Google Workspace | planejados | não bloqueiam o primeiro go-live |

## Sequência obrigatória

### Onda 0 — Proteger e tornar o Zabbix recuperável

1. Diagnosticar e corrigir o timeout do backup noturno na origem, na janela
   aprovada do Zabbix.
2. Comprovar um novo backup `COMPLETED`, checksum, upload externo, `restic
   check` e restore isolado.
3. Repetir a sincronização para a UAT usando essa cópia recente.

**Aceite:** origem recuperável com RPO de 24 h; nenhum corte enquanto o backup
mais recente não estiver comprovado.

**Diagnóstico em 26/08:** `dbzabbix` ocupa aproximadamente 50 GiB; o dump
consistente é intencionalmente executado com prioridade baixa e foi terminado
por `TimeoutStartSec=3h` em 24 e 25/08. A correção preparada amplia o limite
para 6 h e move a cópia ao Object Storage para 05:30 BRT, depois da janela
local. Ela aguarda aplicação e validação na janela Zabbix.

### Onda 1 — Zabbix UAT e piloto Cavan–Matriz

1. Comparar origem e UAT após a sincronização; preservar `zabbix-server`
   mascarado na UAT.
2. Fechar polimento dos 14 ativos Cavan–Matriz: tags, owner, criticidade,
   localização, mapas de infraestrutura e serviços e redução de ruído.
3. Definir a saúde geral da Cavan por serviços: conectividade, rede, diretório,
   virtualização, aplicações, dados e monitoramento.
4. Homologar acesso SAML dos administradores e a conta local break-glass.
5. Executar o cutover somente com janela, rollback, backup novo e autorização
   explícita. Até lá, o destino é somente UAT.

**Aceite:** Cavan possui visão técnica coerente no UAT; origem ainda preservada
até a aceitação formal do corte.

### Onda 2 — ITSM, inventário e portal operacional

1. Regularizar GLPI como CMDB/ITSM, catálogo e conhecimento operacional.
2. Ativar inventário pelo GLPI Agent através do RMM presente em cada ativo.
3. Conectar os serviços Cavan a ativos, tickets e indicadores.
4. Publicar no ness.OS a visão executiva read-only: saúde geral, serviços,
   incidentes confirmados, inventário e projetos.
5. Inserir a PWA para técnicos como jornada móvel, sem automação corretiva.

**Aceite:** um incidente confirmado percorre fonte técnica → AIOps → GLPI →
portal, com segregação de tenant e evidência.

### Onda 3 — AIOps controlado

1. Receber eventos qualificados do Zabbix; deduplicar e correlacionar.
2. Criar incidentes, RCA assistida e runbooks no fluxo de aprovação humana.
3. Medir qualidade da coleta, ruído e indicadores executivos.
4. Manter qualquer remediação automática desligada até métricas e rollback
serem comprovados.

**Aceite:** operação recebe incidentes, não uma enxurrada de alertas; todo
incidente possui fonte, responsável e trilha no ITSM.

### Onda 4 — SecOps e expansão

1. Provisionar Wazuh hub-spoke quando a VPS dedicada estiver aprovada.
2. Integrar o Google Workspace único da Cavan por auditoria read-only, após
delegação do Super Admin; Alert Center fica fora do piloto por exigir escopo
com escrita.
3. Expandir Cavan para unidades fabris pelo modelo de serviços, não por novos
tenants.
4. Escalar VPS e workers por métricas reais, até 5.000 endpoints.

**Aceite:** SecOps é isolado por cliente, recuperável e não compromete a
operação NOC/ITSM já estabilizada.

## Regras de prioridade

- Nada novo entra antes de backup verificável, identidade e rollback da onda
  corrente.
- Cada onda só abre quando o aceite da anterior estiver evidenciado.
- Wazuh, integrações SaaS e automação são aceleradores; não devem atrasar a
  estabilização do Zabbix, GLPI e portal.
- Hardening e branding entram ao fim da estabilização funcional de cada
  componente, antes de ele ser declarado produção.
