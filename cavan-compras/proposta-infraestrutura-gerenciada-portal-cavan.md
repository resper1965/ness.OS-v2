# Proposta de Infraestrutura Gerenciada e Segurança

**Proposta:** PPS-01751/2026
**Projeto:** Portal de Aprovação de Compras da CAVAN
**Preparada para:** CAVAN
**Preparada por:** Ness
**Data:** 25 de agosto de 2026
**Validade da proposta:** 15 dias

---

## 1. Resumo executivo

A Ness propõe o fornecimento e a gestão da infraestrutura necessária para hospedar o Portal de Aprovação de Compras da CAVAN, desenvolvido e mantido pela ITNIA e integrado ao ambiente TOTVS Protheus/Fluig.

A solução contempla infraestrutura Linux, publicação segura em HTTPS, banco de dados, endereço IPv4 público dedicado, backup externo, monitoramento, gestão de patches e SecOps por meio do ness.OS. O objetivo é entregar à CAVAN um ambiente controlado, monitorado e recuperável, com responsabilidades claras entre Ness, CAVAN, ITNIA e TOTVS.

A infraestrutura será dedicada à aplicação web e à sua base espelho. O banco de dados não será publicado na internet e o acesso técnico da ITNIA seguirá o princípio do menor privilégio, com identidades nominais, chaves SSH, restrição de origem e trilha de auditoria.

## 2. Escopo da solução

### 2.1 Infraestrutura de produção

- Servidor virtual Linux com 2 vCPU, 8 GB de memória RAM e 100 GB de armazenamento NVMe;
- capacidade de expansão conforme o consumo observado;
- IPv4 público dedicado para entrada e saída;
- publicação do portal em subdomínio da CAVAN;
- HTTPS com certificado TLS válido e renovação automatizada;
- Nginx ou Apache, PHP 8.2 ou superior e MySQL 8.0 ou MariaDB 10.11 ou superior;
- sistema operacional e banco configurados no fuso `America/Sao_Paulo`;
- firewall de infraestrutura e firewall local;
- backup semanal da máquina e backup externo diário do banco de dados;
- retenção de 30 dias para os dumps do banco;
- monitoramento e segurança integrados ao ness.OS.

### 2.2 Monitoramento e operação pelo ness.OS

- Monitoramento contínuo de disponibilidade do servidor, portal e certificado HTTPS;
- acompanhamento de CPU, memória, armazenamento, rede, servidor web, PHP e banco de dados;
- alertas automatizados de indisponibilidade, degradação e esgotamento de recursos;
- acompanhamento da execução dos backups;
- histórico de eventos e visão operacional consolidada;
- relatório mensal de disponibilidade, incidentes, capacidade, patches e postura de segurança.

### 2.3 Patching

- Inventário de versões do sistema operacional e componentes da stack;
- avaliação de atualizações e vulnerabilidades aplicáveis;
- aplicação mensal de patches em janela acordada;
- tratamento prioritário de vulnerabilidades críticas;
- ponto de recuperação e procedimento de rollback antes de alterações relevantes;
- aviso e validação com a ITNIA antes de atualizações major de PHP, MySQL/MariaDB ou sistema operacional.

### 2.4 SecOps

- Coleta e correlação de eventos de segurança;
- monitoramento de autenticações SSH e uso de privilégios administrativos;
- detecção de alterações em arquivos críticos e no diretório da aplicação;
- identificação de persistência, arquivos suspeitos e indicadores de comprometimento;
- acompanhamento de vulnerabilidades e configurações inseguras;
- alertas para criação de usuários, alteração de chaves SSH, mudanças de firewall e falhas repetidas de autenticação;
- integração com Wazuh como fonte canônica de eventos de segurança;
- registro e acompanhamento de incidentes qualificados pelo ness.OS.

## 3. Segurança da arquitetura

A infraestrutura seguirá uma baseline de endurecimento composta pelos seguintes controles:

- Exposição pública restrita às portas necessárias para HTTP/HTTPS;
- redirecionamento de HTTP para HTTPS;
- SSH sem autenticação por senha e sem login remoto direto de `root`;
- acesso administrativo restrito por endereço de origem ou VPN;
- banco de dados ouvindo somente em interface local;
- porta 3306 não publicada externamente;
- contas separadas para administração, aplicação, publicação e backup;
- segredos mantidos fora do código-fonte e dos pacotes de publicação;
- rate limiting e proteção contra tentativas repetidas de autenticação;
- permissões mínimas no sistema de arquivos e no banco de dados;
- logs administrativos e de segurança enviados ao ambiente de monitoramento;
- backup externo criptografado e teste periódico de restauração;
- revisão periódica de usuários, chaves, privilégios e regras de firewall.

O endereço IP autorizado pela TOTVS será utilizado para as chamadas de saída da aplicação. A allowlist de origem será complementada por TLS e credencial própria da integração, evitando que o endereço IP seja tratado como único fator de segurança.

## 4. Acesso da ITNIA

A ITNIA receberá acesso técnico suficiente para publicar e manter a aplicação, sem acesso irrestrito à infraestrutura.

### 4.1 Controles de acesso

- Uma identidade nominal para cada profissional autorizado;
- autenticação exclusivamente por chave SSH individual;
- proibição de contas e chaves compartilhadas;
- acesso SFTP confinado ao diretório da aplicação;
- quando necessário, usuário de deploy com comandos administrativos previamente autorizados;
- acesso liberado somente a partir de origem aprovada ou VPN;
- acesso à produção condicionado a chamado, aprovação e janela de execução;
- validade definida para cada autorização temporária;
- registro de login, uso de `sudo`, alterações e publicações;
- revogação imediata no desligamento ou substituição de profissionais;
- revisão trimestral das contas e chaves autorizadas.

### 4.2 Banco de dados

- Não haverá publicação externa do MySQL/MariaDB;
- o fornecedor utilizará túnel SSH quando o acesso remoto for necessário;
- a credencial será exclusiva e limitada ao schema da aplicação;
- privilégios administrativos globais não serão concedidos;
- credenciais de produção e homologação serão distintas;
- toda credencial será passível de rotação e revogação.

### 4.3 Processo de publicação

1. A ITNIA entrega pacote versionado, instruções de publicação e checksum;
2. a mudança é registrada e a janela é confirmada;
3. a Ness valida o ponto de recuperação;
4. a publicação é realizada com a identidade de deploy;
5. aplicação, banco e integrações são validados;
6. em caso de falha, o pacote anterior é restaurado;
7. resultado, responsável e evidências ficam registrados.

A ITNIA não receberá acesso ao painel da infraestrutura, ao usuário `root`, às configurações globais de firewall, às contas administrativas do banco ou aos componentes internos do ness.OS.

## 5. Backup e recuperação

- Dump diário do banco de dados;
- retenção de 30 dias;
- cópia armazenada fora do servidor de produção;
- criptografia do conteúdo antes do envio;
- backup semanal da máquina virtual;
- teste periódico de restauração;
- retenção do pacote anterior da aplicação para rollback;
- registro das execuções e falhas no ness.OS.

O conteúdo crítico considerado para recuperação inclui o histórico de decisões, os logs de auditoria e as configurações necessárias para reconstrução do serviço. Os PDFs mantidos oficialmente no Fluig e no Protheus serão apenas temporariamente cacheados no portal e submetidos a expurgo.

## 6. Responsabilidades

| Parte | Responsabilidades principais |
|---|---|
| **Ness** | Infraestrutura, Linux, patches, hardening, firewall, certificado, DNS técnico, backup, restauração, monitoramento, SecOps, gestão de acessos e disponibilidade operacional. |
| **ITNIA** | Aplicação web, esquema da base espelho, pacotes de publicação, correções, compatibilidade da aplicação, integrações e suporte durante projeto e garantia. |
| **TOTVS** | Disponibilidade do Protheus/Fluig, publicação do REST do AppServer, liberações de origem, configurações internas e jobs na T-Cloud. |
| **CAVAN** | Gestão dos usuários aprovadores, dados de negócio, aprovações, domínio corporativo e solicitações formais à TOTVS. |

## 7. Atendimento

- Monitoramento e alertas automatizados: contínuos;
- operação e atuação humana: horário comercial, em dias úteis;
- janela de patching: mensal, previamente acordada;
- vulnerabilidades críticas: avaliação prioritária e tratamento conforme risco e impacto;
- mudanças de versão major: somente após validação de compatibilidade e autorização;
- atendimento humano fora do horário comercial: não incluído nesta proposta, podendo ser contratado separadamente.

## 8. Investimento

### Opção A — Produção gerenciada

| Item | Investimento |
|---|---:|
| Infraestrutura de produção, IPv4 dedicado, firewall, backup e certificado | R$ 110,00/mês |
| ness.OS Managed Server: monitoramento, patching e SecOps | R$ 490,00/mês |
| **Total mensal** | **R$ 600,00** |
| Implantação, hardening e onboarding | **R$ 1.200,00**, pagamento único |

### Opção B — Produção e homologação gerenciadas — recomendada

| Item | Investimento |
|---|---:|
| Produção completa e gerenciada | R$ 600,00/mês |
| Infraestrutura e gestão reduzida de homologação | R$ 310,00/mês |
| Reserva operacional e armazenamento adicional | R$ 15,00/mês |
| **Total mensal** | **R$ 925,00** |
| Implantação, hardening e onboarding dos dois ambientes | **R$ 1.800,00**, pagamento único |

A Opção B é recomendada porque permite validar pacotes, dependências e atualizações antes da publicação em produção, reduzindo o risco operacional e oferecendo à ITNIA um ambiente próprio para homologação.

## 9. Itens incluídos na implantação

- Provisionamento e configuração do sistema operacional;
- configuração do servidor web, PHP e banco de dados;
- hardening inicial;
- configuração de firewall e acesso remoto;
- criação das identidades administrativas e de fornecedor;
- instalação e integração dos agentes de monitoramento e SecOps;
- configuração do backup externo;
- baseline inicial de vulnerabilidades;
- configuração de dashboards e alertas;
- teste de backup e restauração;
- documentação do ambiente e do processo de acesso/publicação.

## 10. Premissas e exclusões

### Premissas

- A CAVAN disponibilizará o subdomínio e realizará as solicitações contratuais junto à TOTVS;
- a TOTVS publicará o REST do AppServer e liberará o IPv4 informado;
- a ITNIA fornecerá aplicação, documentação técnica, requisitos definitivos e pacotes compatíveis;
- a aplicação utilizará HTTPS e autenticação de serviço nas integrações;
- documentos oficiais permanecerão no Fluig e no Protheus, conforme informado pela ITNIA.

### Não incluído

- Desenvolvimento, correção ou sustentação funcional da aplicação;
- licenças ou serviços da TOTVS;
- suporte funcional aos aprovadores;
- operação humana 24x7;
- WAF comercial, proteção anti-DDoS dedicada ou CDN comercial;
- teste de invasão;
- resposta forense extensa ou recuperação decorrente de falha no código da aplicação;
- migração de dados não prevista;
- alterações de escopo ou capacidade solicitadas após o dimensionamento inicial.

Serviços adicionais poderão ser objeto de orçamento específico.

## 11. Condições comerciais

- **Pagamento:** mensalidade cobrada por boleto bancário ou Pix, com vencimento no dia 10 do mês subsequente ao da prestação. A implantação será faturada integralmente no aceite da proposta;
- **Vigência:** contrato com prazo mínimo de 12 meses, renovado automaticamente por períodos iguais e sucessivos, salvo manifestação por escrito de qualquer das partes com antecedência mínima de 90 dias do término do período vigente;
- **Reajuste:** os valores serão reajustados anualmente, a cada 12 meses contados da data de início da prestação, pela variação acumulada do IPCA/IBGE do período. Na ausência ou extinção do IPCA, será adotado o índice que legalmente o substituir;
- **Início:** condicionado ao aceite formal desta proposta, à disponibilização dos dados técnicos e à confirmação das responsabilidades de cada parte;
- **Validade:** esta proposta é válida por 15 dias a partir da data de emissão. Após esse prazo, os valores e condições poderão ser revisados.

## 12. Próximos passos

1. Aprovação da opção comercial;
2. confirmação dos responsáveis técnicos da CAVAN, Ness e ITNIA;
3. validação formal do IPv4 público dedicado para liberação na TOTVS;
4. definição do subdomínio e da janela inicial;
5. recebimento das chaves públicas dos profissionais autorizados da ITNIA;
6. provisionamento, hardening e integração ao ness.OS;
7. homologação técnica, teste de restauração e aceite para entrada em produção.

---

## Aceite

**Opção selecionada:** ( ) Opção A — Produção  ( ) Opção B — Produção e homologação

**CAVAN**

Nome: __________________________________________
Cargo: __________________________________________
Data: ____/____/________
Assinatura: _____________________________________

**Ness**

Nome: Daniel Ajzen
Cargo: Comercial
Data: 26/08/2026
E-mail: dajzen@ness.com.br
Assinatura: _____________________________________

---

Esta proposta descreve o escopo técnico e comercial inicial e não substitui o contrato definitivo, o acordo de nível de serviço ou o instrumento de tratamento de dados aplicável.
