import { describe, expect, it } from 'vitest';
import { describeError } from './error-surface';

describe('describeError', () => {
  it('usa a mensagem do Error e gera código estável', () => {
    const a = describeError(new Error('Falha ao ler a fila'));
    const b = describeError(new Error('Falha ao ler a fila'));
    expect(a.message).toBe('Falha ao ler a fila');
    expect(a.code).toMatch(/^HUB-[0-9A-F]{6}$/);
    expect(a.code).toBe(b.code);
  });

  it('mensagens diferentes geram códigos diferentes', () => {
    expect(describeError(new Error('a')).code).not.toBe(describeError(new Error('b')).code);
  });

  it('aceita string e valor desconhecido sem estourar', () => {
    expect(describeError('texto puro').message).toBe('texto puro');
    expect(describeError(undefined).message).toBe('Falha inesperada');
    expect(describeError(null).code).toMatch(/^HUB-/);
  });
});
