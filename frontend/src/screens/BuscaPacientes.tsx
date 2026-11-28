import { useState, type FormEvent } from 'react';
import { api, type BuscaIA } from '../lib/api';

/** Busca por significado entre todos os pacientes (pgvector + Claude). */
export function BuscaPacientes({ ativa }: { ativa: boolean }) {
  const [pergunta, setPergunta] = useState('');
  const [r, setR] = useState<BuscaIA | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');
  const [aviso, setAviso] = useState('');
  const [verTrechos, setVerTrechos] = useState(false);

  const buscar = async (e: FormEvent) => {
    e.preventDefault();
    setErro('');
    setCarregando(true);
    try {
      setR(await api<BuscaIA>('/ia/busca', { method: 'POST', body: { pergunta } }));
      setVerTrechos(false);
    } catch (err) {
      setErro((err as Error).message);
    }
    setCarregando(false);
  };

  const reindexar = async () => {
    setErro('');
    setAviso('Reindexando…');
    try {
      const { indexados } = await api<{ indexados: number }>('/ia/reindexar', { method: 'POST' });
      setAviso(`${indexados} registros indexados.`);
    } catch (err) {
      setAviso('');
      setErro((err as Error).message);
    }
  };

  if (!ativa)
    return (
      <p className="aviso">
        A busca entre pacientes está desligada. Coloque a <code>VOYAGE_API_KEY</code> no <code>.env</code> do servidor.
      </p>
    );

  return (
    <div className="ia">
      <form className="chat-envio" onSubmit={(e) => void buscar(e)}>
        <input
          className="busca"
          value={pergunta}
          minLength={3}
          maxLength={500}
          onChange={(e) => setPergunta(e.target.value)}
          placeholder="Ex.: quem teve reação à articaína? pacientes com canal pendente no 36?"
          aria-label="Pergunta sobre os pacientes"
        />
        <button type="submit" className="botao" disabled={carregando || pergunta.trim().length < 3}>
          {carregando ? 'Buscando…' : 'Buscar'}
        </button>
      </form>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {r && (
        <section className="ia-cartao">
          <p>{r.resposta}</p>
          {r.pacientes.length > 0 && (
            <ul className="ia-lista">
              {r.pacientes.map((p) => (
                <li key={p.paciente_id}>
                  <b>{p.nome}</b> — {p.motivo}
                </li>
              ))}
            </ul>
          )}
          <p className="muted pequeno">A busca pode não achar todos os casos. Confira no prontuário de cada paciente.</p>
          {r.trechos.length > 0 && (
            <button type="button" className="link" onClick={() => setVerTrechos(!verTrechos)}>
              {verTrechos ? 'Esconder trechos encontrados' : `Ver os ${r.trechos.length} trechos encontrados`}
            </button>
          )}
          {verTrechos &&
            r.trechos.map((t) => (
              <p key={t.id} className="obs pequeno">
                <b>
                  {t.paciente_nome} · {t.origem} · {Math.round(t.similaridade * 100)}%
                </b>
                {'\n'}
                {t.texto}
              </p>
            ))}
        </section>
      )}
      <p className="muted pequeno">
        Anamneses, evoluções e leituras de anexo entram na busca quando são salvas.{' '}
        <button type="button" className="link" onClick={() => void reindexar()}>
          Reindexar tudo
        </button>{' '}
        {aviso}
      </p>
    </div>
  );
}
