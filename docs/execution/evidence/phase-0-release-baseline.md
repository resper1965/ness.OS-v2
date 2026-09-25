# Evidência do baseline de release da Fase 0

Data da coleta: 2026-09-25 (America/Sao_Paulo).

## Escopo de produção

- Hub/AIOps: `144.91.115.242` (`aiops`).
- Zabbix canônico: `144.91.72.202` (`infra-zabbix`).
- VPS `169.58.234.9` (`nes-os-zabbix-pr-01`): infraestrutura do projeto, mas
  registrada no plano de migração como destino de UAT/cutover pendente; não é a
  origem canônica usada para a recuperação nesta fase.
- `169.58.178.187` (`npentest`): excluída do escopo deste projeto.

## Manifesto local

O gerador determinístico e seus seis testes foram adicionados e estão no
repositório. Para atualizar o snapshot após a consolidação da árvore, execute:

```bash
python3 infra/scripts/ness-release-manifest.py --output release-manifest.json
python3 -m pytest infra/tests/test-ness-release-manifest.py -q
```

O snapshot registrado em `phase-0-production-manifest.json` marca
`release_ready=false`: a árvore está suja, e as imagens construídas para API,
frontend e workers não possuem digest de registry no Compose. O manifesto deve
ser regenerado após reconciliar e revisar as mudanças locais.

## Observações em produção

- A VPS AIOps executa API, frontend e workers com imagens locais (`app-api`,
  `app-frontend` e `app-worker-*`); os IDs de imagem observados não são digests de
  release publicados. O Compose em produção foi identificado em
  `/opt/n-infraops/app/docker-compose.yml`.
- O código Python montado do host para o Hub teve hashes coletados para 75
  arquivos. 41 divergem do workspace local. A comparação também encontrou
  divergências no Compose do Hub e no Caddy do Psono; 71 outros arquivos
  implantados ainda não têm hash de produção coletado. O manifesto lista cada
  caminho divergente e cada caminho não observado.
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
  restauração isolada. `ness-zabbix-backup.timer` está habilitado. A execução
  catch-up de 16:23 -03 terminou às 17:02:33 com sucesso; o conjunto
  `20260925T162305-0300` teve os sete checksums aprovados e os serviços
  registrados ativos antes e depois. Próxima execução: 22:00 -03.
- `ness-zabbix-object-storage-backup.timer` está desabilitado. Portanto não há
  snapshot externo recente do Zabbix comprovado nesta evidência. Não habilite o
  timer até resolver a rotação pendente das credenciais do object storage e
  executar a validação externa correspondente.
- Na VPS AIOps, `ness-aiops-backup.timer`,
  `ness-aiops-object-storage-backup.timer` e `ness-psono-backup.timer` estavam
  habilitados. A execução do object storage mais recente listada era
  2026-09-25 00:30 -03.

## Bloqueios

1. Consolidar os arquivos locais e confirmar o commit de release; há mudanças
   preexistentes na árvore que não foram agrupadas nem revisadas nesta evidência.
2. Publicar e fixar por digest as imagens próprias do projeto.
3. Revisar os 41 arquivos de backend divergentes e coletar hashes de produção
   para os 71 arquivos implantados que ainda não foram observados.
4. Exportar e verificar no object storage o conjunto Zabbix atual
   `20260925T162305-0300` depois da rotação autorizada das credenciais.
5. Reconciliar o estado do destino Zabbix `169.58.234.9` antes de qualquer
   cutover; esta evidência não o promove a origem canônica.

Até resolver esses pontos, não criar tag nem declarar a release pronta.
