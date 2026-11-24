/** Regras do odontograma (numeração FDI), sem React, para testar. */

export type Face = 'V' | 'L' | 'M' | 'D' | 'O';
export type EstadoFace = 'carie' | 'restaurado' | 'restaurar';
export type Situacao = 'higido' | 'ausente' | 'extrair' | 'implante' | 'coroa' | 'canal' | 'protese';
export type Posicao = 'cima' | 'baixo' | 'esquerda' | 'direita' | 'centro';

export interface DenteEstado {
  numero: number;
  situacao: Situacao;
  faces: Partial<Record<Face, EstadoFace>>;
  observacao: string | null;
}

/** Linhas do odontograma como o dentista vê: arcada superior em cima, lado direito do paciente à esquerda. */
export const ARCADAS = {
  permanente: {
    superior: [[18, 17, 16, 15, 14, 13, 12, 11], [21, 22, 23, 24, 25, 26, 27, 28]],
    inferior: [[48, 47, 46, 45, 44, 43, 42, 41], [31, 32, 33, 34, 35, 36, 37, 38]],
  },
  deciduo: {
    superior: [[55, 54, 53, 52, 51], [61, 62, 63, 64, 65]],
    inferior: [[85, 84, 83, 82, 81], [71, 72, 73, 74, 75]],
  },
} as const;

const quadrante = (n: number) => Math.floor(n / 10);
export const ehSuperior = (n: number) => [1, 2, 5, 6].includes(quadrante(n));
const ladoDireitoDoPaciente = (n: number) => [1, 4, 5, 8].includes(quadrante(n));

/** Qual face do dente fica em cada posição do desenho. Mesial aponta para a linha média. */
export function faceNaPosicao(n: number, p: Posicao): Face {
  if (p === 'centro') return 'O';
  if (p === 'cima') return ehSuperior(n) ? 'V' : 'L';
  if (p === 'baixo') return ehSuperior(n) ? 'L' : 'V';
  const direito = ladoDireitoDoPaciente(n);
  if (p === 'esquerda') return direito ? 'D' : 'M';
  return direito ? 'M' : 'D';
}

/** Dentes anteriores (incisivos e caninos) têm face incisal, não oclusal. */
export const ehAnterior = (n: number) => n % 10 <= 3;

export const NOME_FACE: Record<Face, string> = { V: 'vestibular', L: 'lingual/palatina', M: 'mesial', D: 'distal', O: 'oclusal/incisal' };

export type Ferramenta = EstadoFace | 'apagar' | Exclude<Situacao, 'higido'> | 'higido';

export const FERRAMENTAS_FACE: { id: EstadoFace | 'apagar'; rotulo: string }[] = [
  { id: 'carie', rotulo: 'Cárie' },
  { id: 'restaurado', rotulo: 'Restaurado' },
  { id: 'restaurar', rotulo: 'A restaurar' },
  { id: 'apagar', rotulo: 'Limpar face' },
];
export const FERRAMENTAS_DENTE: { id: Situacao; rotulo: string }[] = [
  { id: 'extrair', rotulo: 'A extrair' },
  { id: 'ausente', rotulo: 'Ausente' },
  { id: 'canal', rotulo: 'Canal' },
  { id: 'coroa', rotulo: 'Coroa' },
  { id: 'implante', rotulo: 'Implante' },
  { id: 'protese', rotulo: 'Prótese' },
  { id: 'higido', rotulo: 'Dente hígido' },
];

const ehFerramentaFace = (f: Ferramenta): f is EstadoFace | 'apagar' => ['carie', 'restaurado', 'restaurar', 'apagar'].includes(f);

/** Novo estado do dente depois de usar a ferramenta numa posição. Devolve null se nada muda. */
export function aplicar(d: DenteEstado, f: Ferramenta, p: Posicao): DenteEstado | null {
  if (ehFerramentaFace(f)) {
    if (d.situacao === 'ausente' || d.situacao === 'implante') return null;
    const face = faceNaPosicao(d.numero, p);
    const faces = { ...d.faces };
    if (f === 'apagar' || faces[face] === f) delete faces[face]; // tocar de novo desmarca
    else faces[face] = f;
    return { ...d, faces };
  }
  if (f === 'higido') return { ...d, situacao: 'higido', faces: {} };
  const situacao: Situacao = d.situacao === f ? 'higido' : f;
  return { ...d, situacao, faces: situacao === 'ausente' || situacao === 'implante' ? {} : d.faces };
}

export const vazio = (numero: number): DenteEstado => ({ numero, situacao: 'higido', faces: {}, observacao: null });

/** Resumo para a lista: "16: canal; O cárie". */
export function resumo(d: DenteEstado): string {
  const partes: string[] = [];
  if (d.situacao !== 'higido') partes.push(FERRAMENTAS_DENTE.find((x) => x.id === d.situacao)!.rotulo.toLowerCase());
  for (const [face, e] of Object.entries(d.faces)) partes.push(`${face} ${FERRAMENTAS_FACE.find((x) => x.id === e)!.rotulo.toLowerCase()}`);
  return partes.join(', ');
}

/** Forma do dente para o odontograma anatômico: largura da coroa e quantas raízes. */
export function anatomia(n: number): { largura: number; raizes: number; raizLonga: boolean } {
  const pos = n % 10; // 1 incisivo central … 8 terceiro molar
  const deciduo = n > 50;
  const superior = ehSuperior(n);
  if (deciduo) {
    if (pos <= 2) return { largura: 22, raizes: 1, raizLonga: false };
    if (pos === 3) return { largura: 24, raizes: 1, raizLonga: true };
    return { largura: 32, raizes: superior ? 3 : 2, raizLonga: false };
  }
  if (pos <= 2) return { largura: pos === 1 ? 26 : 23, raizes: 1, raizLonga: false };
  if (pos === 3) return { largura: 26, raizes: 1, raizLonga: true };
  if (pos <= 5) return { largura: 28, raizes: superior && pos === 4 ? 2 : 1, raizLonga: false };
  return { largura: 36, raizes: superior ? 3 : 2, raizLonga: false };
}
