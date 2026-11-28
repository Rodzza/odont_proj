import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, type Consulta, type Paciente, type PacienteIn, type PacienteResumo } from '../lib/api';
import { STATUS, cpf, hora, idade, isoDia, somaDias, telefone } from '../lib/formato';
import { Anamnese, type AnamneseDados } from './Anamnese';
import { Anexos } from './Anexos';
import { AssistenteIA } from './AssistenteIA';
import { ConsultaForm } from './ConsultaForm';
import { Odontograma } from './Odontograma';
import { Orcamentos } from './Orcamentos';
import { Tratamentos } from './Tratamentos';

type AbaFicha = 'dados' | 'anamnese' | 'odontograma' | 'orcamentos' | 'tratamentos' | 'anexos' | 'ia';
const ABAS: { id: AbaFicha; rotulo: string }[] = [
  { id: 'dados', rotulo: 'Dados' },
  { id: 'anamnese', rotulo: 'Anamnese' },
  { id: 'odontograma', rotulo: 'Odontograma' },
  { id: 'orcamentos', rotulo: 'Orçamentos' },
  { id: 'tratamentos', rotulo: 'Tratamentos' },
  { id: 'anexos', rotulo: 'Anexos' },
  { id: 'ia', rotulo: 'Assistente IA' },
];

type Tela = { tipo: 'lista' } | { tipo: 'novo' } | { tipo: 'ficha'; id: number } | { tipo: 'editar'; paciente: Paciente };

export function Pacientes() {
  const [tela, setTela] = useState<Tela>({ tipo: 'lista' });
  if (tela.tipo === 'novo') return <PacienteForm onCancelar={() => setTela({ tipo: 'lista' })} onSalvo={(p) => setTela({ tipo: 'ficha', id: p.id })} />;
  if (tela.tipo === 'editar')
    return <PacienteForm paciente={tela.paciente} onCancelar={() => setTela({ tipo: 'ficha', id: tela.paciente.id })} onSalvo={(p) => setTela({ tipo: 'ficha', id: p.id })} />;
  if (tela.tipo === 'ficha') return <Ficha id={tela.id} onVoltar={() => setTela({ tipo: 'lista' })} onEditar={(p) => setTela({ tipo: 'editar', paciente: p })} />;
  return <Lista onNovo={() => setTela({ tipo: 'novo' })} onAbrir={(id) => setTela({ tipo: 'ficha', id })} />;
}

function Lista({ onNovo, onAbrir }: { onNovo: () => void; onAbrir: (id: number) => void }) {
  const [busca, setBusca] = useState('');
  const [arquivados, setArquivados] = useState(false);
  const [lista, setLista] = useState<PacienteResumo[] | null>(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    const t = setTimeout(() => {
      api<PacienteResumo[]>(`/pacientes?busca=${encodeURIComponent(busca.trim())}&arquivados=${arquivados}&limite=200`)
        .then((l) => {
          setLista(l);
          setErro('');
        })
        .catch((e: Error) => setErro(e.message));
    }, 200);
    return () => clearTimeout(t);
  }, [busca, arquivados]);

  return (
    <div>
      <header className="topo">
        <h1 className="dia-titulo">Pacientes</h1>
        <button type="button" className="botao" onClick={onNovo}>
          Cadastrar paciente
        </button>
      </header>
      <div className="filtros">
        <input type="search" className="busca" placeholder="Buscar por nome, CPF ou telefone" aria-label="Buscar paciente" value={busca} onChange={(e) => setBusca(e.target.value)} />
        <label className="alternar">
          <input type="checkbox" checked={arquivados} onChange={(e) => setArquivados(e.target.checked)} /> Ver arquivados
        </label>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {lista && lista.length === 0 && (
        <div className="vazio">
          {busca ? (
            <p>Nenhum paciente encontrado para “{busca}”.</p>
          ) : arquivados ? (
            <p>Nenhum paciente arquivado.</p>
          ) : (
            <>
              <p>Nenhum paciente cadastrado ainda.</p>
              <button type="button" className="botao" onClick={onNovo}>
                Cadastrar o primeiro paciente
              </button>
            </>
          )}
        </div>
      )}
      <ul className="lista-pacientes">
        {lista?.map((p) => {
          const anos = idade(p.nascimento);
          return (
            <li key={p.id}>
              <button type="button" onClick={() => onAbrir(p.id)}>
                <span className="iniciais" aria-hidden="true">
                  {p.nome
                    .split(' ')
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((s) => s[0])
                    .join('')
                    .toUpperCase()}
                </span>
                <span className="lp-nome">{p.nome}</span>
                <span className="lp-info">
                  {anos !== null ? `${anos} anos` : ''}
                  {anos !== null && p.telefone ? ', ' : ''}
                  {telefone(p.telefone)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Ficha({ id, onVoltar, onEditar }: { id: number; onVoltar: () => void; onEditar: (p: Paciente) => void }) {
  const [p, setP] = useState<Paciente | null>(null);
  const [consultas, setConsultas] = useState<Consulta[]>([]);
  const [erro, setErro] = useState('');
  const [marcando, setMarcando] = useState(false);
  const [aba, setAba] = useState<AbaFicha>('dados');
  const [alertas, setAlertas] = useState<string[]>([]);

  const carregar = useCallback(async () => {
    try {
      const hoje = new Date();
      const [pac, cons, anam] = await Promise.all([
        api<Paciente>(`/pacientes/${id}`),
        api<Consulta[]>(`/consultas?de=${isoDia(somaDias(hoje, -31))}&ate=${isoDia(somaDias(hoje, 31))}&paciente_id=${id}`),
        api<AnamneseDados>(`/pacientes/${id}/anamnese`),
      ]);
      setP(pac);
      setConsultas(cons);
      setAlertas(anam.alertas ?? []);
    } catch (e) {
      setErro((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const arquivar = async () => {
    if (!p) return;
    try {
      setP(await api<Paciente>(`/pacientes/${p.id}/arquivar?arquivar=${!p.arquivado}`, { method: 'POST' }));
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  if (erro) return <p className="erro">{erro}</p>;
  if (!p) return <p className="muted">Carregando…</p>;
  const anos = idade(p.nascimento);
  const agora = new Date().toISOString().slice(0, 16);
  const proximas = consultas.filter((c) => c.inicio >= agora);
  const passadas = consultas.filter((c) => c.inicio < agora).reverse();

  const Linha = ({ c }: { c: Consulta }) => (
    <li className={`hist hist--${c.status}`}>
      <span>
        {new Date(`${c.inicio.slice(0, 10)}T12:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}, {hora(c.inicio)}
      </span>
      <span>{c.procedimento ?? 'Consulta'}</span>
      <span className="hist-status">{STATUS[c.status].rotulo}</span>
    </li>
  );

  return (
    <div className="ficha">
      <button type="button" className="link voltar" onClick={onVoltar}>
        ‹ Pacientes
      </button>
      <header className="topo">
        <div>
          <h1 className="dia-titulo">{p.nome}</h1>
          <p className="resumo">
            {anos !== null ? `${anos} anos` : 'Idade não informada'}
            {p.arquivado ? ', arquivado' : ''}
          </p>
        </div>
        {!p.arquivado && (
          <button type="button" className="botao" onClick={() => setMarcando(true)}>
            Marcar consulta
          </button>
        )}
      </header>

      {alertas.length > 0 && (
        <div className="alertas" role="note" aria-label="Atenção antes de atender">
          <strong>Atenção</strong>
          <ul>
            {alertas.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="abas" role="tablist" aria-label="Prontuário">
        {ABAS.map((a) => (
          <button key={a.id} type="button" role="tab" aria-selected={aba === a.id} className="aba" onClick={() => setAba(a.id)}>
            {a.rotulo}
          </button>
        ))}
      </div>

      {aba === 'anamnese' && <Anamnese pacienteId={p.id} onSalvo={(a) => setAlertas(a.alertas ?? [])} />}
      {aba === 'odontograma' && <Odontograma pacienteId={p.id} />}
      {aba === 'orcamentos' && <Orcamentos pacienteId={p.id} />}
      {aba === 'tratamentos' && <Tratamentos pacienteId={p.id} />}
      {aba === 'anexos' && <Anexos pacienteId={p.id} />}
      {aba === 'ia' && <AssistenteIA pacienteId={p.id} />}

      {aba === 'dados' && (
      <>
      <dl className="dados">
        <div>
          <dt>Telefone</dt>
          <dd>{telefone(p.telefone) || '—'}</dd>
        </div>
        <div>
          <dt>CPF</dt>
          <dd>{cpf(p.cpf) || '—'}</dd>
        </div>
        <div>
          <dt>Nascimento</dt>
          <dd>{p.nascimento ? new Date(`${p.nascimento}T12:00`).toLocaleDateString('pt-BR') : '—'}</dd>
        </div>
        <div>
          <dt>E-mail</dt>
          <dd>{p.email || '—'}</dd>
        </div>
        <div className="largo">
          <dt>Endereço</dt>
          <dd>{p.endereco || '—'}</dd>
        </div>
        {p.responsavel && (
          <div className="largo">
            <dt>Responsável</dt>
            <dd>{p.responsavel}</dd>
          </div>
        )}
        {p.observacoes && (
          <div className="largo">
            <dt>Observações</dt>
            <dd className="obs">{p.observacoes}</dd>
          </div>
        )}
      </dl>

      <h2 className="secao">Próximas consultas</h2>
      {proximas.length ? <ul className="historico">{proximas.map((c) => <Linha key={c.id} c={c} />)}</ul> : <p className="muted">Nenhuma marcada.</p>}
      <h2 className="secao">Últimas consultas</h2>
      {passadas.length ? <ul className="historico">{passadas.map((c) => <Linha key={c.id} c={c} />)}</ul> : <p className="muted">Nenhuma no último mês.</p>}

      <div className="ficha-acoes">
        <button type="button" className="botao secundario" onClick={() => onEditar(p)}>
          Editar dados
        </button>
        <button type="button" className="link" onClick={() => void arquivar()}>
          {p.arquivado ? 'Desarquivar paciente' : 'Arquivar paciente'}
        </button>
      </div>
      <p className="muted pequeno">Pacientes não são apagados: o prontuário tem guarda obrigatória. Arquivar só tira da lista.</p>
      </>
      )}

      {marcando && (
        <ConsultaForm
          pacienteFixo={p}
          inicio={`${isoDia(new Date())}T09:00`}
          onFechar={() => setMarcando(false)}
          onSalvo={() => {
            setMarcando(false);
            void carregar();
          }}
        />
      )}
    </div>
  );
}

const VAZIO: PacienteIn = { nome: '', cpf: null, nascimento: null, telefone: null, email: null, endereco: null, responsavel: null, observacoes: null };

function PacienteForm({ paciente, onCancelar, onSalvo }: { paciente?: Paciente; onCancelar: () => void; onSalvo: (p: Paciente) => void }) {
  const [f, setF] = useState<PacienteIn>(paciente ? { ...VAZIO, ...paciente } : VAZIO);
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);
  const campo = (k: keyof PacienteIn) => ({
    value: f[k] ?? '',
    onChange: (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value || null }),
  });

  const salvar = async (e: FormEvent) => {
    e.preventDefault();
    setErro('');
    setSalvando(true);
    try {
      onSalvo(await api<Paciente>(paciente ? `/pacientes/${paciente.id}` : '/pacientes', { method: paciente ? 'PUT' : 'POST', body: f }));
    } catch (err) {
      setErro((err as Error).message);
      setSalvando(false);
    }
  };

  return (
    <form className="form-paciente" onSubmit={salvar}>
      <button type="button" className="link voltar" onClick={onCancelar}>
        ‹ Cancelar
      </button>
      <h1 className="dia-titulo">{paciente ? 'Editar paciente' : 'Cadastrar paciente'}</h1>
      <label className="campo">
        <span>Nome completo</span>
        <input required autoFocus maxLength={160} {...campo('nome')} />
      </label>
      <div className="duas">
        <label className="campo">
          <span>Telefone (WhatsApp)</span>
          <input type="tel" inputMode="tel" placeholder="(91) 98888-7777" {...campo('telefone')} />
        </label>
        <label className="campo">
          <span>Nascimento</span>
          <input type="date" {...campo('nascimento')} />
        </label>
      </div>
      <div className="duas">
        <label className="campo">
          <span>CPF</span>
          <input inputMode="numeric" placeholder="000.000.000-00" {...campo('cpf')} />
        </label>
        <label className="campo">
          <span>E-mail</span>
          <input type="email" {...campo('email')} />
        </label>
      </div>
      <label className="campo">
        <span>Endereço</span>
        <input maxLength={255} {...campo('endereco')} />
      </label>
      <label className="campo">
        <span>Responsável (menores de idade)</span>
        <input maxLength={160} {...campo('responsavel')} />
      </label>
      <label className="campo">
        <span>Observações</span>
        <textarea rows={4} maxLength={5000} placeholder="Alergias, medicamentos em uso, preferências de horário…" {...campo('observacoes')} />
      </label>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      <button type="submit" className="botao" disabled={salvando || f.nome.trim().length < 2}>
        {salvando ? 'Salvando…' : paciente ? 'Salvar alterações' : 'Cadastrar paciente'}
      </button>
    </form>
  );
}
