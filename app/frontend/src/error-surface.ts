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

  // O código acompanha a mensagem: o mesmo defeito gera o mesmo código, e dá para
  // procurar no log sem expor a mensagem crua ao usuário.
  return { code: `HUB-${hash(mensagem)}`, message: mensagem };
}
