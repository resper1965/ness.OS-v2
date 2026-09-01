"""
run_provision_sso.py -- Deploy e executa o script de provisionamento SSO no Authentik.

Uso (a partir da maquina local com WSL):
    python3 run_provision_sso.py

O script:
1. Faz upload do provision_authentik_sso.py para o servidor via SCP
2. Copia para dentro do container ninf-authentik-server
3. Executa com python3
4. Limpa os arquivos temporarios
"""
import subprocess
import sys

# Configuracao do servidor
VPS_IP = "144.91.115.242"
VPS_PASSWORD = "<REVOKED_USE_PSONO>"
CONTAINER_NAME = "ninf-authentik-server"
LOCAL_SCRIPT = "/home/resper/zabbix.ness/provision_authentik_sso.py"

SSH_OPTS = [
    '-o', 'StrictHostKeyChecking=yes',
    '-o', 'KexAlgorithms=curve25519-sha256',
    '-o', 'IPQoS=none',
]


def ssh_cmd(command: str) -> subprocess.CompletedProcess:
    """Executa um comando remoto via SSH."""
    return subprocess.run(
        ['sshpass', '-p', VPS_PASSWORD, 'ssh'] + SSH_OPTS +
        [f'root@{VPS_IP}', command],
        capture_output=True, text=True
    )


def scp_upload(local_path: str, remote_path: str):
    """Upload de arquivo via SCP direto (sem chunking)."""
    res = subprocess.run(
        ['sshpass', '-p', VPS_PASSWORD, 'scp'] + SSH_OPTS +
        [local_path, f'root@{VPS_IP}:{remote_path}'],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        print(f"ERRO no upload SCP: {res.stderr}")
        sys.exit(1)
    print("  Upload SCP completo.")


def main():
    print("=" * 60)
    print("  Authentik SSO Provisioning -- Deploy & Execute")
    print("=" * 60)

    # 1. Upload via SCP
    print("\n[1/4] Fazendo upload do script via SCP...")
    scp_upload(LOCAL_SCRIPT, "/tmp/provision_sso.py")

    # 2. Verificar integridade
    print("[2/4] Verificando integridade do arquivo...")
    res = ssh_cmd('python3 -m py_compile /tmp/provision_sso.py')
    if res.returncode != 0:
        print(f"ERRO: Script com erro de sintaxe apos upload:")
        print(res.stderr)
        sys.exit(1)
    print("  Sintaxe OK.")

    # 3. Copiar para container e executar
    print("[3/4] Copiando para container e executando...")
    res = ssh_cmd(
        f'docker cp /tmp/provision_sso.py {CONTAINER_NAME}:/tmp/provision_sso.py && '
        f'docker exec -e PYTHONPATH=/ -w / -i {CONTAINER_NAME} '
        f'/ak-root/.venv/bin/python3 /tmp/provision_sso.py'
    )

    if res.returncode != 0:
        print(f"\nERRO na execucao:")
        print(res.stderr)
        sys.exit(1)
    else:
        print(res.stdout)

    # 4. Limpeza
    print("[4/4] Limpando arquivos temporarios...")
    ssh_cmd(f'docker exec -u root -i {CONTAINER_NAME} rm -f /tmp/provision_sso.py')
    ssh_cmd('rm -f /tmp/provision_sso.py')

    print("\n" + "=" * 60)
    print("  Provisionamento SSO concluido!")
    print("=" * 60)


if __name__ == "__main__":
    main()
