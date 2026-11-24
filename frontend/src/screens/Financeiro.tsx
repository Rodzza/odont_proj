import { useCallback, useEffect, useState } from 'react';
import { api, type ContaReceber, type Procedimento, type ResumoFinanceiro } from '../lib/api';
import { FORMAS, dataCurta, lerReais, linkCobranca, paraCampo, reais } from '../lib/dinheiro';
import { isoDia } from '../lib/formato';
import { Receber } from './Orcamentos';

const MESES = (d: Date) => d.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });

/** Menu Financeiro: caixa do mês, contas a receber (atrasadas primeiro) e tabela de preços. */
export function Financeiro({ clinica }: { clinica: string }) {
  const [mes, setMes] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [res, setRes] = useState<ResumoFinanceiro | null>(null);
  const [aba, setAba] = useState<'receber' | 'precos'>('receber');
  const [pagando, setPagando] = useState<ContaReceber | null>(null);
  const [erro, setErro] = useState('');

  const de = isoDia(mes);
  const ate = isoDia(new Date(mes.getFullYear(), mes.getMonth() + 1, 0));
  const carregar = useCallback(() => {
    api<ResumoFinanceiro>(`/financeiro?de=${de}&ate=${ate}`).then(setRes).catch((e: Error) => setErro(e.message));
  }, [de, ate]);
  useEffect(carregar, [carregar]);

  const hoje = isoDia(new Date());
  const atrasadas = res?.contas.filter((c) => c.vencimento < hoje) ?? [];
  const proximas = res?.contas.filter((c) => c.vencimento >= hoje) ?? [];
  const mudaMes = (n: number) => setMes((m) => new Date(m.getFullYear(), m.getMonth() + n, 1));

  return (
    <div className="financeiro">
      <header className="topo">
        <div>
          <h1 className="dia-titulo">Financeiro</h1>
          <p className="resumo">Recebimentos e parcelas de todos os pacientes</p>
        </div>
      </header>

      <div className="caixa">
        <section className="caixa-cartao">
          <div className="caixa-mes">
            <button type="button" className="semana-seta" aria-label="Mês anterior" onClick={() => mudaMes(-1)}>
              ‹
            </button>
            <span>Recebido em {MESES(mes)}</span>
            <button type="button" className="semana-seta" aria-label="Próximo mês" onClick={() => mudaMes(1)}>
              ›
            </button>
          </div>
          <strong className="caixa-valor">{res ? reais(res.recebido_periodo) : '…'}</strong>
          {res && Object.keys(res.por_forma).length > 0 && (
            <p className="caixa-formas">
              {Object.entries(res.por_forma)
                .sort((a, b) => b[1] - a[1])
                .map(([f, v]) => `${FORMAS[f] ?? f} ${reais(v)}`)
                .join('  |  ')}
            </p>
          )}
        </section>
        <section className="caixa-cartao">
          <span>A receber</span>
          <strong className="caixa-valor">{res ? reais(res.a_receber) : '…'}</strong>
          <p className="caixa-formas">{proximas.length === 1 ? '1 parcela em dia' : `${proximas.length} parcelas em dia`}</p>
        </section>
        <section className={`caixa-cartao ${res?.atrasado ? 'caixa-cartao--alerta' : ''}`}>
          <span>Atrasado</span>
          <strong className="caixa-valor">{res ? reais(res.atrasado) : '…'}</strong>
          <p className="caixa-formas">{atrasadas.length === 0 ? 'Ninguém em atraso' : atrasadas.length === 1 ? '1 parcela vencida' : `${atrasadas.length} parcelas vencidas`}</p>
        </section>
      </div>

      <div className="abas" role="tablist" aria-label="Financeiro">
        <button type="button" role="tab" className="aba" aria-selected={aba === 'receber'} onClick={() => setAba('receber')}>
          Contas a receber
        </button>
        <button type="button" role="tab" className="aba" aria-selected={aba === 'precos'} onClick={() => setAba('precos')}>
          Tabela de preços
        </button>
      </div>

      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      {aba === 'receber' && res && (
        <>
          {res.contas.length === 0 && <p className="muted">Nenhuma parcela em aberto. Os orçamentos aprovados na ficha do paciente aparecem aqui.</p>}
          {atrasadas.length > 0 && <Lista titulo="Atrasadas" contas={atrasadas} clinica={clinica} atrasada onReceber={setPagando} />}
          {proximas.length > 0 && <Lista titulo="Próximos vencimentos" contas={proximas} clinica={clinica} onReceber={setPagando} />}
        </>
      )}
      {aba === 'precos' && <TabelaPrecos />}

      {pagando && (
        <Receber
          parcela={pagando}
          nome={pagando.paciente_nome}
          onFechar={() => setPagando(null)}
          onFeito={() => {
            setPagando(null);
            carregar();
          }}
        />
      )}
    </div>
  );
}

function Lista({ titulo, contas, clinica, atrasada, onReceber }: { titulo: string; contas: ContaReceber[]; clinica: string; atrasada?: boolean; onReceber: (c: ContaReceber) => void }) {
  return (
    <>
      <h3 className="secao">{titulo}</h3>
      <ul className={`contas ${atrasada ? 'contas--atrasadas' : ''}`}>
        {contas.map((c) => {
          const zap = atrasada ? linkCobranca(c.paciente_nome, c.paciente_telefone, c.valor, c.vencimento, clinica) : null;
          return (
            <li key={c.id}>
              <span className="conta-data">{dataCurta(c.vencimento)}</span>
              <span className="conta-quem">
                <strong>{c.paciente_nome}</strong>
                <small className="muted">
                  parcela {c.numero} de {c.total_parcelas}
                </small>
              </span>
              <span className="num conta-valor">{reais(c.valor)}</span>
              <span className="conta-acoes">
                {zap && (
                  <a className="link" href={zap} target="_blank" rel="noopener noreferrer">
                    Lembrar no WhatsApp
                  </a>
                )}
                <button type="button" className="botao pequeno-botao" onClick={() => onReceber(c)}>
                  Receber
                </button>
              </span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function TabelaPrecos() {
  const [procs, setProcs] = useState<Procedimento[] | null>(null);
  const [novo, setNovo] = useState('');
  const [erro, setErro] = useState('');
  const [salvo, setSalvo] = useState<number | null>(null);

  const carregar = () => api<Procedimento[]>('/procedimentos').then(setProcs).catch((e: Error) => setErro(e.message));
  useEffect(() => {
    void carregar();
  }, []);

  const salvar = async (p: Procedimento, campo: Partial<Procedimento>) => {
    setErro('');
    try {
      const atual = await api<Procedimento>(`/procedimentos/${p.id}`, { method: 'PUT', body: { nome: p.nome, valor: p.valor, ativo: p.ativo, ...campo } });
      setProcs((l) => l?.map((x) => (x.id === p.id ? atual : x)) ?? null);
      setSalvo(p.id);
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const criar = async () => {
    if (novo.trim().length < 2) return;
    try {
      await api('/procedimentos', { method: 'POST', body: { nome: novo, valor: 0 } });
      setNovo('');
      void carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  return (
    <div className="precos">
      <p className="muted pequeno">Os preços daqui entram nos orçamentos. Restauração e extração também são sugeridas a partir do odontograma.</p>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      <ul className="precos-lista">
        {procs?.map((p) => (
          <li key={p.id} className={p.ativo ? '' : 'inativo'}>
            <span>
              {p.nome}
              {p.sugere && <small className="muted"> · sugerido pelo odontograma</small>}
            </span>
            <label className="preco-campo">
              <span className="oculto">Preço de {p.nome}</span>
              R$
              <input
                key={`${p.id}-${p.valor}`}
                inputMode="decimal"
                defaultValue={p.valor ? paraCampo(p.valor) : ''}
                placeholder="definir"
                onBlur={(e) => {
                  const v = lerReais(e.target.value || '0');
                  if (v === null) setErro(`Preço inválido em ${p.nome}.`);
                  else if (v !== p.valor) void salvar(p, { valor: v });
                }}
              />
            </label>
            <button type="button" className="link pequeno" onClick={() => void salvar(p, { ativo: !p.ativo })}>
              {p.ativo ? 'Ocultar' : 'Usar de novo'}
            </button>
            {salvo === p.id && <span className="ok pequeno" aria-live="polite">Salvo</span>}
          </li>
        ))}
      </ul>
      <div className="precos-novo">
        <input aria-label="Novo procedimento" value={novo} maxLength={120} placeholder="Novo procedimento, ex.: Facetas" onChange={(e) => setNovo(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && void criar()} />
        <button type="button" className="botao secundario" onClick={() => void criar()}>
          Adicionar
        </button>
      </div>
    </div>
  );
}
