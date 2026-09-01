# Auditoria das integrações Authentik

> Data da inspeção: 20/08/2026
> Método: inspeção somente leitura das duas VPS, configuração em execução, banco Zabbix e código local
> Escopo: Authentik, Hub, GLPI, n8n e Zabbix
> Regra: configuração existente não equivale a SSO homologado

## Resumo

| Componente | Estado | Evidência observada | Bloqueio principal |
|---|---|---|---|
| Authentik | parcial | server e worker `2026.5.6` saudáveis; aplicações e providers existem; outpost embutido ativo | sem teste de MFA, restore, revogação e acesso break-glass; nenhum evento de autenticação nas 24 horas inspecionadas |
| Hub | parcial | callback alinhada em `/callback`; grants `authorization_code` e `refresh_token` habilitados; autorização sintética chega ao fluxo de autenticação sem erro OAuth | login humano completo, validação de `state`, PKCE, sessão segura, claims, logout e revogação ainda não homologados |
| GLPI | parcial | domínio redireciona ao Authentik; proxy encaminha usuário remoto; plugin `singlesignon` habilitado | fluxo após login não homologado, providers proxy duplicados e endpoint de depuração expõe variáveis de servidor a usuários autenticados |
| n8n | parcial | domínio redireciona ao Authentik por `forward_auth` | proxy protege a borda, mas não comprova sessão/identidade nativa no n8n nem logout/revogação ponta a ponta |
| Zabbix | parcial | SAML e JIT habilitados; endpoint SSO redireciona corretamente ao Authentik | mapeamento de usuário/grupo, logout, revogação e testes negativos ainda não validados; há provider SAML legado não vinculado |

Nenhuma integração deve ser promovida para `homologada` antes da execução completa da matriz de testes deste documento.

## 1. Authentik

### Estado observado

- Contêineres `ninf-authentik-server` e `ninf-authentik-worker` estavam saudáveis.
- Existem aplicações para Hub, GLPI, n8n, Zabbix e também cadastros futuros/fora do escopo atual.
- O outpost embutido contém os providers proxy de n8n e dois providers relacionados ao GLPI.
- Não foram observados eventos de autenticação nas 24 horas anteriores à inspeção. Isso não prova falha, mas impede usar logs recentes como evidência de funcionamento.

### Regularização necessária

1. Fazer backup antes de alterar providers, applications, flows ou outposts.
2. Identificar e remover somente após teste os providers legados/duplicados.
3. Definir grupos e bindings por aplicação, com negação por padrão.
4. Exigir MFA para administradores e testar recuperação de segundo fator.
5. Criar conta break-glass local, guardada fora do fluxo cotidiano e testada trimestralmente.
6. Definir duração de sessão, revogação, logout e desativação de usuário.
7. Ativar retenção e alerta dos eventos de autenticação sem registrar segredos.

## 2. Hub n.infraops

### Estado observado

- O backend em execução possui OIDC habilitado e aponta para o issuer/JWKS do Hub no Authentik.
- O client ID do backend coincide com o client ID fixado no frontend.
- O frontend solicita retorno em `https://hub.ness.com.br/callback`.
- Em 20/08/2026, o provider `hub-oidc` foi corrigido para permitir estritamente `https://hub.ness.com.br/callback`.
- Os grants `authorization_code` e `refresh_token` foram definidos explicitamente. Antes da correção, a lista vazia era rejeitada pela versão Authentik 2026.5.6.
- Após as duas correções, uma autorização sintética com a URI do frontend passou a redirecionar para `/if/flow/default-authentication-flow/`, sem erro OAuth.
- Em 20/08/2026, o frontend passou a gerar `state` com 256 bits via Web Crypto, armazená-lo em `sessionStorage`, removê-lo no primeiro uso e rejeitar callback ausente ou divergente.
- O JWT local é persistido em `localStorage`, incompatível com o requisito de segurança definido para PWA em BYOD.
- Login local por e-mail/senha permanece disponível em paralelo ao SSO.

### Classificação

`parcial`: o início do fluxo OIDC está funcional, mas o login humano completo e os controles de sessão ainda não foram homologados.

### Regularização necessária

1. Adicionar PKCE ao fluxo de autorização e à troca de código no BFF.
2. Migrar a sessão para cookie `HttpOnly`, `Secure` e `SameSite` apropriado ou arquitetura BFF equivalente; não manter token em `localStorage`.
3. Restringir o login local exclusivamente a break-glass e criar contas nominais pelo IdP.
4. Testar JIT, claims, prioridade de grupos, tenant, usuário desativado, logout e revogação.

## 3. GLPI

### Estado observado

- GLPI `11.0.8` está em execução.
- O domínio público redireciona para o Authentik por `forward_auth`.
- Caddy envia `X-Remote-User` e `Remote-User` ao GLPI.
- O plugin `singlesignon` `2.0.3` está habilitado.
- Existem dois providers proxy relacionados ao mesmo domínio GLPI; apenas um está vinculado à aplicação atual, mas ambos permanecem no outpost.
- O artefato `/sso_debug.php` observado na inspeção inicial não está mais presente após a recriação controlada do contêiner GLPI; a validação interna retorna HTTP 404. Os arquivos `ajax/debug.php` e `ajax/switchdebug.php` encontrados são componentes nativos do GLPI e não foram alterados.
- O `forward_auth` cobre o domínio inteiro. A rota usada pelo GLPI Agent pode, portanto, ser interceptada pelo login interativo e precisa de desenho explícito de autenticação e restrição.

### Classificação

`parcial`: a borda chega ao Authentik e há plugin de confiança em cabeçalho, mas o login pós-callback, criação/vínculo do usuário, logout e revogação não foram comprovados.

### Regularização necessária

1. Fazer backup de banco, documentos, configuração e plugins.
2. Definir um único provider e remover o legado apenas depois do teste.
3. Manter teste de regressão garantindo que `sso_debug.php` e outros arquivos temporários não reapareçam em novos deploys.
4. Validar spoofing de cabeçalho: os cabeçalhos de identidade devem ser removidos da requisição externa e definidos somente pelo proxy confiável.
5. Separar a ingestão do GLPI Agent do login humano: rota, credencial/token, TLS, rate limit e allowlist quando praticável.
6. Testar entidade, perfil, grupo, logout, usuário desativado e acesso direto ao backend sem Caddy.

A separação por endpoint/subdomínio técnico foi aprovada. O desenho exato será definido antes de publicar a coleta.

## 4. n8n

### Estado observado

- O domínio público redireciona ao Authentik pelo outpost embutido.
- Não foram observadas variáveis OIDC/SAML ou de gestão de usuário no contêiner n8n.
- O Caddy aplica `forward_auth`, mas não encaminha uma identidade para provisionamento/autorização nativa do n8n.

### Classificação

`parcial`: existe controle de acesso na borda, não SSO nativo comprovado. Após autenticar no Authentik, o operador ainda pode encontrar uma segunda sessão/login ou uma conta n8n compartilhada.

### Regularização necessária

1. Decidir entre SSO nativo suportado pela edição/licença adotada ou proxy de acesso com contas n8n nominais separadas.
2. Proibir conta compartilhada para edição administrativa.
3. Testar login, logout, revogação, usuário desativado e tentativa de acesso direto ao contêiner.
4. Mapear papéis de owner/editor/viewer e limitar a edição de credenciais/workflows.

## 5. Zabbix

### Estado observado

- A autenticação interna continua como padrão; SAML está habilitado como alternativa.
- JIT SAML está habilitado.
- Entity ID, SSO e SLO apontam ao provider Zabbix no Authentik.
- Mensagens e assertions são assinadas; requests/logout não estão configurados para assinatura.
- O endpoint `index_sso.php` retorna redirect válido ao Authentik.
- Existe um provider SAML legado além do provider atualmente vinculado à aplicação.
- O diretório de usuários SAML não possui nome descritivo.

### Classificação

`parcial`: o início do protocolo funciona, mas autenticação completa, mapeamento, JIT, logout e revogação não foram demonstrados.

### Regularização necessária

1. Nomear e documentar o diretório SAML.
2. Conferir certificados, validade, rotação e requisitos de assinatura/criptografia.
3. Mapear grupos Authentik para grupos/roles Zabbix com menor privilégio.
4. Testar usuário novo, existente, sem grupo, desativado, logout e indisponibilidade do IdP.
5. Preservar e testar uma conta local Super Admin exclusivamente break-glass.
6. Remover o provider legado somente após comprovar que não é referenciado.

## 6. Matriz mínima de homologação

Executar para cada solução com um usuário de teste comum, um administrador, um usuário sem grupo e um usuário desativado.

| Teste | Hub | GLPI | n8n | Zabbix |
|---|---:|---:|---:|---:|
| login iniciado pela aplicação | pendente | pendente | pendente | pendente |
| login iniciado pelo portal Authentik | pendente | pendente | pendente | pendente |
| grupo/role correto | pendente | pendente | pendente | pendente |
| tenant/entidade correto | pendente | pendente | N/A a confirmar | N/A |
| usuário sem grupo negado | pendente | pendente | pendente | pendente |
| usuário desativado perde acesso | pendente | pendente | pendente | pendente |
| logout encerra aplicação e IdP | pendente | pendente | pendente | pendente |
| sessão expira no prazo definido | pendente | pendente | pendente | pendente |
| acesso direto ao backend é negado | pendente | pendente | pendente | N/A |
| break-glass funciona sem IdP | pendente | pendente | pendente | pendente |
| trilha de auditoria identifica usuário | pendente | pendente | pendente | pendente |

## 7. Ordem de correção

1. Backup de Authentik e das aplicações dependentes.
2. Remoção controlada do endpoint de diagnóstico do GLPI e bloqueio de acesso direto aos backends.
3. Implementação de PKCE e sessão segura no Hub; callback, grants e validação de `state` já regularizados.
4. Homologação Zabbix, preservando break-glass.
5. Separação segura da rota de inventário do GLPI Agent e homologação do login humano.
6. Definição do modelo de identidade do n8n conforme licença.
7. MFA, revogação, testes negativos e limpeza de providers legados.
8. Teste final completo, evidências e mudança de estado para `homologado`.

## 8. Dependência para concluir a homologação

Foi aprovada a criação de quatro identidades descartáveis de teste: usuário padrão, administrador limitado, usuário sem grupo e usuário a ser desativado. Os testes serão feitos em janela agendada; não devem usar contas pessoais nem senhas compartilhadas.

## 9. Revalidação somente leitura — 22/08/2026

O núcleo Authentik `2026.5.6` permaneceu saudável, com server e worker ativos. A configuração existente não equivale, porém, a homologação das aplicações:

| Aplicação | Evidência observada | Estado |
|---|---|---|
| Hub | aplicação/provider OIDC presentes; domínio HTTP 200 | parcial; falta login nominal ponta a ponta e sessão segura |
| ness.OS legado | provider separado com callbacks conflitantes e grants excessivos; sobrepõe o desenho do Hub | `NO-GO`; reconciliar a identidade canônica antes de uso |
| GLPI | aplicação ligada ao proxy atual; domínio redireciona ao outpost | parcial; há providers concorrentes/legados e o pós-callback não foi homologado |
| n8n | domínio redireciona ao outpost | parcial; proteção de borda, sem identidade nativa comprovada |
| Zabbix | provider SAML ligado; endpoint SSO inicia o protocolo | parcial; JIT, grupos, logout e revogação pendentes |
| Grafana | aplicação/provider registrados | `NO-GO`; DNS público não resolve |
| Wazuh | aplicação/provider registrados | `NO-GO`; DNS público não resolve |

Nenhuma das sete aplicações dependentes está `GO`: Hub, GLPI, n8n e Zabbix estão parciais; ness.OS legado, Wazuh e Grafana estão `NO-GO`.

O grupo global `platform_admin` ainda não existe. Ricardo Esper está no grupo cotidiano `admin`; Ismael Araujo e Rogério Salerno estão em `noc`, `gestao` e `usuarios`. Nenhum dos três possui TOTP, WebAuthn ou código de recuperação confirmado. Os grupos existentes `authentik Admins` e `zabbix-admins` têm semântica de superusuário e não devem ser reutilizados ou renomeados para o papel global da plataforma. Portanto a restrição global aprovada ainda está apenas no código/política, não na identidade efetiva.

Próxima sequência controlada:

1. criar `platform_admin` como grupo comum (`is_superuser=false`) pela API suportada do Authentik, sem SQL, e associar exclusivamente Ricardo, Ismael e Rogério;
2. exigir e comprovar MFA individual antes de liberar gestão da plataforma;
3. homologar Hub, GLPI, Zabbix e n8n com usuário comum, administrador limitado, sem grupo e desativado;
4. resolver DNS e somente então homologar Grafana e Wazuh;
5. reconciliar Hub versus o registro legado ness.OS, escolher um único provider GLPI e um único provider SAML Zabbix, corrigir hosts internos/SLO e remover legados apenas após export, teste negativo e rollback comprovado.

As mutações acima não foram executadas nesta auditoria. A API oficial usa autenticação Bearer; qualquer automação deverá obter o token de Psono/SOPS, operar com menor privilégio, iniciar em dry-run e nunca registrar o valor.

## 10. Diagnóstico de acesso GLPI — 24/08/2026

- `n-ticket.ness.com.br` resolve para a VPS AIOps e responde em HTTPS;
- o acesso público retorna ao fluxo de autenticação do Authentik e o formulário identifica corretamente a aplicação GLPI;
- DNS, TLS, núcleo do Authentik e início do fluxo não são o bloqueio observado;
- produção ainda protege o GLPI com `forward_auth`, enquanto o desenho aprovado prevê OIDC nativo e remoção posterior desse proxy;
- em 24/08/2026, Ricardo Esper confirmou login bem-sucedido no GLPI como `AKADMIN`; isso recupera a administração, mas não homologa acesso nominal, perfis, logout ou revogação;
- o diagnóstico técnico na VPS ainda depende de restaurar o acesso SSH nominal; a chave nominal AIOps disponível anteriormente não está utilizável no workspace atual.

Sequência de recuperação sem contornar o SSO:

1. restaurar o acesso SSH nominal `ness_admin` à VPS AIOps, mantendo `root` remoto bloqueado;
2. exportar Authentik, Caddy, banco/configuração e plugins do GLPI antes de qualquer mutação;
3. conferir se Ricardo Esper está ativo no Authentik e autorizado na aplicação/provider GLPI, sem usar conta compartilhada;
4. validar o callback do proxy e o vínculo do usuário pelo e-mail; corrigir apenas o ponto comprovadamente divergente;
5. criar e testar uma conta GLPI local `break-glass`, restrita por rede e guardada no cofre;
6. homologar login, perfil, entidade, logout, revogação e acesso negado;
7. em mudança separada, migrar do `forward_auth` para OIDC nativo, preservando rollback até a homologação completa.
