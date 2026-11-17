import { useEffect, useState, type FormEvent } from 'react';
import { api, type Consulta, type ConsultaIn, type PacienteResumo } from '../lib/api';
import { telefone } from '../lib/formato';

const DURACOES = [15, 30, 45, 60, 90, 120];
const PROCEDIMENTOS = ['Avaliação', 'Limpeza', 'Restauração', 'Canal', 'Extração', 'Clareamento', 'Manutenção de aparelho', 'Retorno'];

interface Props {
  consulta?: Consulta;
  inicio?: string;
  pacienteFixo?: PacienteResumo;
  onFechar: () => void;
  onSalvo: (c: Consulta) => void;
}

export function ConsultaForm({ consulta, inicio, pacienteFixo, onFechar, onSalvo }: Props) {
  const ini = consulta?.inicio ?? inicio ?? '';
  const [paciente, setPaciente] = useState<{ id: number; nome: string } | null>(
    consulta ? { id: consulta.paciente_id, nome: consulta.paciente_nome } : pacienteFixo ?? null,
  );
  const [busca, setBusca] = useState('');
  const [opcoes, setOpcoes] = useState<PacienteResumo[]>([]);
  const [data, setData] = useState(ini.slice(0, 10));
  const [horaIni, setHoraIni] = useState(ini.slice(11, 16) || '09:00');
  const [duracao, setDuracao] = useState(consulta?.duracao_min ?? 30);
  const [procedimento, setProcedimento] = useState(consulta?.procedimento ?? '');
  const [observacoes, setObservacoes] = useState(consulta?.observacoes ?? '');
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (paciente || busca.trim().length < 2) {
      setOpcoes([]);
      return;
    }
    const t = setTimeout(() => {
      void api<PacienteResumo[]>(`/pacientes?busca=${encodeURIComponent(busca.trim())}&limite=8`)
        .then(setOpcoes)
        .catch(() => setOpcoes([]));
    }, 250);
    return () => clearTimeout(t);
  }, [busca, paciente]);

  const salvar = async (e: FormEvent) => {
    e.preventDefault();
    if (!paciente) return setErro('Escolha o paciente.');
    setErro('');
    setSalvando(true);
    const corpo: ConsultaIn = {
      paciente_id: paciente.id,
      inicio: `${data}T${horaIni}`,
      duracao_min: duracao,
      procedimento: procedimento.trim() || null,
      status: consulta?.status ?? 'agendada',
      observacoes: observacoes.trim() || null,
    };
    try {
      onSalvo(await api<Consulta>(consulta ? `/consultas/${consulta.id}` : '/consultas', { method: consulta ? 'PUT' : 'POST', body: corpo }));
    } catch (err) {
      setErro((err as Error).message);
      setSalvando(false);
    }
  };

  return (
    <div className="painel-fundo" onClick={onFechar}>
      <form className="painel" role="dialog" aria-label={consulta ? 'Editar consulta' : 'Marcar consulta'} onSubmit={salvar} onClick={(e) => e.stopPropagation()}>
        <header className="painel-topo">
          <h2>{consulta ? 'Editar consulta' : 'Marcar consulta'}</h2>
          <button type="button" className="fechar" aria-label="Fechar" onClick={onFechar}>
            ×
          </button>
        </header>

        <div className="campo">
          <span>Paciente</span>
          {paciente ? (
            <div className="escolhido">
              <strong>{paciente.nome}</strong>
              {!consulta && !pacienteFixo && (
                <button type="button" className="link" onClick={() => setPaciente(null)}>
                  Trocar
                </button>
              )}
            </div>
          ) : (
            <>
              <input autoFocus placeholder="Digite o nome, CPF ou telefone" aria-label="Buscar paciente" value={busca} onChange={(e) => setBusca(e.target.value)} />
              {opcoes.length > 0 && (
                <ul className="opcoes" role="listbox">
                  {opcoes.map((p) => (
                    <li key={p.id}>
                      <button type="button" role="option" aria-selected={false} onClick={() => setPaciente(p)}>
                        {p.nome}
                        <small>{telefone(p.telefone)}</small>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {busca.trim().length >= 2 && opcoes.length === 0 && <small className="muted">Nenhum paciente com esse nome. Cadastre em Pacientes.</small>}
            </>
          )}
        </div>

        <div className="duas">
          <label className="campo">
            <span>Dia</span>
            <input type="date" required value={data} onChange={(e) => setData(e.target.value)} />
          </label>
          <label className="campo">
            <span>Horário</span>
            <input type="time" required step={300} value={horaIni} onChange={(e) => setHoraIni(e.target.value)} />
          </label>
        </div>

        <div className="campo">
          <span>Duração</span>
          <div className="chips" role="group" aria-label="Duração">
            {DURACOES.map((d) => (
              <button key={d} type="button" className="chip" aria-pressed={duracao === d} onClick={() => setDuracao(d)}>
                {d < 60 ? `${d} min` : `${d / 60} h${d % 60 ? ' 30' : ''}`}
              </button>
            ))}
          </div>
        </div>

        <label className="campo">
          <span>Procedimento</span>
          <input list="procedimentos" value={procedimento} maxLength={160} onChange={(e) => setProcedimento(e.target.value)} placeholder="Ex.: Limpeza" />
          <datalist id="procedimentos">
            {PROCEDIMENTOS.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </label>

        <label className="campo">
          <span>Observações</span>
          <textarea rows={3} maxLength={5000} value={observacoes} onChange={(e) => setObservacoes(e.target.value)} />
        </label>

        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao" disabled={salvando}>
          {salvando ? 'Salvando…' : consulta ? 'Salvar alterações' : 'Marcar consulta'}
        </button>
      </form>
    </div>
  );
}
