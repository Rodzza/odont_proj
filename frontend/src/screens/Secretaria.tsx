import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, type MensagemIA } from '../lib/api';
import { BuscaPacientes } from './BuscaPacientes';

/** Menu "Assistente": secretária (agenda) e busca entre pacientes. */
export function Assistente() {
  const [aba, setAba] = useState<'secretaria' | 'busca'>('secretaria');
  const [status, setStatus] = useState<{ ativa: boolean; busca: boolean } | null>(null);
  useEffect(() => {
    api<{ ativa: boolean; busca: boolean }>('/ia/status')
      .then(setStatus)
      .catch(() => setStatus({ ativa: false, busca: false }));
  }, []);
  return (
    <div>
      <div className="topo">
        <div>
          <h1 className="dia-titulo">Assistente</h1>
          <p className="resumo">{aba === 'secretaria' ? 'Peça para ver a agenda ou marcar consultas. Ela confirma com você antes de marcar.' : 'Pergunte sobre todos os pacientes de uma vez.'}</p>
        </div>
      </div>
      <div className="abas" role="tablist" aria-label="Assistente">
        <button type="button" role="tab" className="aba" aria-selected={aba === 'secretaria'} onClick={() => setAba('secretaria')}>
          Secretária
        </button>
        <button type="button" role="tab" className="aba" aria-selected={aba === 'busca'} onClick={() => setAba('busca')}>
          Busca entre pacientes
        </button>
      </div>
      {status === null && <p className="muted">Carregando…</p>}
      {status && aba === 'secretaria' && <Secretaria ativa={status.ativa} />}
      {status && aba === 'busca' && <BuscaPacientes ativa={status.ativa && status.busca} />}
    </div>
  );
}

function Secretaria({ ativa }: { ativa: boolean }) {
  const [msgs, setMsgs] = useState<MensagemIA[]>([]);
  const [texto, setTexto] = useState('');
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');
  const [marcadas, setMarcadas] = useState(0);
  const fimRef = useRef<HTMLDivElement>(null);

  useEffect(() => fimRef.current?.scrollIntoView?.({ block: 'end' }), [msgs, carregando]);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const mensagem = texto.trim();
    if (!mensagem) return;
    setErro('');
    setCarregando(true);
    const historico = msgs;
    setMsgs((m) => [...m, { papel: 'user', texto: mensagem }]);
    setTexto('');
    try {
      const r = await api<{ resposta: string; consultas_marcadas: number[] }>('/ia/secretaria', { method: 'POST', body: { mensagem, historico } });
      setMsgs((m) => [...m, { papel: 'assistant', texto: r.resposta }]);
      setMarcadas((n) => n + r.consultas_marcadas.length);
    } catch (err) {
      setErro((err as Error).message);
    }
    setCarregando(false);
  };

  return (
    <div className="secretaria">
      {marcadas > 0 && <p className="aviso pequeno">{marcadas === 1 ? '1 consulta marcada' : `${marcadas} consultas marcadas`} — veja na Agenda</p>}
      {!ativa && (
        <p className="aviso">
          A IA está desligada. Coloque a <code>ANTHROPIC_API_KEY</code> no <code>.env</code> do servidor.
        </p>
      )}
      <div className="chat chat--alto" aria-live="polite">
        {msgs.length === 0 && (
          <p className="muted">Ex.: “Quais horários livres tem na quinta à tarde?”, “Marca a Maria Silva sexta às 14h para limpeza.”</p>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`bolha bolha--${m.papel}`}>
            <p>{m.texto}</p>
          </div>
        ))}
        {carregando && <div className="bolha bolha--assistant muted">Olhando a agenda…</div>}
        <div ref={fimRef} />
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      <form className="chat-envio" onSubmit={(e) => void enviar(e)}>
        <input className="busca" value={texto} maxLength={2000} onChange={(e) => setTexto(e.target.value)} placeholder="Escreva para a secretária" aria-label="Mensagem" disabled={!ativa} />
        <button type="submit" className="botao" disabled={carregando || !texto.trim() || !ativa}>
          Enviar
        </button>
      </form>
    </div>
  );
}
