# Avaliação — Vigil (SOC agêntico) no ness.OS

> Data: 11/11/2026
> Fonte: README público do projeto (`github.com/Vigil-SOC/vigil`) e notas de imprensa, lidos em 11/11.
> **Nada foi instalado nem testado.** Nada aqui autoriza instalação, compra ou ingestão.

## Veredito

O Vigil **não substitui o ness.OS nem o módulo n.secops**. Ele cobre uma função que o Hub ainda não tem:
investigar um caso em vários passos, com agentes e ferramentas. O Hub hoje classifica o alerta em uma
chamada ao modelo e para aí.

Ele entra no plano como **candidato a uma única função**: investigação dos casos `TRIAGE_L2`, atrás do
Hub, como componente de borda substituível. A adoção depende de um laboratório em que ele precise
**ganhar da linha de base** (o que o Hub já faz, mais a entrega E1 do plano). Se não ganhar, não entra.

## O que o Vigil é

| Item | Fato lido |
|---|---|
| Origem | Projeto da DeepTempo, lançado em março de 2026. |
| Licença | Apache 2.0. |
| Maturidade | Versão 1.0.0 publicada em 30/10/2026 (corrigido em 12/11). `main` é o ramo de desenvolvimento. 404 estrelas, 1.571 commits. |
| Pilha | Docker com PostgreSQL, Redis e um gateway de LLM (Bifrost); Node.js 20+; Python. Tem chart Helm. |
| Agentes | Triagem, investigação, hunting, correlação, resposta, relatório, ATT&CK, forense, threat intel, compliance, malware e rede. |
| Extensão | Fluxos em Markdown, integrações por MCP. Expõe as próprias operações em `/mcp`. |
| Entrada de alertas | Um daemon faz polling. Integrações citadas: Splunk, Sentinel, Google SecOps, CrowdStrike (várias experimentais). **Wazuh não é citado. Webhook de entrada não é citado.** |
| Modelos | Anthropic (padrão), OpenAI, Vertex e Ollama local. **OpenRouter não é citado.** |
| Acesso | Uma conta de administrador criada na primeira visita. **Não descreve tenants, organizações nem papéis.** |
| Aprovação | Ação de resposta vira pedido de aprovação. Há um limiar configurável: confiança ≥ 0,90 **aprova sozinha**. O fluxo de aprovação registra `isolate_host`, mas não executa. |
| Imagens | Publicadas com assinatura (cosign). |

## Confronto com as regras do ness.OS

| Regra | Situação | O que exige |
|---|---|---|
| ADR 0010: licença OSI no que é autohospedado | Vigil passa (Apache 2.0). Redis e Bifrost, que vêm no pacote, **não foram conferidos**. O ADR 0010 já trocou Redis por Valkey. | Conferir licença e versão de cada componente do pacote. |
| ADR 0010: versão e digest fixos | 1.0.0 disponível. | Só usar tag de release, com digest. |
| F6: nenhuma remediação privilegiada autônoma | O limiar de 0,90 aprova sozinho. | Vigil **sem nenhuma integração de resposta**. Assim não há o que executar. |
| F7: payload bruto não entra em IA | Vigil foi feito para consultar a fonte direto. | Vigil recebe só o pacote de evidência que o Hub monta. |
| F7: modo observação sem IA | — | Vigil só depois do primeiro gate da F7. |
| Isolamento por tenant | Não descrito. É o critério que pode eliminar o Vigil. | Provar no laboratório que o caso de um cliente não aparece na investigação de outro. |
| `AIRequestV1`: sanitização e teto de custo | Vigil chama o modelo por gateway próprio. | Sanitizar no Hub antes de enviar; teto de gasto próprio na chave do Vigil. |
| ADR 0012: Zabbix, Wazuh, GLPI e ness.OS são a arquitetura oficial | — | Vigil não vira console, fonte de verdade nem entrada de eventos. |

## O que o Hub já tem (linha de base)

- Motor de risco sem modelo: abaixo do limiar arquiva, e só o que sobra chega ao modelo.
- Uma chamada de classificação com prazo de 45 s, validação da resposta e sanitização.
- Decisão persistida (`n_secops_soc_decisions`) com alerta bruto, classificação, confiança e resumo.
- Idempotência, vínculo por tenant e limiares por contrato.

Falta: investigação em vários passos, e o registro do que o modelo recebeu e respondeu.

## Riscos de adotar

1. **Projeto novo, 1.0.0 há poucas semanas.** Mudanças que quebram a integração ainda são prováveis.
2. **Roteiro de um fornecedor.** A DeepTempo usa o Vigil como entrada para o produto pago dela (LogLM). O LogLM é opcional e fica fora.
3. **Custo por caso.** Investigação com vários agentes gasta muito mais que uma chamada. Só dá para saber medindo.
4. **Mais uma pilha para operar.** Banco, cache, gateway e atualizações próprias.

## Outras ferramentas vistas na mesma pesquisa

| Ferramenta | Decisão | Motivo |
|---|---|---|
| Tines | Fora | SaaS proprietário; o ADR 0010 bloqueia. |
| Shuffle | Fora | O orquestrador escolhido é o Node-RED; seria um segundo. |
| AiSOC | Fora como ferramenta | Sobrepõe o Hub (ingestão, casos, console). |
| AlertSage | Fora como ferramenta | Projeto pessoal pequeno. |

Duas ideias dessas ferramentas entram no plano como entrega E1, sem depender do Vigil:

- **Divergência como sinal** (AlertSage): quando o motor de risco e o modelo discordam, a decisão é marcada e entra numa lista de revisão. Não muda o atendimento, que o Hub já decide antes do modelo.
- **Registro da decisão que dá para refazer** (AiSOC): guardar o que o modelo recebeu, qual modelo respondeu e a resposta.

## Próximo passo

[ADR 0022](../adr/0022-vigil-l2-investigation.md) (proposto) e
[plano de entregas](../superpowers/plans/2026-11-11-vigil-investigacao-l2.md).
