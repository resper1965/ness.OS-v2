# Contexto da IA e isolamento de cliente — 08/09/2026

Publicado no hub e nos workers; verificação final às 22:34:48 UTC.

## Alterações

- Triagem e pós-incidente enviam uma lista explícita de campos de incidente.
  Tags arbitrárias, credenciais, cadastro do cliente, IDs internos e payload de
  items não são mais serializados integralmente no prompt de triagem.
- Sanitização percorre listas, listas aninhadas e dicionários em qualquer nível.
  Valores sob chaves sensíveis são substituídos integralmente, inclusive quando
  contêm objetos/listas. Authorization, Cookie e variantes api-key foram incluídos.
- O worker de pós-incidente exige incidente persistido e cliente registrado em
  `ninf_customer_name`. Usa host, descrição, severidade e ticket desse registro,
  rejeita ticket divergente e conflito de cliente entre incidente e ativo. Não cria
  incidentes a partir do corpo da solicitação para contornar essa validação.
- A busca vetorial junta os relatórios aos incidentes e compara clientes com o
  incidente atual. Clientes ausentes e vínculos de ativo conflitantes ficam de fora.
  O construtor do prompt também exclui similares cujo cliente não coincide.
- A representação do vetor é vinculada como JSON textual e convertida explicitamente
  para `vector`, evitando o envio de array SQL incompatível com o operador pgvector.
- Logs fictícios de falha de serviço foram removidos. Sem fonte integrada de logs,
  a seção recebe uma lista vazia; não há fabricação de evidência operacional.
- Chamadas de embedding e geração usam `x-goog-api-key` no cabeçalho. A chave não
  é colocada na URL. Erros registram somente a classe da exceção, inclusive no
  relatório de fallback; o ticket original permanece nesse relatório.

O cabeçalho de autenticação de geração foi conferido na documentação oficial
consultada via Context7: https://ai.google.dev/gemini-api/docs/migrate-to-interactions.
Não foi alterado o modelo contratado nem feito consumo pago para validar a mudança.

## Provas

- 259 testes do backend aprovados, MyPy em 77 arquivos e Ruff nos arquivos alterados.
- Testes de segredo em dicionário dentro de lista, metadata excluída do prompt,
  cliente divergente, incidente ausente, ticket incorreto, chave fora da URL,
  ausência de chave em logs e ausência de logs inventados.
- SQL real extraído do arquivo do worker foi executado no PostgreSQL do hub usando
  tabelas temporárias em transação. Mesmo com vetor de outro cliente mais próximo,
  somente o vizinho do cliente correto foi retornado. Cliente ausente e ativo
  conflitante foram excluídos. Rollback removeu todas as tabelas temporárias.
- Após publicação, contexto canônico verificado com incidente Cavan existente;
  fingerprint inexistente rejeitado antes do provedor; sanitização e lista de
  campos verificadas no runtime. Nenhum ticket ou relatório de cliente foi criado
  pelos testes.
- API e dois workers reiniciados com TERM/encerramento normal. Monitor final: todos
  os componentes ok, duas respostas de workers, filas vazias, zero falhas/retries
  e nenhuma entrega pendente.

Verificador SQL reproduzível: `infra/scripts/hub-ai-tenant-query-check.py`.
Evidência protegida no servidor: `/opt/n-infraops/rollback/ai-context-20260908/`,
incluindo arquivos anteriores `*.before`, `tenant-query-check.jsonl`,
`runtime-check.jsonl` e `health-after.json`.

Reversão deve restaurar em conjunto sanitizer, analyzer, gemini e postmortem e
recarregar API/workers. O módulo aditivo ai_context pode permanecer sem consumidores;
não há necessidade de excluir dados ou reverter schema.

## Limites

Os padrões de sanitização cobrem os formatos implementados e testados; não provam
detecção universal de segredos arbitrários inseridos em texto livre. MISP, política
completa de dados externos, aprovação humana auditável, fonte real de logs,
contrato de métricas e validação do provedor/modelo de embeddings continuam no
aceite F5. Nenhum relatório antigo foi apagado ou declarado retroativamente limpo.
