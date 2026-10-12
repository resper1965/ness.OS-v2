# Authentik — análise, personalização ness. e implementação

Data: 12/10/2026, horário BRT. Responsáveis: Ricardo Esper (aprovação e
custódia), Ismael Araujo (operação), Rogerio Salerno (administrador nominal).
Este documento distingue mudança aplicada de requisito ainda não homologado.

## 1. Resultado e limites

Aplicado à Brand de sso.ness.com.br, UUID
fc7523ea-58a2-4e74-b222-d6c8eb5c5c98:

- branding_title: `ness. | acesso`;
- CSS suportado por Brands: `config/authentik/ness-access.css`;
- título de default-authentication-flow: `Acesse sua conta`;
- logo e favicon existentes preservados; nenhuma edição do core;
- removidos import de fonte externa, gradiente roxo/azul e CSS genérico de
  glassmorphism; superfície escura, BlueDot #00ade8 e controles de 48 px.

Mudança transacional por modelos nativos, precondição nos títulos anteriores,
snapshot protegido antes da escrita. Não modificados providers, certificados,
MFA, usuários, grupos, autorização, cookies, outposts ou callbacks. Não foi
feito upgrade, restart, dump ou restore. Não equivale a aprovação G2.

Teste de navegador real Edge isolado: 1440 e 390 px, título novo, input presente,
sem overflow horizontal, ações sem gradiente, fundo rgb(0,173,232), texto preto,
altura >=48px e reduced-motion sem transição. Teste do título falhou antes e
passou depois. Detector visual retornou zero achados mecânicos. Capturas foram
inspecionadas; sessão humana e interfaces autenticadas não foram homologadas.

O asset raster já instalado foi reutilizado, não redesenhado. A origem da fonte
Montserrat 500 no raster não pode ser certificada pela inspeção: para aceite
integral do logo, obter vetor aprovado com letras brancas/pretas, ponto BlueDot
e fonte incorporada/convertida em curvas. Não usar SVG com import Google Fonts
como substituição automática. Background e favicon não foram reinventados.
Textos nativos parcialmente em inglês permanecem pendência de tradução da
versão, não corrigida por ocultação ou pseudo-elementos CSS.

## 2. Fotografia de configuração atual

Runtime consultado: Authentik2026.5.6, nove aplicações, uma Brand. Inventário de
MFA atual: zero TOTP, zero WebAuthn, zero dispositivos de recuperação estática;
default-authentication-mfa-validation está `not_configured_action=skip`.
Isso permite entrada sem segundo fator para quem não o cadastrou.

| Aplicação | Provider efetivo | Bindings diretas | Limite do aceite |
| --- | --- | ---: | --- |
| hub | OIDC9 | 6 | login nominal, tenant, logout e revogação |
| glpi | proxy12 | 6 | identidade por header + perfil/entidade nativos |
| grafana | OIDC10 | 4 | papel/organização e revogação |
| zabbix | SAML6 | 4 | nominal/MFA, grupo/role e logout |
| zabbix-uat | SAML13 | 1 | isolado, sem coleta; issue51 aberta |
| n8n | proxy5 | 3 | borda não prova autorização nativa |
| nessops | OIDC2 | 0 | verificar controles herdados; fora do aceite |
| n-csirt | OIDC16 | 1 | validar cada origem/callback e tenant |
| wazuh | OIDC11 | 2 | planejado; não promover por existir provider |

Achados atuais, não somente históricos:

1. **P1 MFA administrativo não imposto.** Impor deny global agora bloquearia
   administradores sem dispositivos. Cadastros e recuperação precedem corte.
2. **P1 GLPI: SSO não concede administração.** Authentik autentica e controla
   acesso à aplicação; perfil/entidade GLPI são controles separados. Perfil12
   da identidade API atual só tem Computer READ1; issue74 pede identidade de
   manutenção separada. Não transformar acesso ao SSO em Super-admin GLPI.
3. **P1 nessops sem binding direta.** Não significa automaticamente aberto,
   mas ainda falta demonstração de política efetiva e acesso negado.
4. **P2 drift/legados.** OIDC1 tem três callbacks concatenadas em uma única
   URL strict; OIDC2 usa formato legado e localhost. Hub efetivo é9, com
   callback estrita https://hub.ness.com.br/callback. Não remover1/2 antes de
   apurar referências/consumidores. Cadastro não vinculado não prova inatividade.
5. **P2 GLPI duplicado.** Proxy3 e12 apontam a n-ticket.ness.com.br;12 é ligado
   à aplicação. OIDC8 existe com callback do plugin singlesignon, mas não é o
   provider efetivo. Conferir outpost antes de qualquer exclusão/migração.
6. **P2 SAML legado.** Providers4/6 origem e13/15UAT coexistem;6 e13 efetivos.
   Origem6 assina assertion e response;UAT13 assina assertion, não response.
   Alinhar com exigência do SP, não ativar flags indiscriminadamente.
7. **P2 sessões.** Providers OIDC inspecionados têm access_token1h e refresh30d.
   Isso não é duração de todas as sessões de aplicação; medir revogação real
   antes de alterar prazos. Aprovar política de sessão por risco e cliente.

Provas negativas novas: API pública Authentik core/applications retorna403 sem
sessão mesmo com headers administrativos forjados; GLPI público retorna302
ao sso.ness.com.br com X-Remote-User/Remote-User forjados. Isso cobre requisição
sem sessão, não usuário autenticado atacando outro tenant ou backend direto.

## 3. Ordem executável de implementação global

### A. Controle de mudança e identidade de manutenção

1. Registrar ticket, owner, janela, aplicação afetada e critério de abortar.
2. Exportar somente objetos envolvidos por API/modelo nativo para arquivo
   protegido0600. Segredos fora de Git/chat/email; armazenar no cofre.
3. Usar identidade técnica separada e escopo mínimo. Não ampliar serviço Hub,
   reutilizar token pessoal superadmin ou escrever autenticação por SQL.
4. Confirmar sessão administrativa nominal e break-glass funcional em ambiente
   isolado. Ter operador autorizado disponível antes de endurecer login.
5. Alterar uma aplicação por vez; comparar IDs, bindings, claims e callbacks
   antes/depois. Abort: perda de acesso nominal, cross-tenant ou claim divergente.

### B. MFA dos três administradores — pré-requisito de endurecimento

1. Cada administrador entra com sua própria conta, abre configurações de
   usuário e cadastra TOTP ou WebAuthn pelos fluxos nativos existentes.
2. Gerar códigos de recuperação estática. Ricardo e Ismael formalizam dupla
   custódia fora das VPS; não fotografar QR/seed/códigos para issue ou email.
3. Em sessão nova provar senha+fator, logout, fator incorreto, revogação e
   recuperação. Manter sessão administrativa de contingência durante ensaio.
4. Registrar somente usuário nominal, método, horário e resultado; nunca seed.
5. Criar/usar etapa MFA específica vinculada condicionalmente a platform_admin,
   preservando fluxo de usuários comuns. Não alterar skip de etapa global.
6. Só após os três testes e break-glass PASS exigir fator para esse grupo.
   Testar login do grupo e usuário fora do grupo; reverter binding se houver
   lockout. Não apresentar cadastro de factor como prova de uso obrigatório.

### C. GLPI — resolver o acesso certo antes de trocar protocolo

1. Abrir n-ticket.ness.com.br por sessão nova e verificar provider12/outpost
   efetivos. Preservar forward-auth e rota técnica privada da API.
2. Testar usuário nominal existente: uma identidade no Authentik deve chegar
   ao usuário GLPI esperado. Conferir atributo de matching adotado; não
   conectar contas diferentes só por similaridade de nome ou email não verificado.
3. No GLPI associar perfil à entidade correta, não recursivo salvo contrato.
   Administração técnica nominal é diferente de platform_admin do Hub.
4. Para issue74: usuário API separado de manutenção, Computer READ+CREATE+DELETE13
   na entidade1, sem PURGE/admin. Execução fixa os três hosts e revoga ao término.
5. Provar usuário comum permitido, sem grupo negado, entidade errada negada,
   usuário desativado negado, logout e acesso direto ao backend restrito.
6. Confirmar proxy sobrescreve/limpa headers recebidos externamente. Não liberar
   bypass público de API/Agent; ingestion técnica tem autenticação e TLS próprios.
7. OIDC nativo com provider8 é mudança separada: confirmar plugin/versão/callback
   real, ensaiar em UAT, exportar e só então promover. Não copiar callback do Hub.

### D. Demais aplicações

1. Hub: manter provider9/callback estrita e PKCE S256. Testar viewer/operator/
   NOC/SOC/platform_admin por HTTP e SSE, mesmo tenant e outro tenant; logout
   e revogação devem encerrar sessão e stream. Backend decide papel, não menu.
2. Zabbix: preservar providers6/13 e SPs separados; nominal/MFA/logout e
   break-glass PASS antes de corte. UAT não ativa coleta. Não alterar DNS aqui.
3. Grafana: role/org por grupos mínimos; sem auto-admin por domínio de email.
4. n8n: separar autorização na borda das contas owner/editor/viewer nativas;
   não declarar proxy como SSO nativo nem usar conta compartilhada.
5. nessops: descobrir consumidor de2, avaliar políticas herdadas e dependências
   de1 antes de remover localhost/formatos legados ou adicionar bindings.
6. n-csirt: validar domínios de produção/pages explicitamente autorizados e
   callback de autorização/logout separadas; não generalizar regex para *.com.
7. Wazuh mantém estado planned/unavailable até seu gate próprio.

### E. Limpeza, visual e sustentação

1. Após jornadas aprovadas, inventariar referências de providers/outposts,
   exportar legado, remover uma referência por mudança e provar rollback.
2. Aplicar CSS somente no campo suportado Brands; jamais editar dist/core.
   Revalidar login, senha, fator, recuperação, erro, portal e admin em390/1440px,
   teclado/zoom200%, temas suportados, reduced-motion e upgrade.
3. Revisar tradução dos controles nativos e fonte/logo aprovado em mudança
   visual separada; não prometer recuperação por email antes de SMTP/flow PASS.
4. Revisão trimestral: administradores, contas inativas, dispositivos, tokens,
   certificados, sessões, callbacks, outposts, recuperação e documentação.

## 4. Evidências e rollback desta personalização

Na VPS144.91.115.242, arquivos protegidos:
`/opt/n-infraops/rollback/authentik-global-20261012/before.json` e `applied.json`.
O snapshot inclui apenas Brand/title/CSS/paths e título do fluxo, não credenciais.

Rollback por interface nativa autorizada:

1. Abrir System → Brands → sso.ness.com.br. Confirmar UUID indicado acima e
   comparar estado atual com applied.json; abortar se houver nova mudança humana.
2. Repor branding_title e branding_custom_css de before.json. Não alterar logo,
   favicon, domínio, default, flows ou certificados. Salvar.
3. Abrir Flows → default-authentication-flow e repor flow_title de before.json.
4. Em janela privada conferir título, campos e rota login; não apagar usuários,
   tokens, providers, dispositivos ou sessões de terceiros como parte do rollback.
5. Registrar resultado e manter export para auditoria. CSS é dado versionado;
   fonte da release e runtime precisam coincidir antes de aceite integral.

## 5. Critérios inequívocos de conclusão

- Visual público: PASS restrito à tela inicial desktop/mobile, não todo admin.
- MFA administrativo/recovery/break-glass: PENDENTE.
- SSO nominal, logout, expiração, revogação e acesso negativo por aplicação:
  PENDENTE até matriz com fonte/data/owner/teste resultar PASS.
- Permissões nativas GLPI/identidade de manutenção: PENDENTE issue74.
- Remoção de providers legados: PENDENTE referência e ensaio.
- Logo vetorial/fontes e tradução integral: PENDENTE, sem certificação falsa.

Fontes primárias consultadas: [Brands](https://docs.goauthentik.io/brands/),
[customização](https://docs.goauthentik.io/customize/branding/),
[código oficial](https://github.com/goauthentik/authentik).
Referências main podem superar2026.5.6: campos e comportamento foram conferidos
no runtime antes da escrita. Registros históricos não substituem esta fotografia.

## 6. Dependências e bindings — atualização de 12/10 20:57 BRT

Leitura nova, sem alteração: outpost embutido contém providers3/5/12.
Portanto glpi-sso3 ainda é referenciado junto de glpi-proxy12, embora só12 seja
provider principal da aplicação GLPI. Não excluir3 como se fosse órfão.
Nenhuma das nove aplicações tem backchannel provider configurado nesta amostra.
Isso não exclui consumidor externo de provider aparentemente sem aplicação.

Bindings de grupos observados:

- GLPI: admin/helpdesk/usuarios/noc/soc/gestao; nenhuma policy direta;
- Hub: noc/helpdesk/admin/soc/gestao e uma policy;
- Zabbix: noc/admin/soc/gestao;
- UAT: ness-os-platform-admin;
- n8n: noc/admin/soc; Grafana: noc/admin/soc/gestao; Wazuh: admin/soc;
- nessops: nenhum grupo/policy direto; n-csirt: uma policy, nenhum grupo direto.

Os grupos platform_admin e ness-os-platform-admin têm três membros ativos cada;
interseção dos IDs ativos é três. Logo, nesta amostra a binding UAT legada não
exclui administradores canônicos por divergência de associação. Não trocar
binding nem duplicar grupos para corrigir problema que essa consulta não achou.
Primeira tentativa de consulta usou relação inexistente; corrigida para
interseção em memória dos IDs, exit0, sem exportar identidades ou alterar grupos.

Próximo passo é prova nominal/MFA/logout e análise de sessões/consumidores,
não exclusão de providers ou mais sincronização de grupos. MFA continua
dependência humana de cadastro/recuperação; nenhum fator foi criado pelo agente.
