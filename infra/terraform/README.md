# 🏗️ Terraform - Infraestrutura Contabo (zabbix.ness)

Configuração Terraform para provisionamento automatizado da infraestrutura do projeto **zabbix.ness** na Contabo.

## 📋 Recursos Provisionados

| Recurso | Tipo | Especificações | Custo Estimado |
|---------|------|----------------|----------------|
| **Cloud VPS** | `contabo_instance` | 8 vCPU, 30 GB RAM, 800 GB SSD (V3) | ~€9.99/mês |
| **Object Storage** | `contabo_object_storage` | 250 GB S3-compatível (EU) | €2.49/mês |
| **Chave SSH** | `contabo_secret` | Ed25519 para acesso seguro | — |

> ⚠️ **Nota:** O plano original previa um **Storage VPS 40** (1.2 TB, €20/mês), porém o Contabo **não suporta Storage VPS via API/Terraform**. Utilizamos o **Cloud VPS V3** como alternativa gerenciável via IaC. Para provisionar um Storage VPS, use o [Painel de Controle Contabo](https://my.contabo.com).

## 📁 Estrutura de Arquivos

```
terraform/
├── versions.tf                    # Versões do Terraform e provider
├── variables.tf                   # Definição de todas as variáveis
├── main.tf                        # Recursos principais (VPS, Storage, SSH)
├── outputs.tf                     # Outputs pós-provisionamento
├── environments/
│   └── prod.tfvars                # Valores de produção (com placeholders)
├── .gitignore                     # Proteção de arquivos sensíveis
└── README.md                      # Este arquivo
```

## 🚀 Guia de Uso

### 1. Pré-requisitos

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5.0
- Conta Contabo com acesso à API
- Credenciais OAuth2 (obter em [my.contabo.com/api/details](https://my.contabo.com/api/details))
- Par de chaves SSH gerado

### 2. Gerar Chave SSH

```bash
# Gerar chave Ed25519 (recomendado)
ssh-keygen -t ed25519 -C "ness_admin@zabbix-ness" -f ~/.ssh/ness_admin

# Exibir a chave pública (copiar para o tfvars)
cat ~/.ssh/ness_admin.pub
```

### 3. Configurar Credenciais

**Opção A — Variáveis de ambiente (recomendado):**

```bash
export TF_VAR_contabo_oauth2_client_id="seu-client-id"
export TF_VAR_contabo_oauth2_client_secret="seu-client-secret"
export TF_VAR_contabo_oauth2_user="seu-email@contabo.com"
export TF_VAR_contabo_oauth2_pass="sua-senha-api"
export TF_VAR_ssh_public_key="ssh-ed25519 AAAA... ness_admin@zabbix-ness"
```

**Opção B — Arquivo de segredos local (não versionado):**

```bash
# Criar arquivo de segredos (já incluído no .gitignore)
cp environments/prod.tfvars secrets.auto.tfvars
# Editar e preencher com valores reais
```

### 4. Inicializar e Aplicar

```bash
# Navegar até o diretório terraform
cd terraform/

# Inicializar o Terraform (baixa o provider Contabo)
terraform init

# Validar a configuração
terraform validate

# Visualizar o plano de execução
terraform plan -var-file=environments/prod.tfvars

# Aplicar as mudanças (provisionar recursos)
terraform apply -var-file=environments/prod.tfvars

# Verificar os outputs (IP da VPS, URL do Object Storage, etc.)
terraform output
```

### 5. Acessar a VPS

Após o provisionamento:

```bash
# Conectar via SSH
ssh ness_admin@$(terraform output -raw vps_ip_v4)

# Ou usando o comando completo do output
terraform output -raw connection_summary
```

## 🗑️ Destruir Recursos

```bash
# Destruir toda a infraestrutura (use com cautela!)
terraform destroy -var-file=environments/prod.tfvars
```

## 📦 Object Storage (S3-compatível)

Após o provisionamento, configure o acesso S3 com a AWS CLI:

```bash
# Configurar perfil Contabo S3
aws configure --profile contabo-s3
# Access Key e Secret Key: obter no painel Contabo após provisionamento

# Criar bucket de backup
aws --profile contabo-s3 \
    --endpoint-url $(terraform output -raw object_storage_s3_url) \
    s3 mb s3://zabbix-ness-backups

# Listar buckets
aws --profile contabo-s3 \
    --endpoint-url $(terraform output -raw object_storage_s3_url) \
    s3 ls
```

## 🔒 Segurança

- **Nunca** commite credenciais reais em repositórios Git
- O arquivo `terraform.tfstate` contém dados sensíveis — use backend remoto em produção
- Rotacione as credenciais OAuth2 periodicamente
- Use chaves SSH Ed25519 (mais seguras que RSA)
- Considere o uso de [HashiCorp Vault](https://www.vaultproject.io/) para gerenciamento de segredos

## 📝 Notas Importantes

1. **Storage VPS vs Cloud VPS:** O Contabo não suporta Storage VPS via API. Este projeto usa Cloud VPS V3.
2. **Object Storage por região:** Apenas UMA instância de Object Storage é permitida por região.
3. **Product IDs:** Os IDs podem mudar. Consulte a API antes de aplicar.
4. **Image IDs:** Verifique IDs de imagem atualizados via `contabo_image` data source ou API.
