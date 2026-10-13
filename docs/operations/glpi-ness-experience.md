# Experiência ness. no GLPI — candidato, não implantado

O GLPI 11.0.8 observado tem `_themes` persistente e vazio. A paleta
[`ness-light.scss`](../../config/glpi/ness-light.scss) usa o mecanismo nativo
de temas: todas as regras ficam sob `:root[data-glpi-theme="ness-light"]` e
alteram apenas variáveis de cor documentadas. Preto/branco formam as superfícies;
BlueDot `#00ade8` aparece na prévia, sem ser usado como texto pequeno sobre
branco. A paleta não altera logo, favicon, login nem core.

## Promoção controlada

1. Confirmar o diretório efetivo `GLPI_THEMES_DIR` (ou `GLPI_VAR_DIR/files/_themes`)
   e exportar paleta/preferência anterior do usuário piloto. Não presumir que
   o caminho do contêiner histórico é o mount efetivo.
2. Copiar apenas `ness-light.scss` ao diretório persistente, com dono/permissão
   iguais aos temas existentes. Selecionar a paleta somente numa conta piloto;
   não mudar o default global nem todas as entidades nesta etapa.
3. Inspecionar com sessão nominal as jornadas solicitante, técnico e gestor em
   390 px, 1440 px e zoom 200%: login, lista/detalhe/criação de ticket,
   anexos, ativo, pesquisa, painel e logout. Verificar foco, contraste,
   rolagem, erros e estados vazios. A marca visual não deve duplicar título.
4. Se houver regressão, voltar a preferência anterior e remover somente o
   arquivo candidato. Não restaurar banco nem desinstalar plugins para reverter
   cores. Promover default por entidade só após o piloto passar e haver
   mecanismo de rollback confirmado.

Logo/favicon/imagem de login continuam como estão: a personalização suportada
depende do plugin Branding e de licença/ativos aprovados, ainda não comprovados.
Não redesenhar nem substituir o logo do GLPI por arquivo inventado. Catálogo,
emails, PDFs e prévias seguem pendentes de inspeção por jornada.

Referências oficiais: [paletas GLPI 11](https://glpi-user-documentation.readthedocs.io/fr/latest/advanced/custom_palettes.html)
e [configuração visual por entidade](https://help.glpi-project.org/faq/glpi/general_setup).
