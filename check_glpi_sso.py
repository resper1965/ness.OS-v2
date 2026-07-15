import subprocess, os

env = os.environ.copy()
env["SSHPASS"] = "lav9f1e5CICu!vyh"

queries = [
    # Check if GLPI is configured to auto-add external auth users
    "SELECT id,name,value FROM glpi_configs WHERE name IN ('is_users_auto_add','ssovariables_id','ssologout_url','existing_auth_server_field_clean_domain');",
    # Check all users 
    "SELECT id,name,authtype,auths_id,is_active FROM glpi_users ORDER BY id LIMIT 20;",
    # Check auth sources
    "SELECT * FROM glpi_authldaps LIMIT 5;",
    # Check GLPI PHP error log for SSO clues  
]

for q in queries:
    print(f"\n=== QUERY: {q} ===")
    cmd = [
        'sshpass', '-e',
        'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
        'root@144.91.115.242',
        f"docker exec ninf-glpi-db mysql -uglpi -pglpi_pass_nessops_2026 glpi -e \"{q}\""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)

# Also check PHP error logs
print("\n=== GLPI PHP Error Logs ===")
cmd2 = [
    'sshpass', '-e',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    "docker exec ninf-glpi tail -30 /var/log/apache2/error.log 2>/dev/null || docker exec ninf-glpi find /var/log -name '*.log' -exec tail -5 {} +"
]
res2 = subprocess.run(cmd2, capture_output=True, text=True, env=env)
print(res2.stdout)
if res2.stderr:
    print("STDERR:", res2.stderr)

# Check GLPI files log
print("\n=== GLPI files log ===")
cmd3 = [
    'sshpass', '-e',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    "docker exec ninf-glpi tail -30 /var/www/html/glpi/files/_log/php-errors.log 2>/dev/null || echo 'no php-errors.log'"
]
res3 = subprocess.run(cmd3, capture_output=True, text=True, env=env)
print(res3.stdout)
if res3.stderr:
    print("STDERR:", res3.stderr)
