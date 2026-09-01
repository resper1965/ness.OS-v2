# Organização e quarentena do repositório — 24/08/2026

## Resultado

A organização foi autorizada por Ricardo Esper e executada de forma recuperável. Nenhum arquivo foi apagado.

| Classe | Quantidade | Destino/tratamento |
|---|---:|---|
| arquivos locais com segredos | 4 | `/home/resper/ness-os-quarantine/2026-08-24-repository/secrets` |
| runtimes/venvs acidentais | 4 entradas | `/home/resper/ness-os-quarantine/2026-08-24-repository/runtime` |
| scripts e artefatos avulsos legados da raiz | 66 | `/home/resper/ness-os-quarantine/2026-08-24-repository/root-legacy` |
| planos históricos da raiz | 4 | movidos para `docs/legacy/` |
| código, testes, documentação, assets e infraestrutura candidatos a versionamento | preservados | permaneceram no workspace |

A quarentena fica fora do repositório, com diretórios `700` e conteúdo sem acesso para grupo/outros. Ela contém material possivelmente sensível e não deve ser anexada, sincronizada ou publicada. A recuperação é feita movendo apenas o arquivo explicitamente revisado de volta ao destino correto.

## Correção da classificação Gitleaks

A varredura inicial havia resumido 69 achados como “não versionados”. A triagem de 24/08 refinou esse rótulo:

- os 69 achados estavam em 24 arquivos ignorados pelo Git, não nos arquivos de projeto candidatos a commit;
- três eram arquivos locais de configuração/chaves na primeira triagem;
- a suíte de testes recriou `app/backend/vapid_keys.json`; esse quarto arquivo também foi retirado do workspace e preservado na quarentena, evidenciando que a geração automática de VAPID durante import/teste precisa ser eliminada antes do fechamento do código;
- os demais estavam na `.venv` Windows local e eram majoritariamente padrões de bibliotecas/dependências;
- após mover segredos e runtimes para fora do workspace, Gitleaks 8.30.1 retornou **zero achado no snapshot**, com redaction total e nenhum segredo impresso.

Isso não revoga credenciais já expostas nem limpa o histórico Git. Chaves informadas em chat, arquivos antigos ou logs continuam comprometidas até rotação no provedor.

## Conteúdo preservado para versionamento

Permaneceram no workspace:

- `.github/workflows/secret-scan.yml`;
- código e testes novos de AIOps, GLPI e RBAC;
- `config/glpi/ness-os-foundation-v1.yaml`;
- documentação, ADRs, arquitetura, apresentação e evidências;
- scripts e units de infraestrutura revisados;
- assets de branding e o plugin `nessai` ainda sujeito a revisão própria.

Permanecer no workspace não significa aprovação automática para commit. O próximo gate é revisar o diff por domínio, criar commits atômicos e repetir testes/Gitleaks em um checkout limpo.
