import { describe, expect, it } from 'vitest';
import manifest from '../public/manifest.json';

// O #232 apontou o manifest para um PNG que não existia. Este teste impede a repetição:
// todo ícone declarado precisa existir em public/.
const arquivos = Object.keys(import.meta.glob('../public/icons/*.png')).map((caminho) =>
  caminho.replace('../public', ''),
);

describe('manifest do PWA', () => {
  it('todo ícone declarado existe no build', () => {
    for (const icon of manifest.icons) {
      if (icon.type === 'image/svg+xml') continue;
      expect(arquivos, `faltando ${icon.src}`).toContain(icon.src);
    }
  });

  it('tem 192, 512 e uma variante maskable', () => {
    const sizes = manifest.icons.map((i) => i.sizes);
    const purposes = manifest.icons.map((i) => i.purpose);
    expect(sizes).toContain('192x192');
    expect(sizes).toContain('512x512');
    expect(purposes).toContain('maskable');
  });

  it('a variante maskable é 512 e não reaproveita a versão "any"', () => {
    const maskable = manifest.icons.filter((i) => i.purpose === 'maskable');
    expect(maskable).toHaveLength(1);
    expect(maskable[0].src).not.toBe('/icons/icon-512.png');
  });
});
