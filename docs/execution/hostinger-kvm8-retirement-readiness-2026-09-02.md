# Readiness para descarte da Hostinger KVM8 — 02/09/2026

## Decisão atual

**Descarte/cancelamento bloqueado.** Nenhuma host key foi aceita, removida ou
substituída; nenhuma nova sessão SSH foi aberta durante esta investigação; nenhum
recurso da Hostinger foi alterado. O token de API foi revogado pelo usuário, então
o inventário do control plane também não foi refeito.

A próxima conexão só pode ocorrer depois de confirmar novamente a fingerprint
ED25519 da instância atual por um canal fora do SSH: console autenticado do hPanel
ou resposta do suporte vinculada à VM `1013444` e ao IP `148.230.77.242`.

## Evidências locais

- O bootstrap de 21/08/2026 registra hostname `zabbix-transmutation`, VM `1013444`
  e host key ED25519 `SHA256:6CkaVGeOhXVUfzDZ7IKnX3OIo72Td+ZHz5Cjj1fnhig`.
- O `~/.ssh/known_hosts` local ainda associa ao IP as três chaves históricas:
  ED25519 `6CkaVGe…`, RSA `mhO8Mpy…` e ECDSA `jjSAKy0…`. Elas também estão no
  backup `known_hosts.old`. A consulta foi somente leitura.
- A chave privada dedicada existe fora do repositório, pertence ao usuário local,
  está em modo `0600` e sua chave pública tem fingerprint `SHA256:P2NzlH4…`.
  Esta é a identidade **do cliente**, não a identidade do servidor.
- `~/.ssh/config` contém uma configuração histórica conflitante: o IP
  `148.230.77.242` também aparece no bloco `nphish`, com usuário `root` e outra
  identidade. Isso pode selecionar credenciais erradas, mas não explica uma
  divergência criptográfica das três host keys do servidor.
- Conforme a observação operacional fornecida para este fechamento, a primeira
  sessão identificou `zabbix-transmutation`, `zabbix-server` inativo/mascarado e
  ausência de listeners 10051/HTTP, `cloudflared` e Docker. Na tentativa posterior,
  todas as host keys apresentadas divergiram das três entradas locais. Essa
  segunda tentativa foi interrompida sem aceitar as chaves.

As fingerprints são identificadores públicos e foram abreviadas acima, exceto a
ED25519 já registrada como evidência de bootstrap. Nenhuma chave privada, token,
senha, dump, nome de arquivo remoto ou conteúdo do banco foi coletado.

## Diagnóstico e hipóteses

O sintoma observado é a troca simultânea das identidades ED25519, RSA e ECDSA.
Isso não é explicado pela colisão no `ssh_config`: usuário e chave de cliente
afetam autenticação, mas a verificação da host key acontece antes dela.

Hipóteses, em ordem prática de probabilidade/risco:

1. A VM foi reinstalada ou o SSH foi reprovisionado depois de 21/08, regenerando
   todas as host keys.
2. O IP foi reassociado a outra instância. A configuração histórica `nphish`
   comprova que o endereço já teve mais de um contexto local e aumenta a
   necessidade de confirmar VM ID + IP no provedor.
3. As host keys foram deliberadamente regeneradas dentro da mesma VM, sem que a
   mudança tenha sido registrada neste repositório.
4. Há interceptação ou desvio de rota. Não há evidência local que a confirme, mas
   ela não pode ser descartada antes da verificação fora de banda.

Os arquivos locais não distinguem essas hipóteses. O bloqueio exato é a falta de
uma identidade atual da instância confirmada por canal independente.

## Gate fail-closed de inventário

O script
[`inventory-hostinger-kvm8-retirement.sh`](../../infra/scripts/inventory-hostinger-kvm8-retirement.sh)
faz somente o inventário remoto de readiness. Ele:

- exige fingerprint ED25519 atual e uma declaração de origem
  `provider-console` ou `provider-support-ticket` antes de contatar a porta SSH;
- usa `ssh-keyscan` apenas para descoberta e aborta antes do SSH se a chave
  descoberta não for exatamente a fingerprint confirmada fora de banda;
- usa `-F /dev/null`, usuário `ness_admin`, chave dedicada, algoritmo ED25519 e
  um `known_hosts` temporário, eliminando a colisão do bloco local `nphish`;
- força `StrictHostKeyChecking=yes`, desabilita atualização de host keys,
  senha e keyboard-interactive, e ignora os arquivos globais de host keys;
- executa somente leituras: identidade/SO/capacidade, estados de serviços,
  processos/listeners e contagem/tamanho agregado dos diretórios de dados;
- não lista arquivos nem consulta conteúdo ou credenciais do banco;
- sempre retorna `provider_destruction_readiness=BLOCKED`. Um inventário limpo
  prova apenas quiescência remota, nunca autoriza destruição.

Exemplo, somente depois da confirmação fora de banda:

```bash
bash infra/scripts/inventory-hostinger-kvm8-retirement.sh \
  --host-key-fingerprint 'SHA256:FINGERPRINT_ATUAL_CONFIRMADA' \
  --verification-source provider-console
```

Não usar a fingerprint histórica deste documento como substituto da confirmação
atual. Não copiar uma fingerprint de `ssh-keyscan`, do erro SSH ou de
`known_hosts` para satisfazer o gate.

## Critérios para liberar o descarte

O inventário remoto pode ser considerado concluído quando retornar
`host_key_verification=PASS`, `inventory_transport=PASS` e
`remote_quiescence=PASS`. Mesmo assim, o descarte continua bloqueado até haver
evidência independente de todos os itens abaixo:

- VM ID `1013444`, IP e titularidade/contrato confirmados no hPanel;
- nenhum snapshot, volume, backup ou IP faturável fora do escopo pretendido;
- código, evidências e backups necessários copiados para fora da KVM8, com
  checksums conferidos no destino independente;
- nenhuma dependência de produção, DNS, agente ou proxy apontando para a KVM8;
- credenciais temporárias identificadas e plano de revogação aprovado;
- autorização explícita para eliminar dados e cancelar/devolver a instância.

## Sequência de fechamento após o gate

1. Capturar no hPanel a VM ID, o IP, o estado do contrato e a fingerprint atual.
2. Executar o inventário read-only acima e arquivar apenas sua saída saneada.
3. Conferir externamente os artefatos/checksums e as dependências de produção.
4. Fazer revisão humana do checklist e obter autorização explícita de descarte.
5. Pelo hPanel, inventariar e então eliminar/cancelar somente os recursos
   expressamente aprovados. Este repositório não automatiza essa etapa.
6. Após confirmação do provedor, remover a public key Hostinger `563082`, destruir
   a chave privada dedicada local e limpar as entradas históricas de host key.
   Essas ações estão deliberadamente adiadas e não foram executadas agora.
7. Registrar recibo/data do cancelamento e confirmar que não restou cobrança nem
   recurso órfão.

## Teste local

[`test-hostinger-kvm8-retirement-inventory.sh`](../../infra/tests/test-hostinger-kvm8-retirement-inventory.sh)
usa mocks e comprova que fingerprint divergente ou fonte não confiável não chama
SSH, que o `known_hosts` real não muda, que as opções SSH isolam a configuração
local e que uma falha de quiescência mantém o descarte bloqueado.
