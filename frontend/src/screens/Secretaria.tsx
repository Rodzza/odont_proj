import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, type MensagemIA } from '../lib/api';

/** Secretária com IA: marca consultas na agenda do DentFlow conversando. */
export function Secretaria() {
  const [msgs, setMsgs] = useState<MensagemIA[]>([]);
  const [texto, setTexto] = useState('');
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');
  const [marcadas, setMarcadas] = useState(0);
  const [ativa, setAtiva] = useState<boolean | null>(null);
  const fimRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<{ ativa: boolean }>('/ia/status')
      .then((s) => setAtiva(s.ativa))
      .catch(() => setAtiva(false));
  }, []);
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
      <div className="topo">
        <div>
          <h1 className="dia-titulo">Secretária</h1>
          <p className="resumo">Peça para ver a agenda ou marcar consultas. Ela confirma com você antes de marcar.</p>
        </div>
        {marcadas > 0 && <span className="aviso pequeno">{marcadas === 1 ? '1 consulta marcada' : `${marcadas} consultas marcadas`} — veja na Agenda</span>}
      </div>
      {ativa === false && (
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
        <input className="busca" value={texto} maxLength={2000} onChange={(e) => setTexto(e.target.value)} placeholder="Escreva para a secretária" aria-label="Mensagem" disabled={ativa === false} />
        <button type="submit" className="botao" disabled={carregando || !texto.trim() || ativa === false}>
          Enviar
        </button>
      </form>
    </div>
  );
}
