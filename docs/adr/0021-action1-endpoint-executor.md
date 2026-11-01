# ADR 0021 — Action1 como executor de endpoint

- Status: aceita por decisão do Ricardo em 30/10/2026; adoção depende da homologação abaixo
- Data: 30/10/2026
- Decisor: Ricardo Esper
- Altera: ADR 0003 (SuperOps como candidato RMM-alvo) e a decisão de 30/10 que mantinha o Atera como executor "por ora" (P5)

## Contexto

O Atera foi avaliado e ficou aquém do necessário. O plano P5 mantinha o Atera como executor de endpoint e deixava o Action1 em espera até uma lacuna concreta. A lacuna apareceu na avaliação.

## Decisão

O **Action1** passa a ser a ferramenta-alvo para execução em endpoint (inventário, atualizações pendentes, implantação controlada). Atera e Datto continuam em operação nos ativos que já atendem, até a migração desses ativos. O ness.OS não vira RMM: ele lê estado e resultado e abre atendimento; a execução de patch fica no Action1, não no Hub.

## Regras que não mudam

- GLPI segue como cadastro mestre; o Action1 não cria cadastro paralelo (ADR 0002).
- Cada tenant/ativo tem provedor explícito; fallback automático entre RMMs é proibido (ADR 0003).
- Nenhuma máquina com dois agentes para a mesma função: a troca é por máquina (instala o novo, remove o antigo), nunca em paralelo.
- "Instalação concluída" e "vulnerabilidade corrigida" são verificações distintas (P5).

## Homologação antes de qualquer integração

Itens 1 e 2 têm teste parcial (seção abaixo); o resto não foi verificado. Fato adicional: que o plano gratuito cobre até 200 endpoints (documentação do fornecedor).

1. API: autenticação, escopo mínimo, leitura de inventário, atualizações pendentes e resultado de execução.
2. Multi-tenant: como separar os clientes (organizações) e se isso cabe no isolamento por tenant do Hub.
3. Licenciamento e custo acima de 200 endpoints, dado que a frota gerenciada hoje é maior.
4. Dados que o agente envia e onde ficam (LGPD, contrato com os clientes).
5. Cobertura de patching de terceiros e o que o Atera fazia que o Action1 não faz.
6. Plano de migração por máquina e inventário dos ativos que ainda dependem de Atera e Datto.

## Teste de leitura da API (01/11)

Só GET, contra um PC do Ricardo (sem dado de cliente). A credencial foi criada com o papel Enterprise Admin, por escolha do Ricardo; a leitura foi disciplina do agente, não do papel. É conta de avaliação: antes de qualquer integração real, apagar e criar outra com papel de leitura. Nunca vai para produção.

- Autenticação OAuth 2.0 (`POST /oauth2/token`, form) funciona na região do Ricardo: `https://app.na-2.action1.com/api/3.0`. Token vale 3600 s.
- `GET /organizations` devolve as organizações da conta (2 na avaliação): confirma o modelo multi-tenant por organização (item 2, parcial: falta provar o isolamento entre organizações).
- `GET /endpoints/managed/{org}` devolve inventário rico (SO, CPU, RAM, disco, MAC, fabricante, série, usuário, `last_seen`, `reboot_required`, `update_status`, `vulnerability_status`, versão do agente). Cobre o item 1 para inventário.
- `GET /updates/{org}` ("missing updates" na especificação) lista, no nível da organização, as atualizações ausentes (nome, fornecedor, KB, reboot). Ainda não testado: quais faltam em cada endpoint e o resultado de execução.
- Fica para depois: licença acima de 200, LGPD/região, cobertura de terceiros vs. Atera, migração (itens 3 a 6).

## Achados da documentação pública (30/10)

Fonte: documentação do fornecedor, sem teste em tenant. Nada abaixo foi exercitado.

- **Multi-tenant (item 2):** várias organizações numa conta, com dados separados entre elas. A cota de licença vale para a **conta inteira**, somando todas as organizações. A cotação é no nível da conta (enterprise).
- **Licença (item 3):** gratuito até 200 endpoints, sem limite de funções e sem suporte do fornecedor. Acima disso, assinatura. Endpoints acima da cota ficam `Inactive`. Avaliação de 15 dias; cotação por formulário ou API. Preço acima de 200 não está na documentação: precisa de cotação.
- **Dados do agente (item 4):** coleta inventário de hardware e software, usuários locais e logons, conexões de rede, logs de eventos do Windows e **chave do BitLocker**. O resultado das consultas fica em cache temporário na nuvem do fornecedor e depois é apagado. Permanecem nomes de máquina, IPs e estatísticas de conexão; logs de diagnóstico ficam 7 dias. Região de dados (América do Norte, Europa etc.) é escolha do cliente e vai para o contrato/LGPD.
- **API (item 1):** existe API REST (licença, uso por organização, cotação), mas a especificação em `app.action1.com/apidocs` é renderizada por script e não foi lida. Autenticação, escopo mínimo e endpoints de inventário e atualizações **seguem sem verificação**.
- **Integrações prontas:** a documentação lista o conector de Jira; o fornecedor anuncia outros (ServiceNow, entre eles), não verificados aqui. Nenhum conector para GLPI foi encontrado; a integração com o Hub seria nossa.

## Consequências

- Nenhuma mudança de código agora. O cliente, o router e o remediador do Atera (`app/backend/app/{integrations,api/routers,remediators}/atera.py`), o painel e o texto de preços continuam como estão até a homologação.
- Integração Action1 só entra depois dos itens 1–3, seguindo o padrão da factory de RMM, com provedor explícito por tenant.
- Remover o Atera do código só depois do inventário dos ativos dependentes e da migração.
- Custo recorrente novo: exige aprovação do Ricardo antes da contratação.
