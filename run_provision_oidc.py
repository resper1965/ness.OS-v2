import subprocess
import base64

def chunk_file(local_path, remote_path):
    with open(local_path, "r", encoding="utf-8") as f:
        content = f.read().encode('utf-8')
    b64_str = base64.b64encode(content).decode('utf-8')
    
    # Clear remote
    subprocess.run([
        'sshpass', '-p', 'lav9f1e5CICu!vyh',
        'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
        'root@144.91.115.242',
        f'echo -n "" > /tmp/temp_prv.b64'
    ], check=True)
    
    # Upload chunks
    chunk_size = 500
    for i in range(0, len(b64_str), chunk_size):
        chunk = b64_str[i:i+chunk_size]
        subprocess.run([
            'sshpass', '-p', 'lav9f1e5CICu!vyh',
            'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
            'root@144.91.115.242',
            f'echo -n "{chunk}" >> /tmp/temp_prv.b64'
        ], check=True)
        
    # Decode to target
    subprocess.run([
        'sshpass', '-p', 'lav9f1e5CICu!vyh',
        'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
        'root@144.91.115.242',
        f'base64 -d /tmp/temp_prv.b64 > /tmp/deploy_oidc.py && rm -f /tmp/temp_prv.b64'
    ], check=True)

# Upload provision_authentik_oidc.py
chunk_file(
    "/home/resper/zabbix.ness/provision_authentik_oidc.py",
    "/tmp/provision_authentik_oidc.py"
)

# Run in container
run_cmd = [
    'sshpass', '-p', 'lav9f1e5CICu!vyh',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    'docker cp /tmp/deploy_oidc.py ninf-authentik-server:/tmp/deploy_oidc.py && ' +
    'docker exec -u root -i ninf-authentik-server python3 /tmp/deploy_oidc.py && ' +
    'docker exec -u root -i ninf-authentik-server rm -f /tmp/deploy_oidc.py && ' +
    'rm -f /tmp/deploy_oidc.py'
]
res = subprocess.run(run_cmd, capture_output=True, text=True)
if res.returncode != 0:
    print("OIDC Provisioning Error:", res.stderr)
else:
    print(res.stdout)
