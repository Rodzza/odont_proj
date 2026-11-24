import { describe, expect, it } from 'vitest';
import { lerReais, linkCobranca, paraCampo, reais } from './dinheiro';

describe('dinheiro', () => {
  it('lê valores do jeito que se digita no Brasil', () => {
    expect(lerReais('250')).toBe(25000);
    expect(lerReais('1.234,56')).toBe(123456);
    expect(lerReais('R$ 80,5')).toBe(8050);
    expect(lerReais('80.5')).toBe(8050);
    expect(lerReais('abc')).toBeNull();
    expect(lerReais('')).toBeNull();
  });
  it('mostra em reais', () => {
    expect(reais(123456).replace(/\s/g, ' ')).toBe('R$ 1.234,56');
    expect(paraCampo(8050)).toBe('80,50');
  });
  it('monta a cobrança no WhatsApp', () => {
    const l = linkCobranca('Maria Silva', '(91) 98888-7777', 15000, '2026-12-10', 'Consultório');
    expect(l).toContain('wa.me/5591988887777');
    expect(decodeURIComponent(l!)).toContain('10/12/2026');
    expect(linkCobranca('Maria', null, 1, '2026-01-01', 'C')).toBeNull();
  });
});
