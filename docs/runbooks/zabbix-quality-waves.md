# Zabbix — ondas de qualidade reversíveis

Máximo cinco hosts; executar primeiro dry-run. Não há alteração em produção
por esta ferramenta: `--apply` aceita somente a API HTTPS UAT aprovada. G0/G2
e gates de escrita continuam obrigatórios. Templates removidos usam Unlink,
sem `templates_clear` e sem exclusão de histórico.

```bash
python3 infra/scripts/zabbix-quality-wave.py \
  --inventory config/zabbix/quality-internal-2026-10-12.inventory.json \
  --desired config/zabbix/quality-internal-2026-10-12.desired.json
```

Salvar o plano aprovado fora do Git quando contiver dados operacionais
restritos. Inventário contém apenas hostid, tags e templates; não exportar
macros, tokens, interface credentials ou dados pessoais. Fonte deste exemplo:
banco restaurado do destino em 12/10, não a configuração corrente da origem.

Aplicação autorizada: usar ZABBIX_URL e ZABBIX_TOKEN de runtime protegido,
sem valores em linha de comando, e executar `--apply --plan <plano.json>`.
Rollback: mesmo comando com `--rollback`. Cada lado do plano conserva o estado
anterior/posterior; guardar plano e resultados como evidência protegida.

Preflight compara todos os hosts antes da primeira escrita e verifica novamente
cada host antes/depois de aplicar. Replay não duplica alteração. Falha no meio
da onda interrompe; conferir hosts concluídos antes de rollback. O plano não é
transação distribuída: outro operador pode editar entre leitura e atualização.
Executar em janela exclusiva e interromper se houver divergência.

## Pacote interno inicial

Somente o host 10084 foi identificado inequivocamente como interno. Templates
10001/10047 são preservados; proposta acrescenta tenant, service, technology,
scope e role. Owner, site, environment e criticality não foram inventados.
Ainda não é aceite Z1: completar atributos confirmados e quatro ativos internos
antes de marcar cinco ativos prontos. Hosts de proxies/clientes não entram
automaticamente no pacote ness.
