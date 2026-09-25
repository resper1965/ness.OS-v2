# Branding do cofre

Os arquivos `logo.png` e `logo-inverse.png` são cópias imutáveis dos ativos
aprovados em `ness_logos/`. Eles preservam a assinatura `ness.` isolada, em
caixa baixa, com lettering preto ou branco e BlueDot `#00ade8`.

- `logo.png`: assinatura branca para o cartão escuro da tela de entrada;
- `logo-inverse.png`: assinatura branca para a barra superior escura;
- `custom.css`: tokens, easing e fallback de movimento reduzido.
- `index.html` e `portal-index.html`: título da aba `vault ness.`.
- `language-default.js`: usa `pt-BR` na primeira visita, sem sobrescrever o
  idioma que o usuário já escolheu.
- `service-worker.js` e `service-worker-load.js`: removem somente o precache do
  cliente, sem apagar cookies, sessão ou armazenamento local criptográfico.

O favicon original do Psono é mantido até existir um favicon oficial aprovado.
Não substituir estes ativos por imagens geradas ou redesenhadas.
