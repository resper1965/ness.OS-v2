#!/usr/bin/env bash
# Role common vs. a Debian 12 container with an existing sshd drop-in and an
# authorized_keys file without trailing newline (existing key kept, agent key appended). Usage: bash infra/ansible/tests/test_common_role.sh
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
printf "ClientAliveInterval 60\n" > /etc/ssh/sshd_config.d/99-ness-gate0.conf
printf "PermitRootLogin prohibit-password\nAllowUsers ness_admin\n" > /etc/ssh/sshd_config.d/00-ness-nominal-access.conf
printf "Port 22\n" > /etc/ssh/sshd_config.d/50-ness-baseline.conf
printf "ness_admin ALL=(ALL) NOPASSWD: ALL\n" > /etc/sudoers.d/90-ness_admin; chmod 440 /etc/sudoers.d/90-ness_admin'
dx "service ssh start >/dev/null"
FILES='/etc/ssh/sshd_config /etc/ssh/sshd_config.d/00-ness-nominal-access.conf /etc/ssh/sshd_config.d/99-ness-gate0.conf'
BEFORE="$(dx "sha256sum $FILES")"

printf '[test]\ncontainer ansible_connection=docker ansible_host=%s ansible_user=root ansible_python_interpreter=/usr/bin/python3 ansible_become=false\n' "$NAME" > "$TMP/inventory"
printf -- '- hosts: test\n  gather_facts: false\n  roles: [common]\n' > "$TMP/play.yml"
run() {
  ANSIBLE_ROLES_PATH="$ROOT/infra/ansible/roles" ANSIBLE_STDOUT_CALLBACK=default ANSIBLE_GATHERING=explicit \
    "$ANSIBLE" ansible-playbook -i "$TMP/inventory" -e "@$ROOT/infra/ansible/inventory/group_vars/all.yml" \
    --tags usuario,ssh "$TMP/play.yml"
}

run || fail "first run"
AK="$(dx 'cat /home/ness_admin/.ssh/authorized_keys')"
grep -qF "$(cut -d' ' -f2 "$TMP/key.pub")" <<<"$AK" || fail "existing key removed"
grep -qF "$(grep '^admin_ssh_key' "$ROOT/infra/ansible/inventory/group_vars/all.yml" | cut -d' ' -f3)" <<<"$AK" || fail "agent key missing"
dx 'test -f /etc/sudoers.d/90-ness_admin && ! test -e /etc/sudoers.d/ness_admin' || fail "sudoers must be 90-ness_admin only"
[ "$(dx 'cat /etc/sudoers.d/90-ness_admin')" = "ness_admin ALL=(ALL:ALL) NOPASSWD: ALL" ] || fail "pre-existing (ALL) sudoers not corrected to (ALL:ALL) in place"
dx 'visudo -c >/dev/null' || fail "visudo -c"
[ "$(dx "sha256sum $FILES")" = "$BEFORE" ] || fail "sshd_config or existing drop-ins changed"
dx 'test -f /etc/ssh/sshd_config.d/zz-ness-baseline.conf' || fail "baseline drop-in missing"
dx '! test -e /etc/ssh/sshd_config.d/50-ness-baseline.conf' || fail "old 50- drop-in not removed"
dx 'sshd -t' || fail "sshd -t"
EFF="$(dx 'sshd -T')"
# OpenSSH 9.2 prints prohibit-password as without-password
for v in 'clientaliveinterval 60' 'permitrootlogin without-password' 'passwordauthentication no' 'pubkeyauthentication yes' 'port 22' 'allowusers ness_admin'; do
  grep -qx "$v" <<<"$EFF" || fail "effective sshd value missing: $v"
done
run | tee "$TMP/second.log" >/dev/null || fail "second run"
grep -q 'changed=0 ' "$TMP/second.log" || { cat "$TMP/second.log"; fail "second run not idempotent"; }

# negative: existing drop-in forces PasswordAuthentication yes -> role must fail, leave no zz- applied
dx 'rm /etc/ssh/sshd_config.d/zz-ness-baseline.conf; printf "PasswordAuthentication yes\n" > /etc/ssh/sshd_config.d/10-bad.conf'
if run >"$TMP/neg.log" 2>&1; then cat "$TMP/neg.log"; fail "role must fail when PasswordAuthentication yes is forced"; fi
grep -q "Baseline SSH rejeitado" "$TMP/neg.log" || fail "negative case failed for the wrong reason"
dx '! test -e /etc/ssh/sshd_config.d/zz-ness-baseline.conf' || fail "zz- baseline left applied after failed validation"
echo PASS
