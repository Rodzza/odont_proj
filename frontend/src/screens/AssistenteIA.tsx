import { useEffect, useState, type FormEvent } from 'react';
import { api, type AnaliseIA, type FonteIA, type MensagemIA, type RespostaChatIA, type ResumoIA, type Triagem } from '../lib/api';

const COR_ROTULO: Record<Triagem['cor'], string> = {
  vermelho: 'Vermelho · imediato',
  laranja: 'Laranja · hoje',
  amarelo: 'Amarelo · até 48 h',
  verde: 'Verde · rotina',
};

const AVISO = 'Sugestão da IA (Claude). Confira antes de decidir: a responsabilidade clínica é do dentista.';

/** Aba "Assistente IA" da ficha: resumo, triagem e chat com o prontuário. */
export function AssistenteIA({ pacienteId }: { pacienteId: number }) {
  const [ativa, setAtiva] = useState<boolean | null>(null);
  useEffect(() => {
    api<{ ativa: boolean }>('/ia/status')
      .then((s) => setAtiva(s.ativa))
      .catch(() => setAtiva(false));
  }, []);

  if (ativa === null) return <p className="muted">Carregando…</p>;
  if (!ativa)
    return (
      <p className="aviso">
        A IA está desligada. Para ligar, coloque a <code>ANTHROPIC_API_KEY</code> no arquivo <code>.env</code> do servidor e reinicie.
      </p>
    );
  return (
    <div className="ia">
      <p className="muted pequeno">{AVISO}</p>
      <ResumoBloco pacienteId={pacienteId} />
      <TriagemBloco pacienteId={pacienteId} />
      <ChatBloco pacienteId={pacienteId} />
    </div>
  );
}

function Fontes({ fontes }: { fontes: FonteIA[] }) {
  const [aberta, setAberta] = useState<string | null>(null);
  if (!fontes.length) return null;
  const vista = fontes.find((f) => f.id === aberta);
  return (
    <div className="ia-fontes">
      <span className="muted pequeno">Fontes:</span>
      {fontes.map((f) => (
        <button key={f.id} type="button" className="chip chip--fonte" aria-pressed={aberta === f.id} onClick={() => setAberta(aberta === f.id ? null : f.id)}>
          {f.titulo}
        </button>
      ))}
      {vista && <p className="obs ia-fonte-texto">{vista.texto}</p>}
    </div>
  );
}

function Lista({ titulo, itens }: { titulo: string; itens: string[] }) {
  if (!itens.length) return null;
  return (
    <>
      <h4 className="ia-sub">{titulo}</h4>
      <ul className="ia-lista">
        {itens.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </>
  );
}

function ResumoBloco({ pacienteId }: { pacienteId: number }) {
  const [r, setR] = useState<ResumoIA | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');

  const gerar = async () => {
    setErro('');
    setCarregando(true);
    try {
      setR(await api<ResumoIA>(`/ia/pacientes/${pacienteId}/resumo`, { method: 'POST' }));
    } catch (e) {
      setErro((e as Error).message);
    }
    setCarregando(false);
  };

  return (
    <section className="ia-cartao">
      <header className="ia-topo">
        <h3>Resumo do prontuário</h3>
        <button type="button" className="botao secundario" disabled={carregando} onClick={() => void gerar()}>
          {carregando ? 'Lendo o prontuário…' : r ? 'Gerar de novo' : 'Gerar resumo'}
        </button>
      </header>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {r && (
        <>
          <p>{r.resumo}</p>
          {r.alertas.length > 0 && (
            <ul className="ia-alertas">
              {r.alertas.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          )}
          <Lista titulo="Pendências" itens={r.pendencias} />
          <Lista titulo="Histórico" itens={r.historico} />
          <Fontes fontes={r.fontes_detalhe} />
        </>
      )}
    </section>
  );
}

export function CartaoTriagem({ t, quando }: { t: Triagem; quando?: string }) {
  return (
    <div className={`triagem triagem--${t.cor}`}>
      <strong className="triagem-cor">{COR_ROTULO[t.cor]}</strong>
      <span className="pequeno">Atender: {t.prazo}</span>
      <p>{t.motivo}</p>
      {t.sinais_de_alerta.length > 0 && <p className="pequeno">Sinais: {t.sinais_de_alerta.join('; ')}</p>}
      <p className="pequeno">
        <b>Dizer ao paciente:</b> {t.orientacao_paciente}
      </p>
      {quando && <span className="muted pequeno">{quando}</span>}
    </div>
  );
}

function TriagemBloco({ pacienteId }: { pacienteId: number }) {
  const [queixa, setQueixa] = useState('');
  const [hist, setHist] = useState<AnaliseIA<Triagem>[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');

  useEffect(() => {
    api<AnaliseIA<Triagem>[]>(`/ia/pacientes/${pacienteId}/analises?tipo=triagem`)
      .then(setHist)
      .catch(() => {});
  }, [pacienteId]);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErro('');
    setCarregando(true);
    try {
      const a = await api<AnaliseIA<Triagem>>(`/ia/pacientes/${pacienteId}/triagem`, { method: 'POST', body: { queixa } });
      setHist((h) => [a, ...h]);
      setQueixa('');
    } catch (err) {
      setErro((err as Error).message);
    }
    setCarregando(false);
  };

  return (
    <section className="ia-cartao">
      <header className="ia-topo">
        <h3>Triagem de urgência</h3>
      </header>
      <form onSubmit={(e) => void enviar(e)}>
        <label className="campo">
          <span>O que o paciente relatou?</span>
          <textarea
            rows={3}
            required
            minLength={3}
            maxLength={2000}
            value={queixa}
            onChange={(e) => setQueixa(e.target.value)}
            placeholder="Ex.: dor forte no dente de baixo desde ontem, rosto um pouco inchado, não melhora com dipirona"
          />
        </label>
        <button type="submit" className="botao" disabled={carregando || queixa.trim().length < 3}>
          {carregando ? 'Classificando…' : 'Classificar urgência'}
        </button>
      </form>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {hist.map((a) => (
        <div key={a.id} className="triagem-item">
          <p className="muted pequeno">“{a.entrada}”</p>
          <CartaoTriagem t={a.resultado} quando={new Date(a.criado_em).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })} />
        </div>
      ))}
    </section>
  );
}

interface Msg extends MensagemIA {
  fontes?: FonteIA[];
  semInfo?: boolean;
}

export function ChatBloco({ pacienteId }: { pacienteId: number }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [texto, setTexto] = useState('');
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const pergunta = texto.trim();
    if (!pergunta) return;
    setErro('');
    setCarregando(true);
    const historico = msgs.map(({ papel, texto: t }) => ({ papel, texto: t }));
    setMsgs((m) => [...m, { papel: 'user', texto: pergunta }]);
    setTexto('');
    try {
      const r = await api<RespostaChatIA>(`/ia/pacientes/${pacienteId}/chat`, { method: 'POST', body: { pergunta, historico } });
      setMsgs((m) => [...m, { papel: 'assistant', texto: r.resposta, fontes: r.fontes_detalhe, semInfo: r.sem_informacao }]);
    } catch (err) {
      setErro((err as Error).message);
    }
    setCarregando(false);
  };

  return (
    <section className="ia-cartao">
      <header className="ia-topo">
        <h3>Perguntar ao prontuário</h3>
      </header>
      <div className="chat" aria-live="polite">
        {msgs.length === 0 && <p className="muted pequeno">Ex.: “Ela tem alergia a algum anestésico?”, “O que já foi feito no 36?”, “Tem algo pendente?”</p>}
        {msgs.map((m, i) => (
          <div key={i} className={`bolha bolha--${m.papel}`}>
            <p>{m.texto}</p>
            {m.semInfo && <span className="pequeno muted">O prontuário não tem essa informação.</span>}
            {m.fontes && <Fontes fontes={m.fontes} />}
          </div>
        ))}
        {carregando && <div className="bolha bolha--assistant muted">Consultando o prontuário…</div>}
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      <form className="chat-envio" onSubmit={(e) => void enviar(e)}>
        <input className="busca" value={texto} maxLength={2000} onChange={(e) => setTexto(e.target.value)} placeholder="Escreva sua pergunta" aria-label="Pergunta" />
        <button type="submit" className="botao" disabled={carregando || !texto.trim()}>
          Enviar
        </button>
      </form>
    </section>
  );
}
