# Customização Semântica e Visual do GLPI (Processo NOC/Help Desk)

## Goal
Customizar visual e semanticamente o GLPI (n-ticket.ness.com.br) para alinhar-se perfeitamente com os fluxos operacionais de NOC/Help Desk da ness., incluindo nomenclatura de chamados, perfis de acesso, e identidade visual Montserrat.

## Tasks
- [ ] Task 1: Mapear semântica de chamados no banco de dados → Verify: Executar query para alterar nomes de tipos de chamados (Incident ➔ Incidente / Alerta NOC, Request ➔ Solicitação / Help Desk)
- [ ] Task 2: Configurar perfis de acesso operacionais (NOC e Help Desk) → Verify: Perfis `Operador NOC` e `Analista Help Desk` criados no banco do GLPI com permissões ajustadas
- [ ] Task 3: Padronizar Categorias de ITIL operacionais no banco → Verify: Inserir categorias comuns (Falha de Conectividade, Upgrade de Hardware, Reset de Senha, Alerta de Monitoramento)
- [ ] Task 4: Injetar folha de estilo CSS limpa com Montserrat e paleta ness. → Verify: Atualizar `custom_css_code` na tabela `glpi_entities` para formatar cabeçalhos, botões e fontes globais do GLPI
- [ ] Task 5: Validar a tela de login integrada ao ST-Custom Login → Verify: Validar visualização da tela de login com o logotipo `ness.` e o banner lateral de NOC/SOC carregados via plugin
- [ ] Task 6: Limpar caches e consolidar alterações → Verify: Executar `bin/console cache:clear` e verificar funcionamento do sistema de chamados

## Done When
- [ ] GLPI com nomenclatura NOC/Help Desk nas opções de abertura de chamados.
- [ ] Identidade visual (Montserrat, cores institucionais) aplicada nas telas públicas e internas.
- [ ] Perfis operacionais configurados e utilizáveis.

## Notes
* Todas as alterações de banco serão feitas via script SQL direto na base `glpi` do container MariaDB.
* O design visual respeitará o Montserrat Medium e a paleta de cores institucional com ponto final `#00ade8`.
