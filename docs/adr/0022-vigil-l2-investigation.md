# ADR 0022 — Vigil como candidato à investigação de casos L2

- Status: **proposta**; aguarda decisão do Ricardo
- Data: 11/11/2026 (revisado em 12/11/2026)
- Decisor: Ricardo Esper
- Relaciona: ADR 0001 (SOC em segunda etapa), ADR 0010 (fronteira open source), ADR 0012 (arquitetura oficial)

## Contexto

O n.secops classifica o alerta em uma chamada ao modelo. Ele não investiga: não busca eventos
relacionados, não monta linha do tempo, não propõe hipótese. O Vigil é um SOC agêntico open source
(Apache 2.0) que faz isso. A [avaliação](../evaluations/vigil-agentic-soc-assessment.md) mostra que ele
não substitui o Hub e que tem lacunas sérias para o nosso uso: sem multi-tenant descrito e sem
Wazuh entre as integrações citadas. A versão 1.0.0 saiu em 30/10/2026.

## Decisão proposta

O Vigil é **candidato** a uma função só: investigar casos `TRIAGE_L2`, chamado pelo Hub. Fica atrás de
um adaptador substituível, como toda integração de borda (ADR 0010, item 4).

A adoção só acontece se o laboratório (entrega E2 do plano) provar que ele ganha da linha de base. Se
não provar, este ADR é recusado e nada fica instalado.

## Regras que não mudam

- O Hub continua sendo a entrada de eventos, a fonte de verdade do caso e a tela do analista.
- O GLPI continua sendo o registro do atendimento (ADR 0002).
- O Vigil **não recebe integração de resposta** (EDR, firewall, RMM). Ele só lê o que o Hub envia e devolve texto. Remediação segue a regra da F6: aprovação humana, no Hub.
- O Vigil **não acessa** Wazuh, Zabbix nem GLPI direto no primeiro corte. Recebe o pacote de evidência de um caso, de um tenant, já sanitizado pelo Hub.
- O atendimento nunca espera o Vigil. Se ele falhar, demorar ou estourar o teto, o caso segue como hoje e a falha aparece.
- Clientes não acessam o Vigil. Só a equipe SOC da ness.
- LogLM e demais produtos pagos da DeepTempo ficam fora.

## Homologação antes de qualquer integração

Nada abaixo foi verificado. Tudo é respondido no laboratório, com dado sintético ou do tenant interno `ness`.

1. **Entrada e saída:** dá para criar um caso por API ou MCP e ler a investigação de volta, sem o daemon de polling?
2. **Isolamento:** com casos de dois tenants na mesma instância, a investigação de um cita dado do outro? O agente de correlação precisa de atenção especial. **Critério de corte:** se o isolamento entre tenants não estiver documentado pelo projeto, o Vigil é recusado, mesmo que o teste passe.
3. **Sem resposta:** a aprovação automática só registra a decisão; executar exige integração de EDR. Confirmar no laboratório que, sem EDR configurado, nada é executado.
4. **Licenças do pacote:** Redis (ou Valkey no lugar), gateway Bifrost e dependências passam no ADR 0010?
5. **Modelo e custo:** funciona com o provedor que já usamos? Qual o custo e o tempo por caso?
6. **Qualidade:** a investigação é melhor que a linha de base, na leitura de um analista?
7. **Operação:** consumo de CPU, memória e disco; backup, restauração e atualização por digest.

## Consequências

- Nenhuma mudança de código agora. Este ADR e a avaliação são só documentos.
- A entrega E1 do plano (divergência e registro da decisão) não depende deste ADR e vale por si.
- O laboratório só começa depois do primeiro gate da F7.
- Máquina e gasto novos exigem aprovação do Ricardo antes de contratar.
