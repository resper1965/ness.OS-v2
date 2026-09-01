# ness.OS — estágio do projeto (2026-08-25)

## Concluído nesta etapa

- Nova VPS permanente `zbx-prd-01` preparada, restaurada e validada em
  isolamento.
- Frontend UAT local disponível por túnel SSH, sem HTTP/HTTPS público.
- Hardening de rede, SSH, serviços e permissões comprovado.
- Baseline de polimento gerada: FortiGate, switches, Windows, tags, templates,
  mapas e escalations priorizados.
- Backup offline criptografado do destino e recuperação externa Restic
  comprovados com checksums.

## Pronto para execução controlada

- Onda 1 de polimento: FortiGate por appliance e dois switches mal
  classificados, com rollback sem limpeza.
- UAT segura por túnel, sem coletar nem notificar.
- Backup recorrente pronto para habilitação após o gate de coleta.

## Dependências humanas/externas

- Homologar Authentik: identidade, MFA, logout e revogação.
- Confirmar ativo/modelo/owner no GLPI e aprovar piloto.
- Autorizar início controlado de coleta, DNS/HTTPS público e posterior corte.
