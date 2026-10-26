# Experiência ness. no GLPI — paleta instalada, não selecionada

O GLPI 11.0.8 observado tem `_themes` persistente e vazio. A paleta
[`ness-light.scss`](../../config/glpi/ness-light.scss) usa o mecanismo nativo
de temas: todas as regras ficam sob `:root[data-glpi-theme="ness-light"]` e
alteram apenas variáveis de cor documentadas. Preto/branco formam as superfícies;
BlueDot `#00ade8` aparece na prévia, sem ser usado como texto pequeno sobre
branco. A paleta não altera logo, favicon, login nem core.

Em 13/10/2026, o arquivo foi instalado em
`/var/glpi/files/_themes/ness-light.scss` no volume persistente, sem alterar
preferência de usuário ou default global. O hash local/remoto é
`afa23f55708a77787370a1fdf02c15845c2b61edd36d201f656a9974c1de6fcf`;
permissões `644:33:33`; GET público do login permaneceu `302` para SSO.
O ThemeManager nativo, consultado pelo verificador read-only
[`glpi-theme-readback.php`](../../infra/scripts/glpi-theme-readback.php),
retornou `ness-light` com rótulo `ness.`. Nenhum tema foi selecionado.
Não houve renderização autenticada ou seleção piloto, portanto T10 continua
**não aceito**. O arquivo temporário de transferência foi removido após o
readback; o arquivo versionado é a fonte de retorno.
O aceite nominal está registrado na
[issue #78](https://github.com/resper1965/n-infraops/issues/78), com instruções
enviadas a Ismael e Ricardo; nenhuma preferência deve ser promovida antes do
retorno dessa validação.

## Promoção controlada

1. Exportar a preferência anterior do usuário piloto. Selecionar
   `ness-light` somente nessa conta; não mudar o default global nem todas as
   entidades nesta etapa.
2. Inspecionar com sessão nominal as jornadas solicitante, técnico e gestor em
   390 px, 1440 px e zoom 200%: login, lista/detalhe/criação de ticket,
   anexos, ativo, pesquisa, painel e logout. Verificar foco, contraste,
   rolagem, erros e estados vazios. A marca visual não deve duplicar título.
3. Se houver regressão, voltar a preferência anterior e remover somente o
   arquivo candidato. Não restaurar banco nem desinstalar plugins para reverter
   cores. Promover default por entidade só após o piloto passar e haver
   mecanismo de rollback confirmado.

Logo/favicon/imagem de login continuam como estão: a personalização suportada
depende do plugin Branding e de licença/ativos aprovados, ainda não comprovados.
Não redesenhar nem substituir o logo do GLPI por arquivo inventado. Catálogo,
emails, PDFs e prévias seguem pendentes de inspeção por jornada.

Referências oficiais: [paletas GLPI 11](https://glpi-user-documentation.readthedocs.io/fr/latest/advanced/custom_palettes.html)
e [configuração visual por entidade](https://help.glpi-project.org/faq/glpi/general_setup).
