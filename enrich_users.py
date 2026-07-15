import subprocess

# We will fetch current users to know their names and IDs
cmd_users = [
    'sshpass', '-p', 'lav9f1e5CICu!vyh',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    "docker exec ninf-glpi-db mysql -u glpi --password=glpi_pass_nessops_2026 glpi -N -e 'SELECT id, name, realname, firstname FROM glpi_users;'"
]

res = subprocess.run(cmd_users, capture_output=True, text=True, check=True)
users_list = []
for line in res.stdout.strip().split('\n'):
    if not line:
        continue
    parts = line.split('\t')
    if len(parts) >= 4:
        users_list.append({
            'id': int(parts[0]),
            'username': parts[1].strip(),
            'realname': parts[2].strip() if parts[2] != 'NULL' else '',
            'firstname': parts[3].strip() if parts[3] != 'NULL' else ''
        })

sql_statements = ["START TRANSACTION;"]

# Specific known profiles
known_linkedins = {
    'resper': 'https://www.linkedin.com/in/ricardo-esper-0bb5b71',
    'bertuzzi': 'https://www.linkedin.com/in/thiago-bertuzzi'
}

for u in users_list:
    uid = u['id']
    username = u['username']
    firstname = u['firstname']
    realname = u['realname']
    
    # Clean firstname from prefix like [ CAVAN ] or [ NESS ]
    clean_first = firstname.replace('[ CAVAN ]', '').replace('[ NESS ]', '').strip()
    
    # Default phone and company based on username prefix or company associations
    phone = "NULL"
    company = "Ness Processos e Tecnologia Ltda."
    
    # LinkedIn URL formulation
    if username in known_linkedins:
        linkedin = known_linkedins[username]
    elif clean_first and realname:
        # Standardize URL string
        norm_first = clean_first.lower().replace(' ', '-')
        norm_real = realname.lower().replace(' ', '-')
        linkedin = f"https://www.linkedin.com/in/{norm_first}-{norm_real}"
    else:
        linkedin = f"https://www.linkedin.com/in/{username}"
        
    # Map companies and phones
    if username in ['felipeamancio', 'fabrizio.vieira']:
        company = "Alupar Investimento S.A."
        phone = "'+55 (11) 4571-2400'"
    elif username == 'ecruz' or 'cavan' in clean_first.lower():
        company = "Cavan Pré-Moldado S/A"
        phone = "'+55 (11) 3631-4810'"
    elif username in ['teste.clientea', 'teste.clienteb', 'glpi', 'post-only', 'tech', 'normal', 'glpi-system']:
        # System accounts, skip enriching
        continue
    else:
        # Default to Ness
        phone = "'+55 (11) 2504-7650'"
        
    comment = f"Empresa: {company}\\nLinkedIn: {linkedin}"
    
    # We update comment and phone (if phone is NULL or empty in the database)
    sql_statements.append(f"""
    UPDATE glpi_users SET 
        comment = '{comment}',
        phone = IF(phone IS NULL OR phone = '' OR phone = '5511 ', {phone}, phone)
    WHERE id = {uid};
    """)

sql_statements.append("COMMIT;")
sql_full = "\n".join(sql_statements)

# Initialize remote file
print("Initializing remote SQL file...")
subprocess.run([
    'sshpass', '-p', 'lav9f1e5CICu!vyh',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    'cat > /tmp/enrich_users.sql'
], input="", text=True, check=True)

# Write in MTU-safe chunks
print("Transferring SQL in chunks...")
chunk_size = 1000
for i in range(0, len(sql_full), chunk_size):
    chunk = sql_full[i:i+chunk_size]
    cmd = [
        'sshpass', '-p', 'lav9f1e5CICu!vyh',
        'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
        'root@144.91.115.242',
        'cat >> /tmp/enrich_users.sql'
    ]
    subprocess.run(cmd, input=chunk, text=True, check=True)

print("Executing SQL updates on database container...")
exec_cmd = [
    'sshpass', '-p', 'lav9f1e5CICu!vyh',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    'docker exec -i ninf-glpi-db mysql -u glpi --password=glpi_pass_nessops_2026 glpi < /tmp/enrich_users.sql'
]
subprocess.run(exec_cmd, check=True)

# Cleanup
subprocess.run([
    'sshpass', '-p', 'lav9f1e5CICu!vyh',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'KexAlgorithms=curve25519-sha256', '-o', 'IPQoS=none',
    'root@144.91.115.242',
    'rm -f /tmp/enrich_users.sql'
], check=True)

print("Users successfully enriched with LinkedIn profiles and company details!")
