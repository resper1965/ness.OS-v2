#!/usr/bin/env bash
# Role common vs. a Debian 12 container with an existing sshd drop-in and an
# authorized_keys file without trailing newline. Usage: bash infra/ansible/tests/test_common_role.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ANSIBLE="$ROOT/infra/bin/ansible"
NAME="ness-common-test-$$"
mkdir -p /tmp/opencode
TMP="$(mktemp -d /tmp/opencode/common-role.XXXXXX)"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
dx() { docker exec "$NAME" bash -c "$1"; }

"$ANSIBLE" ansible-galaxy collection install community.docker:==4.8.3 >/dev/null
ssh-keygen -q -t ed25519 -N '' -C synthetic-existing -f "$TMP/key"
docker run -d --name "$NAME" debian:12 sleep infinity >/dev/null
dx 'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server python3 sudo >/dev/null'
docker cp "$TMP/key.pub" "$NAME:/tmp/key.pub"
# shellcheck disable=SC2016  # expansions run inside the container
dx 'install -d -m 755 /run/sshd; mkdir -p /etc/ssh/sshd_config.d
useradd -m -s /bin/bash ness_admin
install -d -m 700 -o ness_admin -g ness_admin /home/ness_admin/.ssh
printf "%s" "$(cat /tmp/key.pub)" > /home/ness_admin/.ssh/authorized_keys
chown ness_admin:ness_admin /home/ness_admin/.ssh/authorized_keys
printf "ClientAliveInterval 60\n" > /etc/ssh/sshd_config.d/99-ness-gate0.conf'
dx "service ssh start >/dev/null"
BEFORE="$(dx 'sha256sum /etc/ssh/sshd_config /etc/ssh/sshd_config.d/99-ness-gate0.conf')"

printf '[test]\ncontainer ansible_connection=docker ansible_host=%s ansible_user=root ansible_python_interpreter=/usr/bin/python3 ansible_become=false\n' "$NAME" > "$TMP/inventory"
printf -- '- hosts: test\n  gather_facts: false\n  roles: [common]\n' > "$TMP/play.yml"
run() {
  ANSIBLE_ROLES_PATH="$ROOT/infra/ansible/roles" ANSIBLE_STDOUT_CALLBACK=default ANSIBLE_GATHERING=explicit \
    "$ANSIBLE" ansible-playbook -i "$TMP/inventory" -e "@$ROOT/infra/ansible/inventory/group_vars/all.yml" \
    --tags usuario,ssh "$TMP/play.yml"
}

run || fail "first run"
[ "$(dx 'grep -c "" /home/ness_admin/.ssh/authorized_keys')" = 2 ] || fail "authorized_keys must have 2 lines"
[ "$(dx 'ssh-keygen -lf /home/ness_admin/.ssh/authorized_keys | wc -l')" = 2 ] || fail "authorized_keys must have 2 valid keys"
[ "$(dx 'sha256sum /etc/ssh/sshd_config /etc/ssh/sshd_config.d/99-ness-gate0.conf')" = "$BEFORE" ] || fail "sshd_config or 99 drop-in changed"
dx 'test -f /etc/ssh/sshd_config.d/50-ness-baseline.conf' || fail "baseline drop-in missing"
dx 'sshd -t' || fail "sshd -t"
run | tee "$TMP/second.log" >/dev/null || fail "second run"
grep -q 'changed=0 ' "$TMP/second.log" || { cat "$TMP/second.log"; fail "second run not idempotent"; }
echo PASS
