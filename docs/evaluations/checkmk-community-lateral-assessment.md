# Avaliação lateral — Checkmk Community no ness.OS

> Data: 21/08/2026
> Regra do projeto: somente edição Community/open source; capacidades Pro/Ultimate não contam como solução disponível.

## Veredito

O Checkmk Community **não deve substituir o Zabbix nem entrar como segundo monitoramento canônico** no ness.OS. Ele é tecnicamente interessante para descoberta automática, organização por regras e cobertura de dispositivos, mas a edição comunitária é oficialmente posicionada para cerca de 100 hosts, enquanto o ness.OS tem meta de 7.000 ativos. A diferença de escala é de aproximadamente 70 vezes.

A decisão não desqualifica o produto: o Checkmk será usado como referência para o polimento lógico do Zabbix. Um laboratório descartável de 20–30 ativos pode ser realizado depois, caso seja necessário medir a experiência de descoberta e a cobertura de equipamentos. Esse laboratório não deverá gerar incidentes, tickets ou outra fonte canônica de estado.

## Comparação aplicada ao cenário

| Critério | Checkmk Community | Efeito no ness.OS |
|---|---|---|
| Escala oficial | Aproximadamente 100 hosts | Incompatível com a meta de 7.000 ativos sem depender de edição comercial ou assumir risco não respaldado pelo fabricante |
| Núcleo de monitoramento | Nagios Core | Em grande escala, alterações de configuração e consumo de CPU tornam-se riscos; o Checkmk Micro Core otimizado é comercial |
| Descoberta de serviços | Forte, automática e com tratamento de serviços novos/desaparecidos | Conceito que deve orientar o polimento do Zabbix |
| SNMP e integrações | SNMP v1/v2c/v3 e amplo catálogo de plug-ins | Bom para acelerar onboarding e servir de referência à matriz de cobertura do Zabbix |
| Agentes | Pacotes e plug-ins básicos disponíveis | Agent Bakery, pacotes personalizados e atualização automática são comerciais; isso pesa muito em 7.000 ativos |
| Monitoramento distribuído | Tecnicamente possível na Community, com mais sincronização e operação manual | Não equivale ao modelo pronto para escala; aumenta custo e risco operacional |
| Multi-tenant/MSP | Isolamento multi-tenant é produto Ultimate comercial | Não atende o requisito de clientes segregados sob a regra Community-only |
| Dashboards e relatórios | Dashboard básico disponível | Dashboards avançados, analytics e relatórios/PDF ficam nas edições comerciais |
| API | REST/OpenAPI disponível para recursos comunitários | Adequada para automação, mas não compensa as lacunas de escala e tenancy |
| Authentik/SSO | SAML nativo é comercial; na Community exige integração manual pelo servidor web | Aumentaria a fragmentação de identidade que o projeto já precisa reduzir |
| Estado atual | Seria uma implantação nova e paralela | Duplicaria inventário, regras, credenciais e diagnóstico sem substituir GLPI, Zabbix ou Wazuh |

## Onde o Checkmk é melhor como referência

1. **Descoberta e ciclo de vida de serviços:** tornar explícitos os itens novos, desaparecidos, desabilitados e pendentes de decisão.
2. **Configuração orientada por regras:** aplicar política por cliente, localidade, tecnologia, criticidade e classe de ativo, evitando exceções manuais por host.
3. **Onboarding de equipamentos:** comparar a cobertura nativa de fabricantes e identificar lacunas nos templates Zabbix.
4. **Visão de problemas:** reduzir ruído e favorecer uma tela operacional simples antes de acrescentar novos painéis.
5. **Organização por sites:** usar localização e função do ativo na arquitetura de proxies, mapas, macros e ownership do Zabbix.

Esses pontos entram no polimento do Zabbix, sem adicionar outra plataforma permanente.

## Por que o Zabbix permanece canônico

- já está em operação e concentra o trabalho de saneamento e migração aprovado;
- não exige trocar o núcleo de monitoramento por uma edição comercial para o desenho de escala;
- encaixa-se no modelo de proxies, mapas/localização e integrações já previsto;
- evita duas fontes de verdade para disponibilidade e incidente;
- preserva o orçamento e a capacidade da equipe para GLPI, Authentik, Hub AIOps, cofre e Wazuh.

## Laboratório opcional, não aprovado por padrão

Se houver dúvida residual baseada em equipamentos específicos, executar por 7–14 dias com:

- 20–30 ativos representativos e credenciais SNMP somente leitura;
- contêiner ou VM efêmera, sem nova VPS permanente;
- nenhuma integração com GLPI, incidentes, notificações ou automações de produção;
- métricas de cobertura, tempo de onboarding, ruído, consumo e esforço de manutenção;
- remoção completa ao final e incorporação apenas das lições úteis ao backlog Zabbix.

O laboratório só se justifica para responder uma hipótese concreta; não é etapa obrigatória nem autorização de implantação.

## Fontes oficiais

- [Preços e posicionamento das edições](https://checkmk.com/pricing)
- [Seleção e diferenças entre edições](https://docs.checkmk.com/latest/en/intro_setup.html)
- [Checkmk Micro Core e limitações do núcleo Nagios em escala](https://docs.checkmk.com/latest/en/cmc.html)
- [Monitoramento distribuído](https://docs.checkmk.com/latest/en/distributed_monitoring.html)
- [Agentes e Agent Bakery](https://docs.checkmk.com/latest/en/wato_monitoringagents.html)
- [Descoberta e ajuste fino de serviços](https://docs.checkmk.com/latest/en/intro_finetune.html)
- [Monitoramento por SNMP](https://docs.checkmk.com/latest/en/snmp.html)
- [API REST](https://docs.checkmk.com/latest/en/rest_api.html)
- [Dashboards](https://docs.checkmk.com/latest/en/dashboards.html)
- [Relatórios](https://docs.checkmk.com/latest/en/reporting.html)
- [SAML](https://docs.checkmk.com/latest/en/saml.html)
