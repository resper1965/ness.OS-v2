#!/usr/bin/env bash
set -Eeuo pipefail

readonly TARGET_USER="ness_admin"
readonly TARGET_HOSTNAME="${NESS_HOSTNAME:-zabbix-transmutation}"
readonly PUBLIC_KEY_FILE="${1:-/root/ness_os_hostinger_kvm8.pub}"
readonly SSH_DROPIN="/etc/ssh/sshd_config.d/00-ness-os-hardening.conf"

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

if [[ ! -s ${PUBLIC_KEY_FILE} ]]; then
  echo "public key file not found or empty: ${PUBLIC_KEY_FILE}" >&2
  exit 1
fi

case "${2:-prepare}" in
  prepare)
    if ! id "${TARGET_USER}" >/dev/null 2>&1; then
      useradd --create-home --shell /bin/bash "${TARGET_USER}"
    fi
    usermod --append --groups sudo "${TARGET_USER}"
    install -d -m 0700 -o "${TARGET_USER}" -g "${TARGET_USER}" "/home/${TARGET_USER}/.ssh"
    install -m 0600 -o "${TARGET_USER}" -g "${TARGET_USER}" "${PUBLIC_KEY_FILE}" "/home/${TARGET_USER}/.ssh/authorized_keys"
    install -m 0440 /dev/stdin "/etc/sudoers.d/90-${TARGET_USER}" <<EOF
${TARGET_USER} ALL=(ALL:ALL) NOPASSWD: ALL
EOF
    visudo --check --strict
    hostnamectl set-hostname "${TARGET_HOSTNAME}"
    ;;
  harden)
    id "${TARGET_USER}" >/dev/null
    test -s "/home/${TARGET_USER}/.ssh/authorized_keys"
    install -m 0644 /dev/stdin "${SSH_DROPIN}" <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers ness_admin
EOF
    rm -f /etc/ssh/sshd_config.d/60-ness-os-hardening.conf
    sshd -t
    systemctl reload ssh
    ;;
  baseline)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get -y dist-upgrade
    apt-get install -y --no-install-recommends \
      apparmor-utils auditd ca-certificates curl fail2ban gnupg jq python3-systemd rsync \
      unattended-upgrades ufw

    timedatectl set-timezone America/Sao_Paulo
    timedatectl set-ntp true
    install -d -m 0755 /etc/systemd/resolved.conf.d
    install -m 0644 /dev/stdin /etc/systemd/resolved.conf.d/60-ness-os.conf <<'EOF'
[Resolve]
LLMNR=no
MulticastDNS=no
EOF
    systemctl restart systemd-resolved

    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp comment 'SSH key-only bootstrap'
    ufw logging low
    ufw --force enable

    install -m 0644 /dev/stdin /etc/fail2ban/jail.d/ness-os-sshd.local <<'EOF'
[sshd]
enabled = true
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd
EOF
    systemctl enable fail2ban auditd
    systemctl restart fail2ban
    systemctl start auditd

    if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
      if [[ ! -e /swapfile ]]; then
        fallocate -l 8G /swapfile
        chmod 0600 /swapfile
        mkswap /swapfile
      fi
      swapon /swapfile
    fi
    grep -qE '^/swapfile[[:space:]]' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    install -m 0644 /dev/stdin /etc/sysctl.d/60-ness-os.conf <<'EOF'
vm.swappiness=10
kernel.kptr_restrict=2
kernel.dmesg_restrict=1
fs.protected_fifos=2
fs.protected_regular=2
EOF
    sysctl --system >/dev/null
    ;;
  *)
    echo "usage: $0 PUBLIC_KEY_FILE {prepare|harden|baseline}" >&2
    exit 2
    ;;
esac
