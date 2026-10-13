# ADR 0020 — fronteira de entidade para manutenção GLPI

- Status: proposta; acesso produtivo bloqueado até ensaio negativo completo
- Data: 13/10/2026
- Escopo: identidade `svc_ness_maintenance` (106), perfil 13, entidade Alupar (1)

## Problema comprovado

A associação da conta 106 à entidade 1, marcada não recursiva, não impediu
`changeActiveEntities` para a descendente 5 seguido de leitura de Computer 5.
O teste direto falhou; a conta 106 foi desativada e deve permanecer assim.
Verificar a entidade efetiva no cliente Hub evita um erro do consumidor, mas
não restringe quem possui o token e chama a API GLPI diretamente. O perfil 13
não deve ganhar privilégios para contornar essa falha. A conta Hub 94 não muda.

## Direção escolhida para protótipo

Testar em ambiente isolado um adaptador privado com operações específicas de
inventário para a entidade 1. O adaptador guarda o token GLPI upstream e
estabelece a entidade no servidor; não expõe `initSession`, `Session-Token`,
`changeActiveEntities`, caminhos arbitrários, IDs globais ou proxy genérico.
Uma rede privada exclusiva deve ser o único caminho do adaptador ao GLPI.
Hub/operador não podem alcançar a rota nativa com a identidade 106. O cliente
continua validando readback e não envia segredos ao navegador.

O contrato inicial é pequeno: consultar identificador de ativo autorizado,
criar Computer/NetworkEquipment validado, ler por ID já associado à entidade
1 e excluir somente um ativo criado pela mesma operação com rollback. Outras
operações — busca livre, subitens, anexos, exportação, batch e mutação de
ticket — ficam negadas até contrato, testes e necessidade próprios. A
identidade upstream só recebe os direitos exatos comprovados para esse
contrato. Nenhum endpoint passa URL, método ou itemtype ao GLPI sem allowlist.

## Condições antes de implantar

1. Confirmar no runtime a topologia de redes, portas e rotas; o Compose de
   raiz não é prova da topologia atual do GLPI. Sem bloqueio direto de rede,
   o adaptador não é fronteira de segurança.
2. Criar fixtures sintéticas de entidade 1 e descendente 5 fora da produção;
   exportar estado e ensaiar rollback sem alterar dados reais.
3. Testar leitura, busca, exportação, subitens e escrita via interface
   permitida; testar também requests diretos à API nativa, path encoding,
   IDs de outra entidade, sessão reaproveitada e batch. Todos os percursos
   não contratados devem negar antes da chamada upstream.
4. Demonstrar acesso autorizado à entidade 1 e negativa à 5 por todas as
   rotas expostas, com logs sem token ou payload sensível.
5. Só então decidir deployment, rotação de credencial e eventual reativação
   normal da conta 106. Uma alternativa que exija ampliar escopo da conta
   ou mudar hierarquia de entidades requer decisão humana explícita.

## Estado e reversão

Esta ADR não aprova T03, G2, ativação de 106 nem onda de três ativos. O
rollback do futuro adaptador será bloquear a rota e desativar 106; os ativos
existentes e a conta Hub 94 devem permanecer intactos.
