# Segredos de automação — SOPS/age

Psono é o cofre humano. Serviços não devem consultar o Psono durante o boot: os
segredos de automação são cifrados com SOPS/age e materializados em arquivos
root-only para os consumidores legados (`env_file` e `EnvironmentFile`).

## Gate de bootstrap

1. Dois custodians geram chaves age separadamente.
2. Somente as chaves públicas entram em `.sops.yaml`.
3. As chaves privadas ficam offline/Psono e são testadas em cerimônia de recovery.
4. `sops` e `age` são instalados por versão/checksum aprovado.
5. Um arquivo de staging é cifrado, decifrado sem eco e validado por dois custodians.

O host x86_64 pode receber as versões aprovadas com
`sudo ./install-sops-age.sh`. O instalador fixa SOPS `3.13.3` e age `1.3.2`,
valida SHA-256 antes de instalar e recusa sobrescrever qualquer binário
existente divergente. A instalação não cria identidades age nem altera
segredos/consumidores.

Até esse gate, `.sops.yaml.example` permanece um template e nenhum recipient
fictício pode ser promovido.

## Janela de compatibilidade

1. Criar o ciphertext SOPS sem remover o `.env` root-only atual.
2. Renderizar com `render-env.sh` para `/run/ness-os` ou `/etc/ness-os`.
3. Reiniciar um consumidor por vez e validar saúde/negação.
4. Confirmar que a credencial antiga é rejeitada.
5. Somente então revogar a antiga e remover o caminho legado.

Rollback retorna o consumidor ao arquivo root-only anterior ainda preservado;
nunca reativa uma credencial já revogada.
