/** Traduz uma falha em algo que a tela consegue mostrar: código curto e estável + mensagem. */

export interface ErrorSurface {
  code: string;
  message: string;
}

/** FNV-1a de 32 bits: estável entre navegadores e sessões, ao contrário de Math.random. */
function hash(texto: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0').slice(0, 6).toUpperCase();
}

export function describeError(erro: unknown): ErrorSurface {
  const mensagem =
    erro instanceof Error
      ? erro.message || erro.name
      : typeof erro === 'string'
        ? erro
        : 'Falha inesperada';

  // O código acompanha a mensagem: dá para casar o que o usuário vê com a linha do log.
  // Mensagem com id ou URL no meio muda o código para o mesmo defeito — é identificador
  // de ocorrência, não de causa.
  return { code: `HUB-${hash(mensagem)}`, message: mensagem };
}
