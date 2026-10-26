# Hub — publicação local candidata (13/10/2026)

Commit revisado: `92eced45c1adf75416475163146b03b3e4e350a7` (PR #81,
draft). Builder: Docker Desktop/Buildx via Ubuntu WSL; GitHub Actions continua
desativado. O publicador `infra/scripts/publish-hub-images.py` concluiu com
exit 0. Black, Flake8, Ruff, Mypy, 24 testes backend, `npm ci`, lint/build
frontend, auditoria npm sem vulnerabilidades e scan de segredos passaram.

Imagens publicadas em pacotes GHCR **privados** e puxadas novamente por digest:

- API: `ghcr.io/resper1965/ninf-api@sha256:c9b059912b8185e074f3238da004bfce1ee81b37b520cf6ca488d96fa945dd60`
- Frontend: `ghcr.io/resper1965/ninf-frontend@sha256:23d512507600e072405d9db043877bda9fb5d9aadc9b4f243227811019594b2e`

Manifesto local de referências: `/home/resper/.local/share/ness-os/releases/2026-10-13-hub-candidate.json`,
diretório 0700/arquivo 0600. Não é manifesto de deploy e não contém segredo.

Ainda **não** é release aprovado: os quatro checks requeridos pela `main`
estão vinculados ao app GitHub Actions (`app_id=15368`). Falta configurar um
emissor externo com identidade restrita e atestação do commit/digest, ensaiar
que PR sem seus quatro status continua bloqueado, validar pull pela identidade
de produção, revisar PR #81 e os gates de implantação. Nenhum host produtivo,
DNS ou coletor foi alterado por esta publicação.
