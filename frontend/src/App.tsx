import { useEffect, useState } from 'react';
import { lerSessao, quandoSessaoExpirar, salvarSessao, type Sessao } from './lib/api';
import { Agenda } from './screens/Agenda';
import { Login } from './screens/Login';
import { Pacientes } from './screens/Pacientes';

export const APP_NOME = 'OdontoNotes';

type Aba = 'agenda' | 'pacientes';

export function App() {
  const [sessao, setSessao] = useState<Sessao | null>(lerSessao);
  const [aba, setAba] = useState<Aba>('agenda');
  const [aviso, setAviso] = useState('');

  useEffect(() => {
    quandoSessaoExpirar(() => {
      setSessao(null);
      setAviso('Sua sessão expirou. Entre de novo.');
    });
  }, []);

  if (!sessao) {
    return (
      <Login
        aviso={aviso}
        onEntrar={(s) => {
          salvarSessao(s);
          setSessao(s);
          setAviso('');
        }}
      />
    );
  }

  const sair = () => {
    salvarSessao(null);
    setSessao(null);
  };

  return (
    <div className="shell">
      <nav className="rail" aria-label="Menu principal">
        <div className="marca">
          <span className="marca-dente" aria-hidden="true" />
          <span>{APP_NOME}</span>
        </div>
        <button type="button" className="rail-item" aria-current={aba === 'agenda' ? 'page' : undefined} onClick={() => setAba('agenda')}>
          <IconeAgenda />
          <span>Agenda</span>
        </button>
        <button type="button" className="rail-item" aria-current={aba === 'pacientes' ? 'page' : undefined} onClick={() => setAba('pacientes')}>
          <IconePacientes />
          <span>Pacientes</span>
        </button>
        <div className="rail-rodape">
          <span className="rail-quem">
            {sessao.nome}
            <small>{sessao.clinica}</small>
          </span>
          <button type="button" className="link" onClick={sair}>
            Sair
          </button>
        </div>
      </nav>
      <main className="conteudo">{aba === 'agenda' ? <Agenda clinica={sessao.clinica} /> : <Pacientes />}</main>
    </div>
  );
}

function IconeAgenda() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <rect x="3.5" y="5" width="17" height="15" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3.5 10h17M8 3v4M16 3v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
function IconePacientes() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <circle cx="12" cy="8.5" r="3.8" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4.5 20c1.2-3.8 4-5.5 7.5-5.5s6.3 1.7 7.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
