# ADR 0016 — Integrações com o Microsoft 365

- Status: aceita
- Data: 05/11/2026
- Decisor: Ricardo Esper
- Relaciona: [ADR 0015](0015-entra-id-identity-local-authorization.md) (Entra ID como identidade)

## Contexto

A ness. migrou do Google Workspace para o Microsoft 365. O ADR 0015 decidiu usar o Entra ID como provedor de identidade e desligar o Authentik. O M365 entrega mais peças além da identidade, e algumas podem servir ao ness.OS sem custo adicional. Outras exigem licença não contratada e não estão disponíveis.

Este ADR cataloga o que está disponível, o que está fora e as regras para construir qualquer integração.

## Decisão

### O que está disponível (custo adicional zero)

| Peça | O que entrega | Uso possível no ness.OS | Quando |
|---|---|---|---|
| **Entra ID** | Identidade, OIDC, MFA, convidados B2B | Identidade central dos operadores e clientes | Decidido no ADR 0015; pós-gate da Fase 0 |
| **Microsoft Graph API** | API REST unificada do M365 | Consultar identidade, validar MFA, ler convidados | Bloqueado até a Fase B do ADR 0015 |
| **Microsoft Teams** | Webhooks de entrada | Canal 2 do atendimento SOC | P3, se o cliente aceitar Teams como canal |
| **Exchange Online** | E-mail | Notificação de backup, relatório automático | Após os dois canais principais do P3 |

### O que está indisponível (licença não contratada)

| Peça | Por quê | O que exigiria |
|---|---|---|
| **Defender for Endpoint** | Sem licença de EDR | Licença Defender for Business ou P2 |
| **Defender for Office 365** | Sem licença | Licença Defender for Office 365 |
| **Purview (Audit, eDiscovery)** | Sem licença, **não confirmada no tenant**; confirmar antes de depender dela | Licença de conformidade |
| **Intune** | Sem licença de MDM | Licença Intune ou EMS |
| **Sentinel (SIEM)** | Sem licença de SIEM | Custo por GB ingerido, sem teto |
| **Power Platform (Automate, Apps, BI)** | Sem licença | Licença premium por usuário |
| **Microsoft Copilot** | Sem licença | Licença por usuário; o custo não é previsível |

### Regras para qualquer integração com o M365

1. **Nenhuma integração nova sem ADR específica.** Este catálogo não autoriza construir nada. Cada peça exige um ADR próprio que defina escopo, custo, dependência e rollback.
2. **Custo adicional zero.** A integração usa o que o M365 atual da ness. já entrega. Se exigir licença nova, entra como decisão de compra, não como decisão de arquitetura.
3. **Conector só com contrato fechado.** Nenhum conector do M365 é construído sem o contrato de sinal ou o contrato de saída fechado com o consumidor.
4. **Identidade primeiro.** As integrações que dependem do Entra ID como identidade (Graph API, convidados B2B) só entram depois da Fase B do ADR 0015 — nunca antes.
5. **Sem dependência circular.** Uma integração não pode depender de outra que ainda não existe. Teams e Exchange são independentes entre si e independentes da identidade; Graph API depende da identidade.

### O que não se aplica

- **Magic WAN, Magic Transit, WAF:** já avaliados no desenho de identidade e perímetro.
- **Intune, Defender e Purview:** exigem licença não contratada. O Acesso Condicional depende de Entra ID P1; hoje o STATE registra MFA por *security defaults*, sem P1. Confirmar a licença antes de depender dele.
- **Qualquer feature que exija Entra ID P1 ou P2:** o MFA vigente é *security defaults*, sem licença. O ADR 0015 prevê P1 para operadores, ainda não contratado.

## Consequências

- Nenhum código, conector, tipo de sinal ou tipo de saída do M365 é construído sem ADR.
- O catálogo de disponíveis não é um backlog: é um inventário para decisão futura.
- Se um cliente exigir Teams ou e-mail como canal, o ADR do P3 cobre.
- Se a autorização local do ADR 0015 se mostrar insuficiente, a Graph API é o próximo passo documentado.
- Peças indisponíveis não voltam à discussão sem decisão de compra.
- A lista de licenças é a conhecida em 05/11/2026. Confirmar no centro de administração do M365 antes de qualquer decisão que dependa dela.