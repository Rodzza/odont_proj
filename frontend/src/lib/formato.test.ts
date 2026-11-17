import { describe, expect, it } from 'vitest';
import { cpf, idade, isoDia, linkConfirmacao, minutosDoDia, semana, telefone } from './formato';

describe('formatação', () => {
  it('telefone e CPF', () => {
    expect(telefone('91988887777')).toBe('(91) 98888-7777');
    expect(telefone('9133334444')).toBe('(91) 3333-4444');
    expect(cpf('52998224725')).toBe('529.982.247-25');
  });
  it('idade considera se já fez aniversário', () => {
    expect(idade('1990-05-10', new Date(2026, 4, 9))).toBe(35);
    expect(idade('1990-05-10', new Date(2026, 4, 10))).toBe(36);
    expect(idade(null)).toBeNull();
  });
  it('semana de segunda a sábado', () => {
    const s = semana(new Date(2026, 10, 19)); // quinta
    expect(s.map(isoDia)).toEqual(['2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21']);
  });
  it('minutos do dia', () => expect(minutosDoDia('2026-12-01T09:30:00')).toBe(570));
  it('link do WhatsApp com DDI e mensagem', () => {
    const l = linkConfirmacao('Maria da Silva', '91988887777', '2026-12-01T09:30:00', 'Consultório Sorriso')!;
    expect(l.startsWith('https://wa.me/5591988887777?text=')).toBe(true);
    expect(decodeURIComponent(l)).toContain('Olá, Maria!');
    expect(decodeURIComponent(l)).toContain('às 09:30');
    expect(linkConfirmacao('A', '123', '2026-12-01T09:30:00', 'X')).toBeNull();
  });
});
