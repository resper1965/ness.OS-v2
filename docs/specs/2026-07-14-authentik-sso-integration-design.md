# Authentik SSO Integration — Design Spec

> **Data:** 2026-07-14
> **Autor:** resper / antigravity
> **Status:** Aprovado
> **Authentik URL:** `https://sso.ness.com.br`

---

## Objetivo

Integrar o Authentik como Identity Provider (IdP) central para todas as aplicações da plataforma ness., garantindo:
- Single Sign-On (SSO) com login unificado
- Provisionamento automático de usuários (JIT)
- Mapeamento de grupos para roles em cada aplicação
- Authentik como fonte primária de usuários, mantendo compatibilidade com usuários locais existentes

---

## Escopo

### Aplicações Incluídas

| App | URL | Protocolo SSO | Servidor |
|-----|-----|---------------|----------|
| Hub (dashboard n.infraops) | `hub.ness.com.br` | OIDC | Docker (VPS n.infraops) |
| Zabbix 7.0 LTS | `zabbix.ness.com.br` | SAML 2.0 | Contabo VPS separada |
| GLPI | `n-ticket.ness.com.br` | OIDC | Docker (VPS n.infraops) |
| n8n | `n8n.ness.com.br` | OIDC | Docker (VPS n.infraops) |

### Fora do Escopo

| App | Motivo |
|-----|--------|
| Evolution API (`waba.ness.com.br`) | API headless com API key, sem login de usuário |

---

## Grupos e Mapeamento de Roles

### Grupos no Authentik

| Grupo | Descrição |
|-------|-----------|
| `admin` | Administradores com acesso total |
| `noc` | Operadores de monitoramento (NOC) |
| `soc` | Analistas de segurança (SOC) — futuro Wazuh |
| `helpdesk` | Analistas de suporte técnico |
| `gestao` | Gerência e diretoria — dashboards e relatórios |
| `usuarios` | Usuários finais — self-service de chamados |

### Matriz de Mapeamento Grupo → Role por App

| Grupo Authentik | Hub | Zabbix | GLPI | n8n |
|-----------------|-----|--------|------|-----|
| `admin` | `admin` | `Super admin` | `Super-Admin` | `Owner` |
| `noc` | `operator` | `User` (read + ack) | `Observer` | `Member` |
| `soc` | `analyst` | `User` (read) | `Observer` | `Member` |
| `helpdesk` | `support` | — | `Technician` | — |
| `gestao` | `viewer` | `User` (read-only) | `Observer` | — |
| `usuarios` | — | — | `Self-Service` | — |

### Authorization Policies

Cada Application no Authentik terá uma policy que restringe acesso por grupo:

| Application | Grupos Permitidos |
|-------------|-------------------|
| Hub | `admin`, `noc`, `soc`, `helpdesk`, `gestao` |
| Zabbix | `admin`, `noc`, `soc`, `gestao` |
| GLPI | `admin`, `helpdesk`, `usuarios`, `noc`, `soc`, `gestao` |
| n8n | `admin`, `noc`, `soc` |

---

## Integração por Aplicação

### 1. Hub (React + FastAPI) — OIDC

**Provider no Authentik:**

| Campo | Valor |
|-------|-------|
| Tipo | OAuth2/OIDC Provider |
| Client ID | `hub-ness` |
| Client Type | Confidential |
| Redirect URI | `https://hub.ness.com.br/auth/callback` |
| Post-Logout Redirect | `https://hub.ness.com.br` |
| Scopes | `openid`, `email`, `profile`, `groups` |
| Signing Key | Authentik self-signed (default) |

**Mudanças no código:**

- **FastAPI (backend)**:
  - Novo módulo `app/auth/oidc.py` — troca authorization code por token, valida JWT
  - Novo endpoint `GET /auth/callback` — recebe code do Authentik, cria sessão
  - Novo endpoint `GET /auth/login` — redireciona para Authentik authorize URL
  - Novo endpoint `GET /auth/logout` — invalida sessão, redireciona para Authentik end_session
  - Middleware: validar JWT em todas as rotas protegidas
  - JIT provisioning: no primeiro login, criar usuário local com dados dos claims

- **React (frontend)**:
  - Botão "Entrar com SSO" na tela de login → redireciona para `/auth/login`
  - Componente `AuthCallback` em `/auth/callback` → processa retorno
  - Context/store de autenticação atualizado para suportar sessão SSO

---

### 2. Zabbix 7.0 LTS — SAML 2.0

**Provider no Authentik:**

| Campo | Valor |
|-------|-------|
| Tipo | SAML Provider |
| ACS URL | `https://zabbix.ness.com.br/index_sso.php?acs` |
| Issuer / Entity ID | `https://sso.ness.com.br` |
| SP Entity ID | `https://zabbix.ness.com.br` |
| SLO URL | `https://zabbix.ness.com.br/index_sso.php?sls` |
| NameID Format | `emailAddress` |
| Signing | Authentik signs assertions |

**Attribute Mapping:**

| SAML Attribute | Valor |
|----------------|-------|
| `urn:oid:0.9.2342.19200300.100.1.3` | `email` |
| `urn:oid:2.5.4.42` | `first_name` |
| `urn:oid:2.5.4.4` | `last_name` |
| `urn:oid:1.3.6.1.4.1.5923.1.1.1.7` | `groups` |

**Configuração no Zabbix (Administration → Authentication → SAML):**

| Campo Zabbix | Valor |
|--------------|-------|
| Enable SAML | ✅ |
| IdP Entity ID | `https://sso.ness.com.br` |
| SSO Service URL | `https://sso.ness.com.br/application/saml/zabbix/sso/binding/redirect/` |
| SLO Service URL | `https://sso.ness.com.br/application/saml/zabbix/slo/binding/redirect/` |
| Username attribute | `urn:oid:0.9.2342.19200300.100.1.3` |
| SP Entity ID | `https://zabbix.ness.com.br` |
| IdP Certificate | Download do Authentik |
| Enable JIT provisioning | ✅ |
| Group attribute | `urn:oid:1.3.6.1.4.1.5923.1.1.1.7` |

**Mapeamento de grupos SAML → Zabbix User Groups:**

| Grupo SAML | Zabbix User Group | Zabbix Role |
|------------|-------------------|-------------|
| `admin` | `Authentik-Admin` | `Super admin role` |
| `noc` | `Authentik-NOC` | `User role` (read + ack) |
| `soc` | `Authentik-SOC` | `User role` (read-only) |
| `gestao` | `Authentik-Gestao` | `Guest role` (read-only) |

---

### 3. GLPI — OIDC

**Provider no Authentik:**

| Campo | Valor |
|-------|-------|
| Tipo | OAuth2/OIDC Provider |
| Client ID | `glpi-ness` |
| Client Type | Confidential |
| Redirect URI | `https://n-ticket.ness.com.br/front/oidc/callback.php` |
| Scopes | `openid`, `email`, `profile`, `groups` |

**Mudanças no GLPI:**

- Instalar plugin SSO/OIDC compatível (ex: `derricksmith/glpi-singlesignon`)
- Configurar provider no plugin admin:
  - Discovery URL: `https://sso.ness.com.br/application/o/glpi-ness/.well-known/openid-configuration`
  - Client ID: `glpi-ness`
  - Client Secret: (gerado pelo Authentik)
- Mapear claim `groups` → perfis GLPI
- JIT provisioning: criar usuário GLPI no primeiro login OIDC

**Mapeamento de grupos OIDC → Perfis GLPI:**

| Grupo OIDC | Perfil GLPI |
|------------|-------------|
| `admin` | `Super-Admin` |
| `helpdesk` | `Technician` |
| `noc` | `Observer` |
| `soc` | `Observer` |
| `gestao` | `Observer` |
| `usuarios` | `Self-Service` |

---

### 4. n8n — OIDC

**Provider no Authentik:**

| Campo | Valor |
|-------|-------|
| Tipo | OAuth2/OIDC Provider |
| Client ID | `n8n-ness` |
| Client Type | Confidential |
| Redirect URI | `https://n8n.ness.com.br/rest/oauth2-credential/callback` |
| Scopes | `openid`, `email`, `profile` |

**Variáveis de ambiente (docker-compose.yml):**

```yaml
n8n:
  environment:
    - N8N_AUTH_TYPE=oidc
    - N8N_OIDC_CLIENT_ID=n8n-ness
    - N8N_OIDC_CLIENT_SECRET=${NINF_N8N_OIDC_SECRET}
    - N8N_OIDC_ISSUER=https://sso.ness.com.br/application/o/n8n-ness/
    - N8N_OIDC_ALLOWED_GROUPS=admin,noc,soc
```

---

## Mudanças de Infraestrutura

### Docker Compose (`app/docker-compose.yml`)

| Ação | Serviço | Detalhe |
|------|---------|---------|
| **Alterar** | `n8n` | Adicionar variáveis OIDC |
| **Manter** | Demais serviços | Sem mudança |

### Caddyfile

| Ação | Bloco | Detalhe |
|------|-------|---------|
| **Alterar** | `n-ticket.ness.com.br` | Remover `forward_auth` — OIDC nativo substitui |
| **Manter** | `sso.ness.com.br` | Sem mudança |
| **Manter** | `hub.ness.com.br` | Sem mudança |
| **Manter** | `waba.ness.com.br`, `api.ness.com.br` | Sem mudança |

### DNS

| Ação | Registro |
|------|----------|
| ✅ Já existe | `zabbix.ness.com.br` |

### Servidor Zabbix (remoto)

| Ação | Detalhe |
|------|---------|
| ✅ Já existe | DNS, VirtualHost, SSL |
| **Configurar** | SAML no Administration → Authentication |
| **Criar** | User Groups para mapeamento SAML |
| **Upload** | Certificado IdP do Authentik |

---

## Ordem de Execução

| Fase | App | Esforço | O que fazer |
|------|-----|---------|-------------|
| **1** | n8n | Baixo | Adicionar vars OIDC no compose, criar provider/app no Authentik |
| **2** | Zabbix | Médio | Criar provider SAML no Authentik, configurar SAML no Zabbix, criar user groups |
| **3** | GLPI | Médio | Instalar plugin OIDC, criar provider no Authentik, remover forward auth |
| **4** | Hub | Alto | Implementar auth OIDC no FastAPI + React, criar provider no Authentik |

---

## Modelo de Usuários

- **Authentik é a fonte primária**: novos usuários são criados no Authentik
- **Usuários locais existentes**: continuam funcionando, são linkados pelo email no primeiro login SSO
- **JIT Provisioning**: cada app cria o usuário local automaticamente quando ele faz o primeiro login via SSO
- **Grupos**: gerenciados centralmente no Authentik, mapeados para roles locais em cada app

---

## Futuro (fora do escopo atual)

- **Wazuh**: quando implantado, grupo `soc` já estará pronto no Authentik — basta criar o provider
- **MFA**: Authentik suporta TOTP/WebAuthn — pode ser habilitado por grupo (ex: obrigatório para `admin`)
- **Password Policy**: definir políticas de senha centralizadas no Authentik
