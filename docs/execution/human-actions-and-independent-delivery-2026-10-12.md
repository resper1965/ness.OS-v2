# ness.os — ações humanas e entrega independente

Decisão do usuário em 12/10/2026: G2 permanece aberto em issues; pessoas estão
indisponíveis nos próximos dias. Continuar toda implementação técnica que não
depende do aceite humano.

## Registro obrigatório

Toda nova dependência humana deve reutilizar ou criar uma issue com responsável,
estado observado, passos exatos, evidência esperada e critério de fechamento.
Enviar instruções por e-mail ao responsável e registrar o envio sem segredos.
Não aguardar resposta para executar trabalho independente. Não duplicar issues
ou e-mails de cobrança quando não houver mudança acionável.

| Ação | Issue | Responsável |
| --- | --- | --- |
| MFA nominal Authentik | #66 | Ricardo, Ismael, Rogerio |
| MFA e recuperação Psono | #43 | Ricardo e Ismael |
| VPS dedicada Psono | #48 | Ricardo |
| Dois recipients age e recovery independente | #45 | Ricardo e Ismael |
| UAT nominal por aplicação | #51 | responsáveis por aplicação |
| Recovery por e-mail | #44, #59 | Ricardo e Ismael |
| Faturamento Actions e revisão dos PRs | #67 | Ricardo e revisor elegível |
| Docker Desktop/WSL para ensaio isolado | #69 | Ricardo |
| Índice e política de execução | #68 | plataforma |
| Troca segura do volume `/var/glpi` antes de recriar GLPI | #76 | Ricardo (GO), Ismael (execução) |

URLs: `https://github.com/resper1965/n-infraops/issues/<número>`.
E-mails consolidados enviados em 12/10 pela conta conectada resper@bekaa.eu:
Ricardo (resper@ness.com.br), Ismael (iaraujo@ness.com.br) e Rogerio
(rsalerno@ness.com.br). Contêm links das issues e passo a passo; nenhum segredo.
Em 13/10 foi enviada uma instrução única para a issue #76 a Ismael, com
Ricardo em cópia: registrar mudança aceita, owner/aprovador, janela, último
backup `COMPLETED`, critérios de aborto e GO. O envio não equivale à aprovação.

## Trilha executável

1. Zabbix: baseline e qualidade em leitura; planejamento das ondas, exports,
   templates e rollback; preservar janela 22:00–00:00 BRT para produção.
2. Fluxo Zabbix → Hub → GLPI: testes e ensaio isolado, replay, falha parcial,
   recuperação e auditoria.
3. Runtime: readiness, filas, retry e testes de falha em ambiente isolado.
4. Interface: proveniência, frescor, estados indisponíveis e branding.
5. Recuperação e runbooks: renovar evidências, instrumentar falhas e preparar
   promoção revisável.

Corte Zabbix, promoção do cofre, automações privilegiadas e aceite produtivo
MVP mantêm seus gates. Issues não aprovam G2.

## Execução iniciada

121 testes de idempotência GLPI e readiness de Zabbix/GLPI passaram. O runner
local recebeu a dependência já declarada pywebpush em venv temporário. Um teste
com PostgreSQL/Redis foi inicialmente pulado por depender de Docker, cujo
daemon local estava parado. Este resultado não comprova o fluxo real GLPI nem
o aceite produtivo.

A suíte completa do backend também passou: **411 testes aprovados, 1 pulado**.
O único pulado é o ensaio PostgreSQL/Redis descrito acima, acompanhado pela
issue #69 e por e-mail de instrução ao Ricardo. Estes testes usam doubles para
as APIs externas; não representam UAT humana nem escrita produtiva GLPI.
