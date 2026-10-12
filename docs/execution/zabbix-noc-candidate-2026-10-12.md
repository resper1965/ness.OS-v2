# Zabbix — candidato NOC

Z3 preparado, ainda não publicado/aceito. Inventário atual do destino confirma
dashboard 1 Global view com nove widgets e dashboard 405 com cinco páginas;
as alterações da origem documentadas em setembro não estão nessa restauração.

`config/zabbix/noc-uat-dashboard.json` é payload candidato `dashboard.update`:
cinco widgets nativos, grade de 72 colunas, sem sobreposição, sem geomap
genérico nem filtro inventado. Dashboard privado; a configuração de acesso
dos grupos NOC será validada antes de publicação. Títulos indicam UAT sem
coleta e dados de restore, evitando aparência de saúde atual.

Aplicação: exportar estado completo do dashboard 1 pela API, guardar rollback
protegido, aplicar payload candidato pela API em UAT autorizada e validar
renderização e escopo. Não publicar em produção nem escrever diretamente no
banco. Widget de problemas usa padrão nativo; filtros, severidades e tenant
exigem validação antes do aceite. Não interpretar vazio como ausência de risco.

Aceite restante: API aceita tipos/payload, widgets renderizam corretamente,
contagens reconciliam com snapshot, NOC acessa e cliente não acessa painel
global. Capacidade e fila entram em Z4 com itens reais resolvidos por ID; não
foram incluídos IDs especulativos nesta entrega. Branding do core permanece Z6.
