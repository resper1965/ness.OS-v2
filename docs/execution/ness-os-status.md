# ness.OS — indicador de entrega

Última verificação: **13/10/2026, 13:50 BRT**. Fonte: plano master,
`PROJECT_CONTEXT.md`, estágio operacional, ledger e GitHub. Este quadro é um
checkpoint, não telemetria em tempo real. Atualizar quando uma entrega, gate,
bloqueio ou prazo mudar; preservar a data da última verificação.

**Estado global: 🔴 produção completa ainda não liberada.** Nenhuma fase
inteira abaixo deve ser chamada de concluída por CI verde, serviço `running`,
preparação UAT ou documentação isolada.

| Frente do master | Estado | Evidência e próximo marco |
|---|---|---|
| F0 — release/continuidade | 🟡 Parcial | PR 65 integrado na `main` em `8563f69`, por exceção pontual autorizada; proteção restaurada e conferida. PR 64 atualizado sobre a `main` em `3737172`, cinco checks PASS, ainda draft e amplo (722 arquivos). Publicação candidata no run `38433314272` falhou no push: GHCR `write_package` negado; pacotes privados `ninf-api`/`ninf-frontend` existentes não estão vinculados ao repositório. Grant de Actions com análise de risco registrado na issue #80 e enviado ao titular; nenhum digest novo nem deploy. G0/G1 globais não declarados PASS. |
| F1 — Authentik/tenant/Psono | 🟡 Parcial | Marca e login público Authentik verificados; MFA nominal, recuperação, jornadas autenticadas/tenant e Psono dedicado ainda sem aceite. G2 aberto. |
| F2 — Zabbix definitivo | 🟡 UAT preparada | Destino restaurado e isolado; origem segue única coletora. Referência: 262 hosts reais + 63 protótipos; 2,086% unsupported na última amostra. SSO nominal, qualidade da frota, gates, freeze e GO faltam antes do corte. Janela até 15/10 11:47:35 BRT; token anterior expirado. |
| F3 — GLPI | 🟡 Em execução | Volume persistente e borda pública corrigidos; busca idempotente, paginação e URL privada do gateway endurecidas na branch, sem deploy. API real confirmou o contrato de paginação. Conta 106 desativada; gateway candidato, três ativos e replay aguardam T03. Ações automáticas: 18 internas atrasadas, sem conversão; `graph` elimina arquivos antigos e não serve como canário sem efeito. Os sete agentes têm último contato em julho; piloto autenticado/isolamento registrados na issue #79, não executados. Deduplicação restante e tema ness. aguardam decisão/teste nominal. |
| F4 — Hub/PWA | 🟡 Parcial | Runtime anterior promovido e rollback ensaiado; mudanças recentes estão só na branch. G3 e jornada produtiva por tenant/perfil não aceitos. |
| F5 — operação integrada | 🔴 Pendente | Sem prova produtiva completa evento → incidente → ticket, replay/timeout, papéis e todas as entidades. G4 não aprovado. |
| F6 — AIOps/automação | 🟡 Parcial | Componentes existentes, mas RCA/Node-RED e jornadas assistidas ampliadas sem aceite produtivo global. |
| F7 — Wazuh/Workspace | ⚪ Sem aceite | Capacidade/custo, isolamento, ingestão e rollout por faixa ainda pendentes. G5 não aprovado. |
| F8 — marca/sustentação | 🟡 Parcial | Camadas ness. aplicadas em algumas superfícies; render nominal GLPI, marca completa, runbooks testados e observação D+1/D+3/D+7 após cortes ainda pendentes. |

**Foco agora:** GLPI T03. PR 65 foi integrado; próxima liberação depende da
revisão técnica do PR 64, acesso de escrita seguro aos pacotes GHCR,
imagem por digest e integração do PR 64,
imagem publicada por digest e matriz negativa real da rota direta, rota
pública autenticada e entidade descendente; só então considerar ativar a
identidade mínima 106 e reconciliar ativos/tickets em ondas. Trabalho
independente GLPI continua. Zabbix não corta por extensão da janela apenas.

**Regra do indicador:** 🟢 = aceite comprovado; 🟡 = entrega parcial ou em
execução; 🔴 = gate obrigatório não satisfeito; ⚪ = sem aceite produtivo.
Nunca converter estados em porcentagem inventada.
