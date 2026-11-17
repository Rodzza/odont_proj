import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import {
  ARCADAS,
  FERRAMENTAS_DENTE,
  FERRAMENTAS_FACE,
  NOME_FACE,
  aplicar,
  ehAnterior,
  ehSuperior,
  faceNaPosicao,
  resumo,
  vazio,
  type DenteEstado,
  type Ferramenta,
  type Posicao,
} from '../lib/odontograma';

const T = 40; // tamanho do dente no desenho
const I = 14; // margem até a face central

/** Polígono de cada posição dentro do quadrado do dente (estilo cruz do odontograma). */
const POLIGONOS: Record<Exclude<Posicao, 'centro'>, string> = {
  cima: `0,0 ${T},0 ${T - I},${I} ${I},${I}`,
  baixo: `0,${T} ${T},${T} ${T - I},${T - I} ${I},${T - I}`,
  esquerda: `0,0 ${I},${I} ${I},${T - I} 0,${T}`,
  direita: `${T},0 ${T},${T} ${T - I},${T - I} ${T - I},${I}`,
};

function DenteSvg({ d, selecionado, onToque }: { d: DenteEstado; selecionado: boolean; onToque: (p: Posicao) => void }) {
  const sup = ehSuperior(d.numero);
  const semFaces = d.situacao === 'ausente' || d.situacao === 'implante';
  const face = (p: Posicao) => d.faces[faceNaPosicao(d.numero, p)];
  const rotuloFace = (p: Posicao) => {
    const f = faceNaPosicao(d.numero, p);
    const nome = f === 'O' ? (ehAnterior(d.numero) ? 'incisal' : 'oclusal') : NOME_FACE[f];
    return `Dente ${d.numero}, face ${nome}${d.faces[f] ? `: ${d.faces[f]}` : ''}`;
  };

  return (
    <g className={`dente dente--${d.situacao}${selecionado ? ' dente--sel' : ''}`}>
      <text className="dente-num" x={T / 2} y={sup ? -8 : T + 18} textAnchor="middle">
        {d.numero}
      </text>
      {(Object.keys(POLIGONOS) as Exclude<Posicao, 'centro'>[]).map((p) => (
        <polygon
          key={p}
          points={POLIGONOS[p]}
          className={`face ${face(p) ? `face--${face(p)}` : ''}`}
          role="button"
          tabIndex={semFaces ? -1 : 0}
          aria-label={rotuloFace(p)}
          onClick={() => onToque(p)}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onToque(p))}
        />
      ))}
      <rect
        x={I}
        y={I}
        width={T - 2 * I}
        height={T - 2 * I}
        className={`face ${face('centro') ? `face--${face('centro')}` : ''}`}
        role="button"
        tabIndex={semFaces ? -1 : 0}
        aria-label={rotuloFace('centro')}
        onClick={() => onToque('centro')}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onToque('centro'))}
      />
      {/* Marcas da situação do dente inteiro */}
      {d.situacao === 'ausente' && <path className="dmarca dmarca--ausente" d={`M3 3L${T - 3} ${T - 3}M${T - 3} 3L3 ${T - 3}`} />}
      {d.situacao === 'extrair' && <path className="dmarca dmarca--extrair" d={`M3 3L${T - 3} ${T - 3}M${T - 3} 3L3 ${T - 3}`} />}
      {d.situacao === 'canal' && <path className="dmarca dmarca--canal" d={`M${T / 2} ${sup ? T + 2 : -2}V${T / 2}`} />}
      {d.situacao === 'coroa' && <circle className="dmarca dmarca--coroa" cx={T / 2} cy={T / 2} r={T / 2 + 2} />}
      {d.situacao === 'implante' && <path className="dmarca dmarca--implante" d={`M${T / 2 - 6} 8H${T / 2 + 6}M${T / 2 - 8} 16H${T / 2 + 8}M${T / 2 - 8} 24H${T / 2 + 8}M${T / 2 - 6} 32H${T / 2 + 6}M${T / 2} 6V34`} />}
      {d.situacao === 'protese' && <path className="dmarca dmarca--protese" d={`M-2 ${T / 2}H${T + 2}`} />}
    </g>
  );
}

export function Odontograma({ pacienteId }: { pacienteId: number }) {
  const [dentes, setDentes] = useState<Map<number, DenteEstado>>(new Map());
  const [tipo, setTipo] = useState<'permanente' | 'deciduo'>('permanente');
  const [ferramenta, setFerramenta] = useState<Ferramenta>('carie');
  const [selecionado, setSelecionado] = useState<number | null>(null);
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(0);

  useEffect(() => {
    api<DenteEstado[]>(`/pacientes/${pacienteId}/odontograma`)
      .then((l) => {
        setDentes(new Map(l.map((d) => [d.numero, d])));
        if (l.length && l.every((d) => d.numero > 50)) setTipo('deciduo');
      })
      .catch((e: Error) => setErro(e.message));
  }, [pacienteId]);

  const estado = (n: number) => dentes.get(n) ?? vazio(n);

  const salvar = async (novo: DenteEstado) => {
    const antes = dentes.get(novo.numero);
    setDentes((m) => new Map(m).set(novo.numero, novo)); // mostra na hora
    setSalvando((n) => n + 1);
    try {
      await api(`/pacientes/${pacienteId}/odontograma/${novo.numero}`, {
        method: 'PUT',
        body: { situacao: novo.situacao, faces: novo.faces, observacao: novo.observacao },
      });
      setErro('');
    } catch (e) {
      setDentes((m) => {
        const c = new Map(m);
        if (antes) c.set(novo.numero, antes);
        else c.delete(novo.numero);
        return c;
      });
      setErro(`Não salvou o dente ${novo.numero}: ${(e as Error).message}`);
    }
    setSalvando((n) => n - 1);
  };

  const tocar = (n: number, p: Posicao) => {
    setSelecionado(n);
    const novo = aplicar(estado(n), ferramenta, p);
    if (novo) void salvar(novo);
  };

  const arcada = ARCADAS[tipo];
  const larguraLado = arcada.superior[0].length * (T + 6);
  const largura = larguraLado * 2 + 18;
  const linha = (numeros: readonly number[], x0: number, y: number) =>
    numeros.map((n, i) => (
      <g key={n} transform={`translate(${x0 + i * (T + 6)}, ${y})`}>
        <DenteSvg d={estado(n)} selecionado={selecionado === n} onToque={(p) => tocar(n, p)} />
      </g>
    ));

  const sel = selecionado ? estado(selecionado) : null;
  const marcados = [...dentes.values()].filter((d) => d.situacao !== 'higido' || Object.keys(d.faces).length).sort((a, b) => a.numero - b.numero);

  return (
    <div className="odonto">
      <div className="odonto-topo">
        <div className="chips" role="group" aria-label="Dentição">
          <button type="button" className="chip" aria-pressed={tipo === 'permanente'} onClick={() => setTipo('permanente')}>
            Permanente
          </button>
          <button type="button" className="chip" aria-pressed={tipo === 'deciduo'} onClick={() => setTipo('deciduo')}>
            Decídua (de leite)
          </button>
        </div>
        <span className="muted pequeno" aria-live="polite">
          {salvando ? 'Salvando…' : 'Salvo automaticamente'}
        </span>
      </div>

      <div className="ferramentas" role="radiogroup" aria-label="Ferramenta">
        <span className="ferr-grupo">Faces</span>
        {FERRAMENTAS_FACE.map((f) => (
          <button key={f.id} type="button" role="radio" aria-checked={ferramenta === f.id} className={`ferr ferr--${f.id}`} onClick={() => setFerramenta(f.id)}>
            <i aria-hidden="true" />
            {f.rotulo}
          </button>
        ))}
        <span className="ferr-grupo">Dente inteiro</span>
        {FERRAMENTAS_DENTE.map((f) => (
          <button key={f.id} type="button" role="radio" aria-checked={ferramenta === f.id} className={`ferr ferr--${f.id}`} onClick={() => setFerramenta(f.id)}>
            <i aria-hidden="true" />
            {f.rotulo}
          </button>
        ))}
      </div>

      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      <div className="odonto-rolagem">
        <svg className="odonto-svg" viewBox={`-6 -30 ${largura + 12} ${2 * T + 104}`} style={{ minWidth: largura * 0.92 }} aria-label={`Odontograma ${tipo === 'permanente' ? 'permanente' : 'decíduo'}`}>
          <line className="linha-media" x1={larguraLado + 6} y1={-26} x2={larguraLado + 6} y2={2 * T + 70} />
          <line className="linha-media" x1={-4} y1={T + 22} x2={largura + 6} y2={T + 22} />
          {linha(arcada.superior[0], 0, 0)}
          {linha(arcada.superior[1], larguraLado + 18, 0)}
          {linha(arcada.inferior[0], 0, T + 44)}
          {linha(arcada.inferior[1], larguraLado + 18, T + 44)}
        </svg>
      </div>
      <p className="muted pequeno">Escolha a ferramenta e toque na face ou no dente. Tocar de novo com a mesma ferramenta desfaz.</p>

      {sel && (
        <div className="dente-detalhe">
          <strong>Dente {sel.numero}</strong>
          <span className="muted">{resumo(sel) || 'Hígido'}</span>
          <label className="campo">
            <span>Observação do dente</span>
            <input
              key={sel.numero}
              defaultValue={sel.observacao ?? ''}
              maxLength={500}
              placeholder="Ex.: mobilidade grau 1"
              onBlur={(e) => {
                const obs = e.target.value.trim() || null;
                if (obs !== sel.observacao) void salvar({ ...sel, observacao: obs });
              }}
            />
          </label>
        </div>
      )}

      {marcados.length > 0 && (
        <>
          <h3 className="secao">Situação registrada</h3>
          <ul className="odonto-lista">
            {marcados.map((d) => (
              <li key={d.numero}>
                <button type="button" className="link" onClick={() => setSelecionado(d.numero)}>
                  {d.numero}
                </button>
                <span>{resumo(d)}</span>
                {d.observacao && <span className="muted">{d.observacao}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
