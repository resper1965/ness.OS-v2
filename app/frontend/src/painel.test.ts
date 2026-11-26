import { describe, expect, it } from 'vitest';
import { painelQuery } from './components/PainelView';
import { allowedView } from './App';

describe('painel', () => {
  it('sem cliente escolhido não leva parâmetro; com cliente codifica', () => {
    expect(painelQuery(null)).toBe('');
    expect(painelQuery('alupar pe')).toBe('?customer_id=alupar%20pe');
  });
  it('qualquer papel abre o painel', () => {
    expect(allowedView('painel', false, false)).toBe('painel');
    expect(allowedView('painel', true, true)).toBe('painel');
  });
});
