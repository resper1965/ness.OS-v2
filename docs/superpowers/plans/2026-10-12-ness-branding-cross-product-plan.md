# ness. — customização transversal do ness.OS

> Planejamento compartilhado por todos os planos de produto. Não executar com o modelo autor. Usar Ponytail full e skill `ness-branding`: máxima cobertura útil pelos recursos suportados, mínimo código próprio.

## Direção única

- Marca `ness.` em caixa baixa, sem itálico; wordmark Montserrat Medium 500, letras pretas/brancas e ponto #00ade8. Reutilizar assets aprovados, sem redesenhar ou inventar favicon.
- Uma marca por região visual. Título descreve a tarefa; não repetir logo + “ness.” + subtítulo. Nome técnico ness.OS, slugs, client IDs, marcadores e contratos existentes não são renomeados como efeito cosmético.
- Largura útil no desktop, alinhamento à esquerda, navegação estável, grid 8px, superfícies sóbrias, sombras suaves, animação discreta e reduced-motion. Azul da marca não substitui cores semânticas de alerta.
- Textos em pt-BR, horários explicitamente localizados, erros com próxima ação, carregamento e vazio claros. Dados antigos/indisponíveis nunca recebem aparência de saúde.
- Acessibilidade: contraste AA, foco/teclado, zoom 200%, toque 48px e uma descrição acessível por logo. Preservar funcionalidade em 390px/1440px e temas suportados.

## Cobertura por produto

| Produto | Superfícies a personalizar | Caminho e limite |
|---|---|---|
| Authentik | Login, Google, senha, MFA, enrollment, recuperação, consentimento, logout, erros, biblioteca, perfil, admin, emails, favicon/títulos | Brands, fluxos, aplicação e templates suportados; ampliar CSS existente sem esconder controles |
| GLPI | Entrada SSO, portal solicitante, catálogo/formulários, fila técnica, tickets/acompanhamentos, ativos, conhecimento, painéis, relatórios/exportações e emails futuros | Configuração/plugin compatível; preservar estados/permissões e atribuições legais. Email só prévia até autorização do canal |
| Zabbix | Entrada, cabeçalho/menu, logo/favicon, NOC, qualidade/capacidade, cliente, mapas, relatórios e mobile | Hook/módulo nativo existente, dashboards e mídia suportada; não alterar core ou cores de severidade para decorar |
| Hub/PWA | Shell, navegação, visão geral, incidentes, ativos, tickets, fontes, estados de erro, instalação, ícones e suporte | Componentes/tokens existentes, sem biblioteca visual paralela; ícones PWA aprovados, cache não simula dado atual |
| Psono | Entrada, cofre, organização, compartilhamento, recuperação e ajuda | Somente recursos da edição instalada; não alterar criptografia, permissões ou interação de segredos |
| Grafana | Pastas, dashboards, variáveis, títulos, legendas, links e relatórios suportados | Branding global depende da edição/licença; não presumir white-label gratuito nem remover marca obrigatória |
| n8n / Node-RED | Nomes de fluxos, descrições, ajuda operacional, painéis de usuário quando existentes | Consoles técnicos mantêm identidade/licença obrigatória; não criar editor próprio ou migrar fluxo por motivo visual |
| Wazuh | Dashboards, navegação operacional, tenant, contexto de alerta e relatórios | Configuração suportada após implantação; permanece planned até gate, sem telas fictícias de operação |

## Execução enxuta por produto

1. Inventariar cada superfície da tabela, versão/edição e mecanismo suportado. Marcar `existente`, `a personalizar`, `não aplicável` ou `limitada pela edição` com motivo.
2. Reutilizar assets/tokens já aprovados. Preferir configuração, depois extensão instalada, por último pequena extensão compatível. Não comprar licença ou plugin sem autorização.
3. Preparar visual local/UAT enquanto dependências funcionais são tratadas. Promover junto da jornada aprovada; personalização não autoriza mudar autenticação, dados ou contratos.
4. Exportar configuração anterior e registrar deltas; verificar precondição para não sobrescrever edição humana. Reaplicação idempotente não duplica menus, painéis ou assets.
5. Verificar uma jornada real por persona, seus erros e versão móvel. Testar componentes alterados; não repetir suites de produtos intocados.
6. Registrar reversão e um ensaio de compatibilidade com atualização pertinente. Não fixar versão insegura apenas para preservar CSS.

Na implementação, criar **um** manifesto `config/branding/ness-surfaces.json` com produto, superfície, mecanismo, asset, status, evidência e rollback. O arquivo é proposto, não criado por este planejamento. Não criar biblioteca compartilhada que obrigue produtos diferentes a usar o mesmo runtime; compartilhar critérios e assets.

## Ajustes consolidados dos planos existentes

- GLPI T10/T11 incorpora toda a linha GLPI da matriz, incluindo catálogo, conhecimento e saídas documentais; customização não se limita à tela inicial.
- Zabbix etapa 5 incorpora toda a linha Zabbix, preservando os painéis e branding já aplicados. Coleta e corte permanecem prioritários.
- Authentik etapa 5 incorpora todas as jornadas, além de login inicial já aprovado.
- Roteiro geral de 11/10, tarefa 10.3, usa esta matriz como definição de cobertura; planos de Hub/PWA e aceite integrado herdam os mesmos critérios.
- Planos legados que recomendam SQL direto para marca/perfis ou plugin sem compatibilidade comprovada são referência histórica, não instrução de execução.

## Critério de conclusão

Todas as superfícies aplicáveis têm marca consistente, legibilidade, jornada funcional, evidência e retorno. Limitação de edição, falta de asset ou campo não customizável fica explícita; não simular suporte com overlay frágil. Não remover avisos, licenças, atribuições ou elementos de segurança para obter white-label.

O resultado esperado é uma experiência reconhecível como ness., com controles e informações próprios de cada ferramenta preservados. Este plano não contém aplicação de CSS, instalação, envio de email ou mudança produtiva.
