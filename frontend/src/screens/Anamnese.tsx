import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../lib/api';

export interface AnamneseDados {
  queixa_principal: string | null;
  alergias: string | null;
  medicamentos: string | null;
  doencas: string[];
  outras_doencas: string | null;
  gestante: boolean | null;
  fumante: boolean | null;
  reacao_anestesia: boolean | null;
  sangramento_excessivo: boolean | null;
  pressao_arterial: string | null;
  observacoes: string | null;
  atualizado_em?: string | null;
  alertas?: string[];
}

const DOENCAS: [string, string][] = [
  ['diabetes', 'Diabetes'],
  ['hipertensao', 'Hipertensão'],
  ['cardiopatia', 'Cardiopatia'],
  ['asma', 'Asma'],
  ['epilepsia', 'Epilepsia'],
  ['hepatite', 'Hepatite'],
  ['problemas_renais', 'Problemas renais'],
  ['disturbio_coagulacao', 'Distúrbio de coagulação'],
  ['osteoporose', 'Osteoporose'],
  ['ansiedade', 'Ansiedade'],
];

const PERGUNTAS: [keyof AnamneseDados, string][] = [
  ['reacao_anestesia', 'Já teve reação à anestesia?'],
  ['sangramento_excessivo', 'Sangra muito em cortes ou extrações?'],
  ['gestante', 'Está grávida?'],
  ['fumante', 'Fuma?'],
];

function SimNao({ valor, onChange, rotulo }: { valor: boolean | null; onChange: (v: boolean | null) => void; rotulo: string }) {
  return (
    <div className="simnao" role="radiogroup" aria-label={rotulo}>
      <span>{rotulo}</span>
      {([
        [true, 'Sim'],
        [false, 'Não'],
      ] as const).map(([v, r]) => (
        <button key={r} type="button" role="radio" aria-checked={valor === v} className="chip" onClick={() => onChange(valor === v ? null : v)}>
          {r}
        </button>
      ))}
    </div>
  );
}

export function Anamnese({ pacienteId, onSalvo }: { pacienteId: number; onSalvo: (a: AnamneseDados) => void }) {
  const [a, setA] = useState<AnamneseDados | null>(null);
  const [erro, setErro] = useState('');
  const [msg, setMsg] = useState('');
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    api<AnamneseDados>(`/pacientes/${pacienteId}/anamnese`).then(setA).catch((e: Error) => setErro(e.message));
  }, [pacienteId]);

  if (erro && !a) return <p className="erro">{erro}</p>;
  if (!a) return <p className="muted">Carregando…</p>;

  const texto = (k: keyof AnamneseDados) => ({
    value: (a[k] as string | null) ?? '',
    onChange: (e: { target: { value: string } }) => setA({ ...a, [k]: e.target.value || null }),
  });

  const salvar = async (e: FormEvent) => {
    e.preventDefault();
    setSalvando(true);
    setErro('');
    setMsg('');
    try {
      const corpo: Partial<AnamneseDados> = { ...a };
      delete corpo.atualizado_em;
      delete corpo.alertas;
      const novo = await api<AnamneseDados>(`/pacientes/${pacienteId}/anamnese`, { method: 'PUT', body: corpo });
      setA(novo);
      onSalvo(novo);
      setMsg('Anamnese salva.');
    } catch (err) {
      setErro((err as Error).message);
    }
    setSalvando(false);
  };

  return (
    <form className="anamnese" onSubmit={salvar}>
      {a.atualizado_em && <p className="muted pequeno">Atualizada em {new Date(a.atualizado_em).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</p>}
      <label className="campo">
        <span>Queixa principal</span>
        <textarea rows={2} maxLength={1000} {...texto('queixa_principal')} />
      </label>
      <label className="campo">
        <span>Alergias</span>
        <input maxLength={1000} placeholder="Medicamentos, látex, anestésicos…" {...texto('alergias')} />
      </label>
      <label className="campo">
        <span>Medicamentos em uso</span>
        <input maxLength={1000} {...texto('medicamentos')} />
      </label>
      <fieldset className="campo doencas">
        <legend>Condições de saúde</legend>
        {DOENCAS.map(([id, rotulo]) => (
          <label key={id} className="alternar">
            <input
              type="checkbox"
              checked={a.doencas.includes(id)}
              onChange={(e) => setA({ ...a, doencas: e.target.checked ? [...a.doencas, id] : a.doencas.filter((d) => d !== id) })}
            />
            {rotulo}
          </label>
        ))}
      </fieldset>
      <label className="campo">
        <span>Outras condições</span>
        <input maxLength={1000} {...texto('outras_doencas')} />
      </label>
      {PERGUNTAS.map(([k, r]) => (
        <SimNao key={k} rotulo={r} valor={a[k] as boolean | null} onChange={(v) => setA({ ...a, [k]: v })} />
      ))}
      <label className="campo curto">
        <span>Pressão arterial</span>
        <input maxLength={20} placeholder="12/8" {...texto('pressao_arterial')} />
      </label>
      <label className="campo">
        <span>Observações</span>
        <textarea rows={3} maxLength={3000} {...texto('observacoes')} />
      </label>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {msg && <p role="status" className="ok">{msg}</p>}
      <button type="submit" className="botao" disabled={salvando}>
        {salvando ? 'Salvando…' : 'Salvar anamnese'}
      </button>
    </form>
  );
}
