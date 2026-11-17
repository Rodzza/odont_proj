import { useState, type FormEvent } from 'react';
import { api, type Sessao } from '../lib/api';

export function Login({ onEntrar, aviso }: { onEntrar: (s: Sessao) => void; aviso?: string }) {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  const entrar = async (e: FormEvent) => {
    e.preventDefault();
    setErro('');
    setEnviando(true);
    try {
      onEntrar(await api<Sessao>('/auth/login', { method: 'POST', body: { email, senha } }));
    } catch (err) {
      setErro((err as Error).message);
    }
    setEnviando(false);
  };

  return (
    <div className="login">
      <form className="login-cartao" onSubmit={entrar} noValidate>
        <span className="marca-dente grande" aria-hidden="true" />
        <h1>Entrar no consultório</h1>
        {aviso && <p className="aviso">{aviso}</p>}
        <label className="campo">
          <span>E-mail</span>
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="campo">
          <span>Senha</span>
          <input type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
        </label>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao" disabled={enviando || !email || !senha}>
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
