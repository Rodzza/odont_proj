import { describe, expect, it } from 'vitest';
import { aplicar, faceNaPosicao, resumo, vazio } from './odontograma';

describe('odontograma', () => {
  it('mesial aponta para a linha média em cada quadrante', () => {
    expect(faceNaPosicao(16, 'direita')).toBe('M'); // superior direito do paciente, desenhado à esquerda
    expect(faceNaPosicao(26, 'esquerda')).toBe('M');
    expect(faceNaPosicao(36, 'esquerda')).toBe('M');
    expect(faceNaPosicao(46, 'direita')).toBe('M');
    expect(faceNaPosicao(55, 'direita')).toBe('M');
  });
  it('vestibular fica para fora da boca: em cima na arcada superior, embaixo na inferior', () => {
    expect(faceNaPosicao(11, 'cima')).toBe('V');
    expect(faceNaPosicao(41, 'cima')).toBe('L');
    expect(faceNaPosicao(41, 'baixo')).toBe('V');
    expect(faceNaPosicao(11, 'centro')).toBe('O');
  });
  it('marca e desmarca face; dente ausente não tem face', () => {
    const d1 = aplicar(vazio(16), 'carie', 'centro')!;
    expect(d1.faces).toEqual({ O: 'carie' });
    expect(aplicar(d1, 'carie', 'centro')!.faces).toEqual({});
    const aus = aplicar(d1, 'ausente', 'centro')!;
    expect(aus.situacao).toBe('ausente');
    expect(aus.faces).toEqual({});
    expect(aplicar(aus, 'carie', 'centro')).toBeNull();
  });
  it('situação do dente alterna e hígido limpa tudo', () => {
    const c = aplicar(aplicar(vazio(16), 'restaurado', 'cima')!, 'canal', 'centro')!;
    expect(c.situacao).toBe('canal');
    expect(c.faces).toEqual({ V: 'restaurado' });
    expect(aplicar(c, 'canal', 'centro')!.situacao).toBe('higido');
    expect(aplicar(c, 'higido', 'centro')).toEqual(vazio(16));
  });
  it('resumo legível', () => {
    expect(resumo({ ...vazio(16), situacao: 'canal', faces: { O: 'carie' } })).toBe('canal, O cárie');
  });
});
