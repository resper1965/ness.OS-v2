# Hostinger KVM8 — ativo devolvido e fora de escopo

Data: 2026-09-02

## Estado final

O proprietário confirmou que a antiga KVM8 não pertence mais à Ness. O endereço
anterior pode estar reassociado e passa a ser infraestrutura de terceiro. Desde
essa confirmação, qualquer conexão, varredura, inventário, cancelamento ou outra
ação contra a instância atual está proibida.

O token da API Hostinger foi revogado pelo proprietário. A assinatura SSH atual
não foi aceita nem gravada localmente.

## Evidência que levou ao bloqueio

- A identidade histórica do servidor registrada após o bootstrap deixou de
  coincidir com as chaves apresentadas pelo endereço anterior.
- Três consultas de descoberta, anteriores à confirmação da devolução, retornaram
  um conjunto novo e consistente de chaves ED25519, RSA e ECDSA.
- A troca simultânea é compatível com reinstalação ou reassociação do endereço e
  não autorizava atualizar `known_hosts`.
- Nenhum arquivo válido foi copiado da instância reassociada. Duas transferências
  incompletas foram interrompidas e os arquivos parciais locais foram removidos.

## Higienização local executada

- chave privada e chave pública dedicadas à KVM8 removidas de `~/.ssh/`;
- entradas do endereço antigo removidas de `known_hosts` e de seu backup;
- bloco SSH histórico `nphish` que apontava ao mesmo endereço removido;
- scripts capazes de contatar a antiga KVM8 bloqueados antes de qualquer comando
  de rede;
- documentação mantida apenas como registro histórico, sem instrução operacional
  de reconexão.

A chave histórica `id_nphish_vps` não foi removida porque não foi criada
especificamente para a KVM8 e pode pertencer a outro ativo. Ela não possui mais
bloco ativo no `ssh_config`; sua destinação exige inventário próprio.

## Limite de autorização

O repositório não automatiza cancelamento no provedor. Como o ativo já foi
devolvido, não há etapa de readiness ou descarte a executar contra o endereço.
Resta somente confirmar no hPanel, sem acessar a VPS, que não existe assinatura,
IP, snapshot, volume ou cobrança residual vinculada à conta da Ness.

## Prova preventiva

`infra/tests/test-hostinger-kvm8-retirement-inventory.sh` executa os quatro scripts
históricos com ferramentas de rede falsas e exige saída 64 antes de qualquer
tentativa de SSH, SCP, rsync ou `ssh-keyscan`.
