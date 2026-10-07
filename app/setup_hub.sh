#!/usr/bin/env bash
# ==============================================================================
# n.infraops — Setup and Hardening Script for AIOps Hub
# ==============================================================================
# Este script deve ser executado como root na nova máquina Contabo.
# Uso: curl -s https://raw.githubusercontent.com/resper1965/n-infraops/main/app/setup_hub.sh | bash

set -e

echo "[+] Iniciando Hardening e Setup do AIOps Hub..."

# 1. Atualizar pacotes
echo "[+] Atualizando pacotes do Debian..."
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
apt-get install -y ufw fail2ban curl wget git htop

# 2. Configurar UFW (Firewall)
echo "[+] Configurando UFW..."
ufw default deny incoming
ufw default allow outgoing

# Portas essenciais
ufw allow 22/tcp      # SSH padrão
ufw allow 80/tcp      # HTTP (Caddy Let's Encrypt)
ufw allow 443/tcp     # HTTPS (Caddy)

echo "y" | ufw enable
ufw status

# 3. Configurar fail2ban
echo "[+] Configurando fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

# 4. Criar diretórios da aplicação
echo "[+] Criando estrutura de diretórios para o AIOps Hub..."
mkdir -p /opt/n-infraops
cd /opt/n-infraops

echo ""
echo "================================================================================"
echo "✅ Setup Base Concluído!"
echo "O servidor está protegido com UFW e Fail2ban."
echo ""
echo "Próximos passos (A serem executados pelo operador):"
echo "1. Clonar o repositório em /opt/n-infraops:"
echo "   git clone -b feat-hub-stack https://github.com/resper1965/n-infraops.git ."
echo "2. Copiar as variáveis:"
echo "   cp app/.env.example app/.env"
echo "   (edite o arquivo app/.env colocando as senhas fortes)"
echo "3. Subir a stack:"
echo "   cd app && docker compose up -d"
echo "================================================================================"
