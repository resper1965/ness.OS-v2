# n.infraops — UX/UI Design System

Este documento define a fundação visual da plataforma B2B `n.infraops`, baseada na captura de branding do site oficial `ness.com.br` e nas práticas de inteligência de design B2B SaaS.

## Identidade e Posicionamento (Branding)
- **Logotipo e Marca ("ness."):** Deve ser sempre representada na fonte **Montserrat** (peso Medium - 500), em caixa baixa ("ness."). A cor do texto principal é preta ou branca (a depender do contraste com o fundo), e o **ponto final (".") deve ser obrigatoriamente na cor `#00ADE8` (Ciano).**
- **Vibe:** "Tecnologia de precisão", DevSecOps, Segurança Cibernética, Alta Performance.
- **Público:** B2B Corporativo, Engenheiros, SysAdmins.
- **Estilo Base:** **Dark Mode Nativo** (baseado no `theme-color: #0a0a0f` capturado), transmitindo um ambiente de monitoramento, SOC (Security Operations Center) e foco em métricas.

## 1. Paleta de Cores (Dark Theme B2B SaaS)

| Função | Hex Code | Uso |
|--------|----------|-----|
| **Background Base** | `#0A0A0F` | Fundo principal da aplicação (direto do site da Ness). |
| **Superfícies/Cards** | `#14141B` | Fundo de painéis, tabelas e modais (levemente mais claro que o base para gerar profundidade). |
| **Primary (Brand Accent)** | `#00ADE8` | Cor oficial da marca (ciano do "."). Usada para botões principais de destaque, highlights e logotipos. |
| **Secondary (Accents)** | `#334155` | Bordas, divisores, e botões secundários. |
| **Text Primary** | `#F8FAFC` | Textos principais, títulos e dados em tabelas. |
| **Text Muted** | `#94A3B8` | Textos de apoio, labels de formulários e breadcrumbs. |
| **Status - Success** | `#10B981` | (Emerald 500) Indicadores de serviços online/OK (Zabbix). |
| **Status - Danger/Alert** | `#EF4444` | (Red 500) Alertas críticos de infraestrutura. |

## 2. Tipografia

- **Fonte de Logotipo/Marca:** Montserrat (500, Lowercase)
- **Fonte Principal da UI:** [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans)
- **Pesos:** 
  - `300` e `400` para body/textos de parágrafos.
  - `500` e `600` para botões e labels.
  - `700` para Headers (H1, H2) e números em dashboards.

## 3. Estilo e Efeitos Visuais (Glassmorphism & Precisão)

- **Cards e Painéis:** Fundo sólido escuro (`#14141B`) com bordas muito sutis de `1px solid rgba(255, 255, 255, 0.05)`.
- **Modais e Navegação (Glassmorphism):** Overlays com `backdrop-blur` de 10px a 20px.
- **Interações (Hover):** Transição suave de `150ms a 300ms`.
- **Tabelas de Dados:** Uso amplo de espaço negativo escuro, linhas divisórias finas e foco direto na leitura do status.

## 4. Ícones
- Uso estrito de ícones SVG vetorizados (Lucide ou Heroicons). 
- Sem uso de emojis na interface.
- Tamanhos padronizados (`24x24px`, `16x16px`).
