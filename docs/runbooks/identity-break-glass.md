# Runbook: acesso break-glass de identidade

## Objetivo e limites

Recuperar o plano de controle quando o Authentik ou o fluxo normal de login não
estiver disponível. A conta break-glass é exclusiva para emergência, não integra
grupos de operação diária e não substitui contas administrativas nominativas.
Este procedimento não autoriza mudanças em produção antes da aprovação do gate
da Fase 0.

## Gatilhos

Ativar somente quando pelo menos uma condição for verdadeira:

- indisponibilidade do IdP impede a resposta a um incidente operacional ou de
  segurança;
- todas as contas administrativas normais perderam acesso, MFA ou recuperação;
- contenção imediata exige revogar sessões ou credenciais comprometidas.

Falha de uma conta individual, conveniência ou atividade planejada não é gatilho.

## Autorização e custódia

1. Um responsável registra o incidente, impacto, sistemas necessários e duração
   estimada.
2. Duas pessoas distintas aprovam o uso: responsável pelo incidente e outro
   custodiante autorizado. Quem solicita não pode ser o único aprovador.
3. A credencial fica em item dedicado do Psono, com acesso nominal e dupla
   custódia. Senhas, recovery codes, seeds TOTP, cookies e tokens não entram no
   ticket, terminal, evidência ou log.
4. Se Psono estiver indisponível, usar somente a cópia de recuperação lacrada
   prevista no procedimento aprovado de custódia; registrar quem abriu e quem
   testemunhou, sem copiar o segredo para o registro.

## Execução

1. Confirmar o gatilho e as duas aprovações; iniciar registro de horário e
   custodiante.
2. Recuperar a credencial sem incluí-la em argumentos de processo ou histórico
   do shell; acessar apenas o serviço necessário.
3. Usar a conta para restaurar o fluxo normal ou conter a ameaça. Não criar
   usuários, ampliar grupos, exportar dados ou alterar MFA além do escopo
   aprovado no incidente.
4. Registrar ações, objetos afetados, resultados e referências de evidência
   redigidas. Não anexar material autenticador.
5. Encerrar a sessão e revogar tokens/sessões emitidos durante o uso.
6. Rotacionar a credencial break-glass e qualquer segredo exposto; confirmar que
   a credencial anterior deixou de funcionar.
7. Desabilitar a conta até a próxima emergência e confirmar o login normal com
   duas contas administrativas nominativas.

## Auditoria e encerramento

O registro deve conter: identificador do incidente, gatilho, aprovadores,
custodiante, início/fim, serviços acessados, ações realizadas, referência da
rotação e evidência de revogação. Não registrar segredos nem conteúdo do cofre.

O responsável de segurança revisa o registro no próximo dia útil, confirma que a
conta foi desabilitada e atribui correções permanentes. Teste periódico de
recuperação usa conta descartável ou ambiente controlado; não ativa a conta
break-glass de produção fora de janela formalmente aprovada.

## Evidência de recuperação Psono

Depois de testar recuperação dos dois custodians, registrar no host do Psono em
`/etc/ness-os/psono-recovery-tested`, arquivo root-owned, sem conteúdo secreto:

```text
tested_at=AAAA-MM-DD
custodians_tested=2
```

Manter modo `0600`. O relatório F2 aceita evidência de até 180 dias. Esse arquivo
é uma atestação operacional; não substitui os recovery codes guardados no cofre
nem o teste de restore do backup.

O relatório Authentik exige `AUTHENTIK_REQUIRED_ADMIN_USERS`, lista separada por
vírgulas dos usernames administrativos canônicos. Conferir a lista contra os
grupos administrativos atuais antes de cada leitura; fornecê-la somente no
ambiente protegido do operador, nunca em arquivo versionado. A saída mostra
apenas contagens, não os usernames nem os fatores cadastrados.
