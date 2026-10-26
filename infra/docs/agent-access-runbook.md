# Acesso do agente às VPS — runbook

Acesso operacional mínimo para um agente automatizado executar reconhecimento
e verificação read-only. Não autoriza deploy, mutação de produção ou mudança de
gate.

## Identidade

| Item | Valor |
|---|---|
| Chave pública | `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN3Yr5hM6WjgNx3qIQ8DDAT+xts1WfsPp2MDxDnFvtxn agente@stack-nessos-2026-10` |
| Fingerprint | `SHA256:qEBGMTX8+zIBl1FDbmmfHXKzOc+06iuszAjzB9ds0p0` |
| Tipo | ed25519, sem passphrase (necessário para operação não interativa) |
| Origem permitida | **sem restrição `from=`** — ver *Limites* |
| Cópia privada | somente no host de origem; nunca em repositório, cofre de texto ou mensagem |

A chave privada **não é** backup de nada: se for perdida, o acesso se recupera
pelo Rescue System em cerca de dez minutos. O ativo durável é este procedimento,
não o arquivo.

## Hosts autorizados

| Host | Papel | Porta SSH | Usuário | Chave instalada |
|---|---|---|---|---|
| `169.58.234.9` | UAT Zabbix (`zbx-prd-01`) | 22 | `ness_admin` | 26/10, sim |
| `144.91.115.242` | Hub AIOps (`vmi3409271`) | 22 | `ness_admin` | 26/10, sim |
| `144.91.72.202` | Zabbix produção (`zabbix-srv01`) | 2222 | `ness_admin` | 26/10, sim |

Estado em 26/10/2026: as três instâncias do projeto aceitam a chave como
`ness_admin` com `sudo`. A `npentest` (`169.58.178.187`) está fora do escopo do
ness.OS e não foi tratada.

## Instalação (Rescue System da Contabo)

Necessário quando não há nenhuma chave autorizada no host. Exige acesso ao
painel da Contabo; o rescue não usa o `sshd` do disco, por isso funciona mesmo
com `PasswordAuthentication no`.

1. Painel → *Servers & Hosting* → menu do servidor → **Rescue System** → definir
   senha temporária → iniciar.
2. `ssh root@<IP>` com a senha do passo 1. O aviso de host key alterada é
   esperado: é o sshd do rescue.
3. Executar o bloco abaixo.
4. `sync && umount /mnt/rootfs && reboot`.
5. Confirmar no painel que o rescue não permaneceu ativo.

```bash
KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN3Yr5hM6WjgNx3qIQ8DDAT+xts1WfsPp2MDxDnFvtxn agente@stack-nessos-2026-10'
mkdir -p /mnt/rootfs && ROOT=""
for d in $(lsblk -lnpo NAME,FSTYPE | awk '$2 ~ /^(ext4|xfs)$/ {print $1}'); do
  mount "$d" /mnt/rootfs 2>/dev/null || continue
  [ -f /mnt/rootfs/etc/passwd ] && { ROOT="$d"; break; }
  umount /mnt/rootfs
done
[ -z "$ROOT" ] && { echo "FALHOU: disco nao encontrado"; exit 1; }
H="/mnt/rootfs/home/ness_admin"
UG=$(awk -F: '$1=="ness_admin"{print $3":"$4}' /mnt/rootfs/etc/passwd)
[ -z "$UG" ] && { echo "FALHOU: ness_admin ausente"; exit 1; }
install -d -m 700 "$H/.ssh"
AK="$H/.ssh/authorized_keys"; touch "$AK"
# arquivo sem quebra de linha final faz o append concatenar na chave anterior
if [ -s "$AK" ] && [ -n "$(tail -c1 "$AK")" ]; then echo >> "$AK"; fi
grep -qxF "$KEY" "$AK" 2>/dev/null || echo "$KEY" >> "$AK"
chmod 600 "$AK"
chown -R "$UG" "$H/.ssh"
awk '{print NR": "length($0)" bytes"}' "$AK"
```

O bloco preserva chaves existentes, detecta a partição raiz pelo conteúdo
(`/etc/passwd`) e aborta sem alterar nada se o usuário não existir.

**Falha conhecida (26/10/2026).** A primeira versão deste bloco usava
`grep -qF` (substring) e não garantia quebra de linha final. Na AIOps o
`authorized_keys` não terminava em `\n`: a chave nova foi concatenada na última
linha, gerando uma única linha de `210` bytes (`102 + 108`) que o `sshd` não
consegue interpretar — o resultado foi `Permission denied (publickey)` com a
chave visivelmente "presente" no arquivo. O sintoma que identifica o caso é a
contagem de linhas: um `authorized_keys` com menos linhas do que chaves
instaladas. O `grep -qxF` e a quebra de linha garantida acima corrigem a causa.

## Revogação

No host, remover a linha correspondente de `/home/ness_admin/.ssh/authorized_keys`.
Não é necessário reiniciar serviço. Revogar em todos os hosts quando:

- a origem `148.230.77.242` for descomissionada;
- houver suspeita de comprometimento do host de origem;
- o agente deixar de operar.

## Rotação

Gerar novo par no host de origem (`ssh-keygen -t ed25519 -C agente@<host>-<ano>-<mes>`),
instalar pelo procedimento acima, testar, e só então remover a chave anterior.
Nunca manter duas chaves ativas sem motivo.

## Limites

- A chave entra como `ness_admin` com `sudo`; qualquer uso de `sudo` deve ser
  read-only salvo autorização explícita registrada.
- Deploy, corte, restauração e escrita em produção exigem janela, GO e rollback,
  independente do acesso existir.
- O host de origem é a KVM8 da Hostinger (`148.230.77.242`), classificada no
  registro de 02/09 como KVM8 devolvida, mas é hoje a `stack` (titularidade a confirmar, ver reconciliação de 26/10). Ao descomissioná-la, este runbook
  precisa ser reexecutado a partir do novo host permanente.
- Não há restrição `from=` nas entradas instaladas. Fixar a origem no IP atual
  não compensa: a KVM8 será descomissionada, e a saída IPv6 da `stack`
  (`2a02:4780:14:e47d::1`) não é coberta por uma regra IPv4. Aplicar a restrição
  junto com a rotação para o host permanente.
