# Cavan — Google Workspace SecOps (preparação)

## Decisão de arquitetura

- A Cavan será integrada como **um único tenant Google Workspace**, abrangendo
  Matriz e unidades fabris.
- Domínio principal confirmado: `cavan.com.br`. A resolução pública de MX em
  2026-08-26 aponta para a infraestrutura Google, coerente com o uso informado
  de Google Workspace.
- O ness.OS exibirá saúde geral consolidada e acompanhamento por serviços.
  Unidade organizacional, localidade e serviço de origem serão atributos de
  contexto do evento, nunca tenants distintos.
- Wazuh continua sendo a camada de correlação/SIEM. Ele não recebe o Google
  Workspace diretamente; o conector Workspace normaliza as auditorias e as
  entrega ao pipeline SecOps.
- GAM7 será usado para inventário e leitura de postura. O conector será usado
  para coleta contínua de auditorias. Nenhuma dessas frentes terá capacidade
  de alteração no tenant.
- A operação da leitura é responsabilidade da **ness.**. Ismael Araújo é o
  responsável técnico provisório até a entrada em operação; o responsável
  definitivo será designado no go-live.

## Fontes de dados iniciais

1. Admin SDK Reports API: `login`, `admin`, `token`, `drive` e os demais
   serviços que estiverem habilitados na edição contratada.
2. Alert Center API: alertas de segurança e administração disponíveis no
   tenant. **Fica fora do piloto inicial:** a API oferece o escopo
   `apps.alerts`, que permite leitura e escrita. Só será incluída após uma
   aprovação explícita de exceção de privilégio.
3. Inventário GAM7: domínios, unidades organizacionais, grupos, privilégios,
   aplicações OAuth e configurações relevantes, com relatório versionado.

## Segurança mínima obrigatória

- Projeto Google Cloud exclusivo por cliente e conta de serviço exclusiva:
  `ness-os-cavan-workspace-reader`.
- Delegação em todo o domínio apenas com escopos de leitura aprovados. O
  escopo inicial e único é `admin.reports.audit.readonly`; qualquer escopo
  adicional deve ser justificado e aprovado antes de ser incluído.
- Impersonação de uma conta administrativa delegada, não da conta pessoal de
  um operador.
- Chave de conta de serviço guardada somente no cofre de segredos do host de
  integração, com permissão `0600`; nunca no repositório, ticket, painel ou
  log.
- Saída do conector via JSON estruturado, sem conteúdo de e-mail, arquivos de
  Drive ou tokens OAuth. Apenas metadados de auditoria necessários à triagem.

## Entregas antes da ativação

- [x] Arquitetura e escopo funcional definidos.
- [ ] **Gate de autoridade:** identificar e validar o Super Admin responsável
      do tenant `cavan.com.br` para aprovar a delegação. A conta de serviço,
      credencial e operação ficam sob custódia da ness.; sem essa autorização,
      não há delegação de domínio nem coleta.
- [ ] Criar projeto Google Cloud e conta de serviço do tenant Cavan.
- [ ] Habilitar Reports API.
- [ ] Avaliar separadamente o Alert Center API. Seu escopo disponível é de
      leitura e escrita, portanto não integra o piloto read-only.
- [ ] Aprovar delegação de domínio com os escopos mínimos.
- [ ] Executar GAM7 em modo inventário e revisar o relatório inicial.
- [ ] Publicar o conector somente leitura no AIOps/Wazuh e validar eventos
      sintéticos, sem automação corretiva.
- [ ] Criar painéis: saúde do Workspace, identidade, administração, OAuth e
      colaboração/Drive; disponibilizar ao cliente somente após homologação.

## Critério de aceite

- Eventos de login, administração e autorizações OAuth chegam normalizados ao
  SecOps e preservam `tenant=cavan`.
- Eventos possuem correlação por serviço; unidade só aparece quando o dado de
  origem existir.
- Não há credencial ou conteúdo sensível no repositório nem nos dashboards.
- Ações corretivas permanecem desligadas; incidentes seguem o fluxo AIOps e
  ITSM aprovado.
