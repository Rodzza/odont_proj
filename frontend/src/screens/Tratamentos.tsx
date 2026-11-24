import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, type Tratamento } from '../lib/api';
import { Evolucao } from './Evolucao';

/** Aba "Tratamentos": o que falta fazer (dos orçamentos aprovados e avulsos) e, ao lado, as evoluções. */
export function Tratamentos({ pacienteId }: { pacienteId: number }) {
  const [vista, setVista] = useState<'tratamentos' | 'evolucoes'>('tratamentos');
  return (
    <div className="tratamentos">
      <div className="segmento" role="tablist" aria-label="Tratamentos ou evoluções">
        <button type="button" role="tab" aria-selected={vista === 'tratamentos'} onClick={() => setVista('tratamentos')}>
          Tratamentos
        </button>
        <button type="button" role="tab" aria-selected={vista === 'evolucoes'} onClick={() => setVista('evolucoes')}>
          Evoluções
        </button>
      </div>
      {vista === 'tratamentos' ? <ListaTratamentos pacienteId={pacienteId} /> : <Evolucao pacienteId={pacienteId} />}
    </div>
  );
}

function ListaTratamentos({ pacienteId }: { pacienteId: number }) {
  const [finalizados, setFinalizados] = useState(false);
  const [itens, setItens] = useState<Tratamento[] | null>(null);
  const [novo, setNovo] = useState(false);
  const [erro, setErro] = useState('');

  const carregar = useCallback(() => {
    api<Tratamento[]>(`/pacientes/${pacienteId}/tratamentos?finalizados=${finalizados}`).then(setItens).catch((e: Error) => setErro(e.message));
  }, [pacienteId, finalizados]);
  useEffect(carregar, [carregar]);

  const mudar = async (t: Tratamento, acao: 'finalizar' | 'reabrir') => {
    setErro('');
    try {
      await api(`/tratamentos/${t.id}/${acao}`, { method: 'POST' });
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  return (
    <>
      <div className="trat-topo">
        <h3 className="secao">{finalizados ? 'Tratamentos finalizados' : 'Lista de tratamentos'}</h3>
        <label className="interruptor">
          <input type="checkbox" role="switch" checked={finalizados} onChange={(e) => setFinalizados(e.target.checked)} />
          <span aria-hidden="true" />
          ver finalizados
        </label>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {itens?.length === 0 && (
        <p className="muted">{finalizados ? 'Nenhum tratamento finalizado ainda.' : 'Nada a fazer. Os itens de orçamentos aprovados aparecem aqui; você também pode adicionar um tratamento avulso.'}</p>
      )}
      <ul className="trat-lista">
        {itens?.map((t) => (
          <li key={t.id}>
            <div className="trat-info">
              <strong>
                {t.dente && <span className="trat-dente">{t.dente}</span>} {t.descricao}
              </strong>
              <span className="muted">{t.dentista}</span>
              {t.faces && (
                <span className="trat-faces">
                  Faces{' '}
                  {t.faces.split('').map((f) => (
                    <i key={f}>{f}</i>
                  ))}
                </span>
              )}
              {t.feito_em && <small className="muted">Finalizado em {new Date(t.feito_em).toLocaleDateString('pt-BR')}</small>}
              {!t.orcamento_id && <small className="muted">Sem orçamento</small>}
            </div>
            {t.feito ? (
              <button type="button" className="link" onClick={() => void mudar(t, 'reabrir')}>
                Reabrir
              </button>
            ) : (
              <button type="button" className="botao pequeno-botao" onClick={() => void mudar(t, 'finalizar')}>
                Finalizar
              </button>
            )}
          </li>
        ))}
      </ul>
      {!finalizados && (
        <button type="button" className="botao largo" onClick={() => setNovo(true)}>
          Adicionar tratamento
        </button>
      )}
      <p className="muted pequeno">Ao finalizar, o tratamento é anotado na evolução do paciente.</p>
      {novo && (
        <NovoTratamento
          pacienteId={pacienteId}
          onFechar={() => setNovo(false)}
          onSalvo={() => {
            setNovo(false);
            carregar();
          }}
        />
      )}
    </>
  );
}

function NovoTratamento({ pacienteId, onFechar, onSalvo }: { pacienteId: number; onFechar: () => void; onSalvo: () => void }) {
  const [descricao, setDescricao] = useState('');
  const [dente, setDente] = useState('');
  const [faces, setFaces] = useState('');
  const [erro, setErro] = useState('');
  const salvar = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/pacientes/${pacienteId}/tratamentos`, { method: 'POST', body: { descricao, dente: dente ? Number(dente) : null, faces: faces || null } });
      onSalvo();
    } catch (err) {
      setErro((err as Error).message);
    }
  };
  return (
    <div className="painel-fundo" onClick={onFechar}>
      <form className="painel" role="dialog" aria-label="Adicionar tratamento" onSubmit={salvar} onClick={(e) => e.stopPropagation()}>
        <header className="painel-topo">
          <h2>Adicionar tratamento</h2>
          <button type="button" className="fechar" aria-label="Fechar" onClick={onFechar}>
            ×
          </button>
        </header>
        <label className="campo">
          <span>Tratamento</span>
          <input required minLength={2} maxLength={160} value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="Ex.: Contenção fixa inferior" />
        </label>
        <div className="duas">
          <label className="campo">
            <span>Dente (opcional)</span>
            <input inputMode="numeric" value={dente} onChange={(e) => setDente(e.target.value.replace(/\D/g, '').slice(0, 2))} placeholder="21" />
          </label>
          <label className="campo">
            <span>Faces (opcional)</span>
            <input value={faces} onChange={(e) => setFaces(e.target.value.toUpperCase().replace(/[^VLMDO]/g, '').slice(0, 5))} placeholder="MV" />
          </label>
        </div>
        <p className="muted pequeno">Tratamento avulso não gera cobrança. Para cobrar, faça um orçamento.</p>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao">
          Adicionar
        </button>
      </form>
    </div>
  );
}
