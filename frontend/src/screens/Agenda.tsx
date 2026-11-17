import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, type Consulta, type Status } from '../lib/api';
import { STATUS, diaLongo, hora, isoDia, linkConfirmacao, minutosDoDia, semana, somaDias, telefone } from '../lib/formato';
import { ConsultaForm } from './ConsultaForm';

const INICIO_DIA = 7 * 60;
const FIM_DIA = 20 * 60;
const PX_POR_MIN = 2;

type Edicao = { consulta?: Consulta; inicio?: string } | null;

export function Agenda({ clinica }: { clinica: string }) {
  const [dia, setDia] = useState(() => new Date());
  const [consultas, setConsultas] = useState<Consulta[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState('');
  const [aberta, setAberta] = useState<Consulta | null>(null);
  const [edicao, setEdicao] = useState<Edicao>(null);

  const dias = useMemo(() => semana(dia), [dia]);
  const de = isoDia(dias[0]!);
  const ate = isoDia(dias[dias.length - 1]!);

  const carregar = useCallback(async () => {
    setErro('');
    try {
      setConsultas(await api<Consulta[]>(`/consultas?de=${de}&ate=${ate}`));
    } catch (e) {
      setErro((e as Error).message);
    }
    setCarregando(false);
  }, [de, ate]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const hoje = isoDia(dia);
  const doDia = consultas.filter((c) => c.inicio.startsWith(hoje));
  const ativas = doDia.filter((c) => c.status !== 'cancelada');
  const aConfirmar = doDia.filter((c) => c.status === 'agendada').length;

  const mudarStatus = async (c: Consulta, status: Status) => {
    try {
      const nova = await api<Consulta>(`/consultas/${c.id}/status`, { method: 'PATCH', body: { status } });
      setConsultas((l) => l.map((x) => (x.id === nova.id ? nova : x)));
      setAberta(nova);
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const novaNoHorario = (min: number) => {
    const h = String(Math.floor(min / 60)).padStart(2, '0');
    const m = String(min % 60).padStart(2, '0');
    setEdicao({ inicio: `${hoje}T${h}:${m}` });
  };

  const horas = [];
  for (let m = INICIO_DIA; m < FIM_DIA; m += 60) horas.push(m);

  return (
    <div className="agenda">
      <header className="topo">
        <div>
          <h1 className="dia-titulo">{diaLongo(dia)}</h1>
          <p className="resumo">
            {ativas.length === 0 ? 'Nenhuma consulta marcada' : `${ativas.length} ${ativas.length === 1 ? 'consulta' : 'consultas'}`}
            {aConfirmar > 0 && <span className="pendente">, {aConfirmar} a confirmar</span>}
          </p>
        </div>
        <button type="button" className="botao" onClick={() => setEdicao({ inicio: `${hoje}T09:00` })}>
          Marcar consulta
        </button>
      </header>

      <div className="semana" role="tablist" aria-label="Dias da semana">
        <button type="button" className="semana-seta" aria-label="Semana anterior" onClick={() => setDia(somaDias(dia, -7))}>
          ‹
        </button>
        {dias.map((d) => {
          const iso = isoDia(d);
          const n = consultas.filter((c) => c.inicio.startsWith(iso) && STATUS[c.status].ativa).length;
          return (
            <button key={iso} type="button" role="tab" className="semana-dia" aria-selected={iso === hoje} onClick={() => setDia(d)}>
              <span className="semana-nome">{d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '')}</span>
              <span className="semana-num">{d.getDate()}</span>
              <span className="semana-pontos" aria-label={`${n} consultas`}>
                {Array.from({ length: Math.min(n, 5) }, (_, i) => (
                  <i key={i} />
                ))}
              </span>
            </button>
          );
        })}
        <button type="button" className="semana-seta" aria-label="Próxima semana" onClick={() => setDia(somaDias(dia, 7))}>
          ›
        </button>
        <button type="button" className="link hoje" onClick={() => setDia(new Date())}>
          Hoje
        </button>
      </div>

      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      <div className="pagina" style={{ height: (FIM_DIA - INICIO_DIA) * PX_POR_MIN }} aria-busy={carregando}>
        {horas.map((m) => (
          <div key={m} className="linha-hora" style={{ top: (m - INICIO_DIA) * PX_POR_MIN }}>
            <span>{String(m / 60).padStart(2, '0')}:00</span>
          </div>
        ))}
        {horas.flatMap((m) => [m, m + 30]).map((m) => (
          <button
            key={`s${m}`}
            type="button"
            className="vaga"
            style={{ top: (m - INICIO_DIA) * PX_POR_MIN, height: 30 * PX_POR_MIN }}
            aria-label={`Marcar às ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`}
            onClick={() => novaNoHorario(m)}
          />
        ))}
        {doDia.map((c) => {
          const top = (Math.max(minutosDoDia(c.inicio), INICIO_DIA) - INICIO_DIA) * PX_POR_MIN;
          return (
            <button
              key={c.id}
              type="button"
              className={`bloco bloco--${c.status}`}
              style={{ top, height: Math.max(c.duracao_min * PX_POR_MIN - 3, 26) }}
              onClick={() => setAberta(c)}
            >
              <span className="bloco-hora">{hora(c.inicio)}</span>
              <span className="bloco-nome">{c.paciente_nome}</span>
              {c.procedimento && <span className="bloco-proc">{c.procedimento}</span>}
              <span className="bloco-status">{STATUS[c.status].rotulo}</span>
            </button>
          );
        })}
      </div>

      {aberta && (
        <div className="painel-fundo" onClick={() => setAberta(null)}>
          <section className="painel" role="dialog" aria-label={`Consulta de ${aberta.paciente_nome}`} onClick={(e) => e.stopPropagation()}>
            <header className="painel-topo">
              <div>
                <h2>{aberta.paciente_nome}</h2>
                <p className="muted">
                  {hora(aberta.inicio)}, {aberta.duracao_min} min{aberta.procedimento ? `, ${aberta.procedimento}` : ''}
                </p>
              </div>
              <button type="button" className="fechar" aria-label="Fechar" onClick={() => setAberta(null)}>
                ×
              </button>
            </header>
            {aberta.paciente_telefone && <p>{telefone(aberta.paciente_telefone)}</p>}
            {aberta.observacoes && <p className="obs">{aberta.observacoes}</p>}
            <div className="status-escolha" role="group" aria-label="Situação da consulta">
              {(Object.keys(STATUS) as Status[]).map((s) => (
                <button key={s} type="button" className={`chip chip--${s}`} aria-pressed={aberta.status === s} onClick={() => void mudarStatus(aberta, s)}>
                  {STATUS[s].rotulo}
                </button>
              ))}
            </div>
            <div className="painel-acoes">
              {(() => {
                const link = linkConfirmacao(aberta.paciente_nome, aberta.paciente_telefone, aberta.inicio, clinica);
                return link ? (
                  <a className="botao whatsapp" href={link} target="_blank" rel="noopener noreferrer">
                    Confirmar pelo WhatsApp
                  </a>
                ) : (
                  <p className="muted">Cadastre o telefone do paciente para confirmar pelo WhatsApp.</p>
                );
              })()}
              <button
                type="button"
                className="botao secundario"
                onClick={() => {
                  setEdicao({ consulta: aberta });
                  setAberta(null);
                }}
              >
                Editar consulta
              </button>
            </div>
          </section>
        </div>
      )}

      {edicao && (
        <ConsultaForm
          consulta={edicao.consulta}
          inicio={edicao.inicio}
          onFechar={() => setEdicao(null)}
          onSalvo={(c) => {
            setEdicao(null);
            setDia(new Date(`${c.inicio.slice(0, 10)}T12:00:00`));
            void carregar();
          }}
        />
      )}
    </div>
  );
}
