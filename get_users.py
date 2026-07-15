import subprocess

cmd = [
    'sshpass', '-p', 'lav9f1e5CICu!vyh',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    'docker exec ninf-glpi-db mysql -u glpi --password=glpi_pass_nessops_2026 glpi -e "SELECT id, name, realname, firstname, phone, phone2 FROM glpi_users;" -B'
]
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    import sys
    print("Error:", res.stderr, file=sys.stderr)
    sys.exit(res.returncode)
print(res.stdout)
