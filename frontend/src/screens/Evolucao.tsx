import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api } from '../lib/api';

interface Entrada {
  id: number;
  texto: string;
  dentes: number[];
  retifica_id: number | null;
  retificada_por: number | null;
  autor: string;
  criado_em: string;
}

const quando = (iso: string) => new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

export function Evolucao({ pacienteId }: { pacienteId: number }) {
  const [itens, setItens] = useState<Entrada[] | null>(null);
  const [texto, setTexto] = useState('');
  const [dentes, setDentes] = useState('');
  const [retificando, setRetificando] = useState<Entrada | null>(null);
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(() => {
    api<Entrada[]>(`/pacientes/${pacienteId}/evolucoes`).then(setItens).catch((e: Error) => setErro(e.message));
  }, [pacienteId]);
  useEffect(carregar, [carregar]);

  const salvar = async (e: FormEvent) => {
    e.preventDefault();
    setErro('');
    setSalvando(true);
    const nums = dentes.split(/[\s,;]+/).filter(Boolean).map(Number);
    try {
      await api(`/pacientes/${pacienteId}/evolucoes`, { method: 'POST', body: { texto, dentes: nums, retifica_id: retificando?.id ?? null } });
      setTexto('');
      setDentes('');
      setRetificando(null);
      carregar();
    } catch (err) {
      setErro((err as Error).message);
    }
    setSalvando(false);
  };

  return (
    <div className="evolucao">
      <form className="evo-form" onSubmit={salvar}>
        {retificando && (
          <div className="aviso">
            Retificando a anotação de {quando(retificando.criado_em)}. A original continua no prontuário, marcada como retificada.{' '}
            <button type="button" className="link" onClick={() => setRetificando(null)}>
              Cancelar
            </button>
          </div>
        )}
        <label className="campo">
          <span>{retificando ? 'Correção' : 'Nova anotação do atendimento'}</span>
          <textarea rows={4} maxLength={10000} required value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Procedimento realizado, materiais, orientações…" />
        </label>
        <label className="campo curto">
          <span>Dentes (opcional)</span>
          <input value={dentes} onChange={(e) => setDentes(e.target.value)} placeholder="16, 17" inputMode="numeric" />
        </label>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao" disabled={salvando || texto.trim().length < 3}>
          {salvando ? 'Registrando…' : retificando ? 'Registrar correção' : 'Registrar no prontuário'}
        </button>
        <p className="muted pequeno">Anotações não podem ser editadas nem apagadas. Se algo estiver errado, registre uma correção.</p>
      </form>

      {itens && itens.length === 0 && <p className="muted">Nenhuma anotação ainda.</p>}
      <ol className="linha-tempo">
        {itens?.map((e) => (
          <li key={e.id} className={`${e.retificada_por ? 'retificada' : ''} ${e.retifica_id ? 'correcao' : ''}`}>
            <div className="lt-cabeca">
              <time dateTime={e.criado_em}>{quando(e.criado_em)}</time>
              <span className="muted">{e.autor}</span>
              {e.dentes.length > 0 && <span className="lt-dentes">Dentes {e.dentes.join(', ')}</span>}
            </div>
            {e.retifica_id && <p className="lt-etiqueta">Correção de uma anotação anterior</p>}
            <p className="lt-texto">{e.texto}</p>
            {e.retificada_por ? (
              <p className="lt-etiqueta">Retificada por uma anotação posterior</p>
            ) : (
              <button type="button" className="link pequeno" onClick={() => setRetificando(e)}>
                Corrigir esta anotação
              </button>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
