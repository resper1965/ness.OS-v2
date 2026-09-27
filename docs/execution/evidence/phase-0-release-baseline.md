# Evidência do baseline de release da Fase 0

Baseline inicial coletado em 2026-09-25. Inventário Contabo, evidência AIOps e
manifesto local foram atualizados em 2026-09-27 (America/Sao_Paulo). A comparação
produção/código/imagens ainda usa fatos coletados em 25/09 às 17:49 BRT; hashes
e digests remotos seguem sem atualização.

## Escopo de produção

- Hub/AIOps: `144.91.115.242` (`aiops`).
- Zabbix canônico: `144.91.72.202` (`infra-zabbix`).
- VPS `169.58.234.9` (`nes-os-zabbix-pr-01`): infraestrutura do projeto, mas
  registrada no plano de migração como destino de UAT/cutover pendente; não é a
  origem canônica usada para a recuperação nesta fase.
- `169.58.178.187` (`npentest`): excluída do escopo deste projeto.

## Manifesto local

O gerador determinístico e seus nove testes estão no
repositório. Para atualizar o snapshot após a consolidação da árvore, execute:

```bash
python3 infra/scripts/ness-release-manifest.py --output release-manifest.json
python3 -m pytest infra/tests/test-ness-release-manifest.py -q
```

O manifesto local-only foi gerado em 27/09 para o commit limpo `ec76784` e está
em [`phase-0-local-release-manifest-2026-09-27.json`](phase-0-local-release-manifest-2026-09-27.json).
Seus 9 testes passaram. Marca `release_ready=false`: 8 de 19 imagens locais não
possuem digest.

A comparação produção/local em `phase-0-production-manifest.json` continua
baseada no snapshot do commit `3c8bb4d` e nos fatos de produção coletados em
25/09 às 17:49 BRT: 8 de 19 imagens sem digest, 43 divergências de arquivo e 47
arquivos sem hash remoto. Esse snapshot não prova o estado remoto atual.

## Observações em produção

- A VPS AIOps executa API, frontend e workers com imagens locais (`app-api`,
  `app-frontend` e `app-worker-*`); os IDs de imagem observados não são digests de
  release publicados. O Compose em produção foi identificado em
  `/opt/n-infraops/app/docker-compose.yml`.
- O código Python montado do host para o Hub teve hashes coletados para 75
  arquivos. 41 divergem do workspace local. A comparação também encontrou
  divergências no Compose do Hub e no Caddy do Psono. O manifesto atual compara
  126 arquivos montados/instalados aos 79 hashes remotos conhecidos e registra
  43 divergências e 47 caminhos ainda sem hash de produção. Fontes incorporadas
  às imagens são representadas pelo commit e pelos digests da release, não como
  arquivos remotos independentes.
- Classificação dos mesmos 75 arquivos comparando produção, workspace e Git
  HEAD: 14 coincidem nos três; 15 têm alterações locais não commitadas que já
  coincidem com produção; 5 arquivos locais ainda não rastreados também
  coincidem com produção; 33 arquivos locais estão iguais ao HEAD, mas divergem
  da produção; 6 divergem nos três estados; 2 arquivos locais não rastreados
  divergem da produção. Isso confirma que o HEAD atual não representa todo o
  código em execução.
- Postgres/Timescale, Redis, Evolution API/Manager, Authentik, Caddy, GLPI e Psono
  estavam ativos na coleta. As imagens externas inspecionadas estavam fixadas
  por digest no runtime.
- O Compose Psono foi identificado em `/opt/ness-os-psono/docker-compose.yml`.
  O Psono tem timer local de backup e timer de verificação de restauração ativos.
- Restauração isolada Psono executada em `2026-09-25 18:04:13–18:04:53 -03`, a
  partir do snapshot do conjunto `20260925T013239-0300`: checksums aprovados,
  51 tabelas restauradas, endpoint HTTP 200, assinatura válida e chave pública
  correspondente. Containers/volume temporários foram limpos e produção ficou
  saudável.
- Zabbix canônico usa MariaDB `10.11.18-MariaDB`. O comando `docker` não está
  instalado nesse host, consistente com a implantação nativa usada pelo teste de
  restauração isolada. O conjunto local `20260925T220022-0300` foi copiado para o
  snapshot Restic `15a5ef41be82e65eda4fc5be285d948a1daeccd0c68f0a46ceb9090b168c190e`.
  Cópia externa, `restic check` completo e restore isolado passaram; restore
  verificou Zabbix 7.0.27, MariaDB 10.11.18, 203 tabelas, 685 hosts,
  64.226 itens, 26.697 triggers, 362 templates e schema obrigatório 7000000.
  Essa evidência comprova o conjunto de 25/09, não o disparo seguinte. Na
  tentativa de 27/09, SSH à porta 22 expirou e a porta documentada 2222 rejeitou
  a chave (`Permission denied (publickey)`); backup local/externo e timers atuais
  do Zabbix permanecem sem verificação.
- A API do Zabbix autenticada retorna 260 hosts ao usuário técnico, mas nega
  `template.get` por falta de permissão. A validação funcional read-only permanece
  parcial e bloqueia a onda Zabbix; nenhum ajuste de permissões foi feito.
- Na VPS AIOps, a coleta read-only de 27/09 confirmou o conjunto local
  `20260926T230011-0300`, checksums e snapshot Restic `4ca60242`; restore isolado
  de 862,761 MiB com `--verify`, 26 arquivos e limpeza temporária aprovados.
  Os timers local e externo estão ativos e os serviços terminaram com código 0.
  Detalhes em
  [`phase-0-aiops-recovery-2026-09-27.md`](phase-0-aiops-recovery-2026-09-27.md).
  Essa coleta não renova hashes do código ou das imagens.

## Bloqueios

1. Revisar e aprovar o candidato local limpo `ec76784`; ele permanece na branch
   local de execução e não está publicado nem associado a produção.
2. Publicar e fixar por digest as 8 imagens sem digest identificadas no snapshot
   local atualizado.
3. Revisar os 41 arquivos de backend divergentes e coletar hashes de produção
   para os 47 arquivos montados/instalados que ainda não foram observados.
4. Renovar as evidências locais, externas e dos timers do Zabbix; o último
   conjunto comprovado é de 25/09 e o acesso SSH válido ainda não foi recuperado.
5. Reconciliar o estado do destino Zabbix `169.58.234.9` antes de qualquer
   cutover; esta evidência não o promove a origem canônica.
6. Completar o baseline autenticado da UAT e a permissão de leitura de templates
   no Zabbix antes da onda funcional, sem ampliar privilégios sem revisão.

Até resolver os bloqueios de evidência Zabbix atual, reconciliação, digest,
rollback e CI acima, não criar tag nem declarar a release pronta. O backup AIOps
mais recente está restaurado e verificado externamente; isso não aprova release
nem cutover.
