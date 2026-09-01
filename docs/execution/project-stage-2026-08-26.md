# ness.OS — estágio do projeto (2026-08-26)

## Concluído hoje

- O backup noturno da origem Zabbix de 26/08 concluiu com sucesso: conjunto
  `COMPLETED`, `SHA256SUMS` validado e 5,4 GiB. A cópia externa criptografada
  criou o snapshot `6177525c`; `restic check` não encontrou erros.
- Zabbix UAT publicado por Cloudflare em TLS Full (strict), com origem
  restringida e servidor de coleta ainda mascarado.
- SAML do Authentik homologado de ponta a ponta para o Zabbix UAT, sem JIT e
  com contingência local preservada.
- Certificado do IdP instalado, estado anterior do diretório SAML copiado em
  backup local restrito e parâmetros efetivos documentados.

## Pronto para a próxima onda

- Homologar acesso de plataforma com os demais administradores autorizados.
- Definir grupos e papéis de operação antes de habilitar JIT/SCIM.
- Revisar e reduzir os Super Admins herdados da cópia restaurada para o modelo
  de administração de plataforma aprovado, sem revogação em massa.
- Concluída a redução dos Super Admins herdados no Zabbix UAT, a retirada de
  `akadmin` do grupo SSO de plataforma e a normalização do identificador do
  Ricardo para a conta canônica `resper`. A conta duplicada foi desativada,
  sem exclusão, para preservação de auditoria e rollback.
- Executar o polimento do Zabbix (nomes, owners, localização, mapas,
  templates e redução de ruído) antes da primeira onda de coleta.
- Após a estabilização funcional, aplicar a identidade visual ness. ao
  frontend Zabbix: marca, paleta, tipografia e textos de contexto. A alteração
  deve ser versionada, reversível e validada a cada atualização do Zabbix;
  não é pré-requisito para ativar a coleta.
- Após estabilizar a identidade e os acessos, executar a frente de UX/UI do
  Authentik com branding ness.: telas de login, recuperação de senha, MFA,
  mensagens de erro, biblioteca de aplicações, contraste/acessibilidade e
  jornada mobile. A customização deve preservar os fluxos de segurança,
  evitar segredos em telas e ser homologada antes de substituir o tema padrão.
- Diagnóstico de polimento do Zabbix UAT concluído: 611 hosts cadastrados,
  249 habilitados, 240 grupos, 254 hosts sem tags e somente um mapa. O plano
  é executar saneamento e piloto de até 25 hosts antes de qualquer coleta.
- Piloto de polimento iniciado e etiquetado: Cavan–Matriz, produção, 14 hosts
  e owner Ricardo Esper. A conectividade em balanceamento e as duas visões de
  mapa (infraestrutura e serviços) foram definidas; coleta e notificações
  continuam desativadas.
- Cavan definido como tenant-referência end-to-end do ness.OS: além de
  monitoramento, será a primeira implementação integrada de ITSM, SecOps,
  portal executivo, inventário e runbooks, com segregação reutilizável.
- Criados os mapas UAT de infraestrutura e serviços da Cavan–Matriz, ambos
  com 14 elementos e 13 relações; a visão de serviços será a base do portal
  executivo do cliente quando o acesso for formalmente liberado.
- Definida a frente Google Workspace da Cavan: um único tenant corporativo,
  abrangendo Matriz e unidades fabris. A saúde será consolidada no nível do
  cliente e apresentada por serviços; cada unidade será apenas contexto do
  evento quando a informação estiver disponível.
- Arquitetura aprovada para descoberta: GAM7 para inventário/postura e um
  conector versionado de auditoria do Google Workspace para Reports API,
  encaminhando eventos normalizados ao Wazuh/AIOps. Alert Center foi separado
  por exigir escopo com escrita. A coleta só será ativada após a delegação
  administrativa de leitura mínima e a aprovação do escopo.
- Base do backend ness.OS validada localmente: suíte atual com 57 testes
  aprovados em 2026-08-26, sem dependência de credenciais externas.
- Portal ness.OS confirmado ativo em `https://hub.ness.com.br`; a referência
  antiga `infraops.ness.com.br` não possui DNS e foi removida da configuração
  de exemplo e do default do backend.
- Corrigido o cache do PWA do Hub: a versão anterior servia o HTML em
  cache-first, podendo referenciar bundles Vite já substituídos e exibir tela
  branca. A versão `ninf-v2` usa rede-primeiro para navegação, mantém somente
  fallback offline e foi publicada com validação HTTP 200.
- Corrigido também o erro de execução `token is not defined` na área
  autenticada do Hub. O token de Web Push passou a ser derivado do cabeçalho
  de sessão existente; o bundle novo foi publicado e validado por HTTP 200.
- Hub padronizado para a assinatura única `ness.`: Montserrat 500 em caixa
  baixa, ponto `#00ADE8`, sem repetir a marca nos títulos de módulos ou telas.
  Os módulos são apresentados como Visão geral, InfraOps e SecOps.
- Transparência de dados aplicada ao Hub: o catálogo GLPI permanece marcado
  como não publicado; a base SecOps está explicitamente identificada como
  referência estática, sem alegar atualização ou aplicabilidade em tempo real.
- A visão geral do Hub foi refeita como centro de operação: pulso por fonte,
  leituras com proveniência, pendências e ausência deliberada de score até a
  homologação das entradas. O bundle foi publicado e respondendo HTTP 200.
- A área operacional da visão geral passou a ocupar toda a largura disponível,
  com a leitura principal ancorada à esquerda e maior peso visual para o
  pulso das fontes. Publicação validada em `https://hub.ness.com.br` com
  frontend saudável e resposta HTTP 200 em 2026-08-27.
- A composição foi adensada para telas largas: o fluxo operacional agora
  recebe a maior parte da largura, enquanto a integridade da visão funciona
  como apoio contextual. A tela preserva o comportamento responsivo e não
  introduz indicadores sintéticos.
- Sequência de implantação rebaseada em
  `docs/execution/ness-os-rebaseline-2026-08-26.md`: Zabbix recuperável,
  piloto Cavan, GLPI/portal, AIOps e então SecOps/escala.
- GLPI está acessível e possui entidades, categorias, template, conhecimento e
  SLAs; ainda não possui projetos ou tarefas. A integração suportada por API
  permanece bloqueada até a criação de credenciais mínimas de aplicação e de
  serviço, sem uso de escrita direta no banco.
- Verificação em 27/08: API, frontend, PostgreSQL, Redis e workers do AIOps
  estão saudáveis, mas o token configurado para leitura do Zabbix retorna
  `Not authorized`. Assim, a plataforma está disponível, porém a ingestão
  Zabbix → AIOps não está operacional. Atera, Datto e GLPI
  também ainda não têm credenciais de ingestão configuradas.
- Decisão de escopo: RocketCyber foi removido do AIOps (configuração, rotas,
  KPIs e conector). O SecOps será alimentado por Wazuh e pelas fontes futuras
  aprovadas; não há substituição implícita nem dados RocketCyber em uso.

## Proteções preservadas

- `zabbix-server`: inativo e mascarado.
- JIT, SCIM, ações e notificações: não habilitados por esta etapa.
- Conta break-glass e provedor SAML temporário: mantidos somente para rollback
  até a aprovação explícita de revogação.
