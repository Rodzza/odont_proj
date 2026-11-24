import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, type ItemOrcamento, type Orcamento, type Parcela, type Procedimento } from '../lib/api';
import { FORMAS, dataCurta, lerReais, paraCampo, reais } from '../lib/dinheiro';
import { isoDia } from '../lib/formato';

const ROTULO: Record<Orcamento['status'], string> = {
  aberto: 'Aguardando resposta',
  aprovado: 'Aprovado',
  recusado: 'Recusado',
  cancelado: 'Cancelado',
};

type Linha = { descricao: string; dente: string; faces: string; valor: string; quantidade: number };
const LINHA_VAZIA: Linha = { descricao: '', dente: '', faces: '', valor: '', quantidade: 1 };
const paraLinha = (i: ItemOrcamento): Linha => ({ descricao: i.descricao, dente: i.dente ? String(i.dente) : '', faces: i.faces ?? '', valor: paraCampo(i.valor), quantidade: i.quantidade });

/** Aba "Financeiro" da ficha do paciente: orçamentos, aprovação em parcelas e recebimentos. */
export function Orcamentos({ pacienteId }: { pacienteId: number }) {
  const [lista, setLista] = useState<Orcamento[] | null>(null);
  const [editando, setEditando] = useState<{ orc?: Orcamento; linhas: Linha[] } | null>(null);
  const [aprovando, setAprovando] = useState<Orcamento | null>(null);
  const [pagando, setPagando] = useState<Parcela | null>(null);
  const [aberto, setAberto] = useState<number | null>(null);
  const [erro, setErro] = useState('');

  const carregar = useCallback(() => {
    api<Orcamento[]>(`/pacientes/${pacienteId}/orcamentos`).then(setLista).catch((e: Error) => setErro(e.message));
  }, [pacienteId]);
  useEffect(carregar, [carregar]);

  const novo = async (doOdontograma: boolean) => {
    setErro('');
    try {
      const itens = doOdontograma ? await api<ItemOrcamento[]>(`/pacientes/${pacienteId}/orcamentos/sugestao`) : [];
      if (doOdontograma && itens.length === 0) {
        setErro('Nada pendente no odontograma: marque cárie, “a restaurar” ou “a extrair” primeiro, ou monte o orçamento à mão.');
        return;
      }
      setEditando({ linhas: itens.length ? itens.map(paraLinha) : [LINHA_VAZIA] });
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const acao = async (caminho: string, confirmar?: string) => {
    if (confirmar && !window.confirm(confirmar)) return;
    try {
      await api(caminho, { method: 'POST' });
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const restante = async (o: Orcamento) => {
    try {
      const novo = await api<Orcamento>(`/orcamentos/${o.id}/restante`, { method: 'POST' });
      setAberto(novo.id);
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const estornar = async (p: Parcela) => {
    const motivo = window.prompt('Motivo do estorno (fica registrado):');
    if (!motivo) return;
    try {
      await api(`/parcelas/${p.id}/estornar`, { method: 'POST', body: { motivo } });
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const hoje = isoDia(new Date());

  return (
    <div className="orcamentos">
      <div className="orc-acoes">
        <button type="button" className="botao" onClick={() => void novo(true)}>
          Orçamento do odontograma
        </button>
        <button type="button" className="botao secundario" onClick={() => void novo(false)}>
          Orçamento em branco
        </button>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {lista && lista.length === 0 && <p className="muted">Nenhum orçamento ainda. Comece pelo odontograma: o que estiver marcado como pendente vira item com o preço da sua tabela.</p>}

      {lista?.map((o) => (
        <article key={o.id} className={`orc orc--${o.status}`}>
          <button type="button" className="orc-linha-resumo" aria-expanded={aberto === o.id} onClick={() => setAberto(aberto === o.id ? null : o.id)}>
            <span className="orc-titulo">
              <strong>{o.origem_id ? 'Orçamento restante' : 'Plano de tratamento'}</strong>
              <span className="orc-total">{reais(o.total)}</span>
              <small className="muted">{new Date(o.criado_em).toLocaleDateString('pt-BR')}</small>
            </span>
            <span className={`orc-status orc-status--${o.status}`}>{ROTULO[o.status]}</span>
          </button>
          {aberto === o.id && (
          <div className="orc-detalhe">
          <p className="muted pequeno">Feito por {o.autor}{o.parcelas.length > 0 && `, ${reais(o.pago)} pago de ${reais(o.total)}`}</p>
          <table className="orc-itens">
            <tbody>
              {o.itens.map((i) => (
                <tr key={i.id} className={i.feito ? 'feito' : ''}>
                  <td>
                    {i.descricao}
                    {i.dente && <span className="muted"> · dente {i.dente}</span>}
                    {i.faces && <span className="muted"> · faces {i.faces}</span>}
                    {o.status === 'aprovado' && i.feito && <span className="ok pequeno"> · feito</span>}
                    {i.quantidade > 1 && <span className="muted"> × {i.quantidade}</span>}
                  </td>
                  <td className="num">{reais(i.valor * i.quantidade)}</td>
                </tr>
              ))}
              {o.desconto > 0 && (
                <tr className="muted">
                  <td>Desconto</td>
                  <td className="num">− {reais(o.desconto)}</td>
                </tr>
              )}
            </tbody>
          </table>
          {o.observacoes && <p className="obs">{o.observacoes}</p>}

          {o.parcelas.length > 0 && (
            <>
              <h4 className="orc-sub">Parcelas</h4>
              <ul className="parcelas">
                {o.parcelas.map((p) => {
                  const atrasada = !p.pago_em && !p.cancelada && p.vencimento < hoje;
                  return (
                    <li key={p.id} className={atrasada ? 'atrasada' : p.pago_em ? 'paga' : ''}>
                      <span className="num">
                        {p.numero}/{o.parcelas.length}
                      </span>
                      <span>{dataCurta(p.vencimento)}</span>
                      <span className="num">{reais(p.valor)}</span>
                      {p.pago_em ? (
                        <span className="parc-pago">
                          Pago em {dataCurta(p.pago_em)} ({FORMAS[p.forma ?? ''] ?? p.forma}){' '}
                          <button type="button" className="link pequeno" onClick={() => void estornar(p)}>
                            Estornar
                          </button>
                        </span>
                      ) : p.cancelada ? (
                        <span className="muted">Cancelada</span>
                      ) : (
                        <button type="button" className="botao pequeno-botao" onClick={() => setPagando(p)}>
                          {atrasada ? 'Atrasada · Receber' : 'Receber'}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          <div className="orc-rodape">
            {o.status === 'aberto' && (
              <>
                <button type="button" className="botao" onClick={() => setAprovando(o)}>
                  Paciente aprovou
                </button>
                <button type="button" className="link" onClick={() => setEditando({ orc: o, linhas: o.itens.map(paraLinha) })}>
                  Editar
                </button>
                <button type="button" className="link" onClick={() => void acao(`/orcamentos/${o.id}/recusar`, 'Marcar este orçamento como recusado?')}>
                  Recusado
                </button>
              </>
            )}
            {(o.status === 'aprovado' || o.status === 'cancelado') && o.itens.some((i) => !i.feito) && (
              <button type="button" className="link" onClick={() => void restante(o)}>
                Gerar orçamento restante
              </button>
            )}
            {o.status === 'aprovado' && (
              <button type="button" className="link" onClick={() => void acao(`/orcamentos/${o.id}/cancelar`, 'Cancelar o tratamento? Parcelas em aberto deixam de ser cobradas; as pagas continuam registradas.')}>
                Cancelar tratamento
              </button>
            )}
          </div>
          </div>
          )}
        </article>
      ))}

      {editando && (
        <EditorOrcamento
          pacienteId={pacienteId}
          orc={editando.orc}
          linhasIniciais={editando.linhas}
          onFechar={() => setEditando(null)}
          onSalvo={() => {
            setEditando(null);
            carregar();
          }}
        />
      )}
      {aprovando && (
        <Aprovar
          orc={aprovando}
          onFechar={() => setAprovando(null)}
          onFeito={() => {
            setAprovando(null);
            carregar();
          }}
        />
      )}
      {pagando && (
        <Receber
          parcela={pagando}
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

function EditorOrcamento({ pacienteId, orc, linhasIniciais, onFechar, onSalvo }: { pacienteId: number; orc?: Orcamento; linhasIniciais: Linha[]; onFechar: () => void; onSalvo: () => void }) {
  const [linhas, setLinhas] = useState<Linha[]>(linhasIniciais);
  const [procs, setProcs] = useState<Procedimento[]>([]);
  const [desconto, setDesconto] = useState(orc ? paraCampo(orc.desconto) : '');
  const [obs, setObs] = useState(orc?.observacoes ?? '');
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    api<Procedimento[]>('/procedimentos').then((l) => setProcs(l.filter((p) => p.ativo))).catch(() => setProcs([]));
  }, []);

  const muda = (i: number, campo: Partial<Linha>) => setLinhas((l) => l.map((x, k) => (k === i ? { ...x, ...campo } : x)));
  const escolher = (i: number, nome: string) => {
    const p = procs.find((x) => x.nome === nome);
    muda(i, p && p.valor > 0 && !linhas[i]!.valor ? { descricao: nome, valor: paraCampo(p.valor) } : { descricao: nome });
  };

  const subtotal = linhas.reduce((s, l) => s + (lerReais(l.valor) ?? 0) * l.quantidade, 0);
  const desc = lerReais(desconto) ?? 0;

  const salvar = async (e: FormEvent) => {
    e.preventDefault();
    setErro('');
    const itens = [];
    for (const [k, l] of linhas.entries()) {
      const valor = lerReais(l.valor);
      if (valor === null) return setErro(`Valor inválido no item ${k + 1}.`);
      itens.push({ descricao: l.descricao.trim(), dente: l.dente ? Number(l.dente) : null, faces: l.faces || null, valor, quantidade: l.quantidade });
    }
    if (desconto && lerReais(desconto) === null) return setErro('Desconto inválido.');
    setSalvando(true);
    try {
      const body = { itens, desconto: desc, observacoes: obs.trim() || null };
      await api(orc ? `/orcamentos/${orc.id}` : `/pacientes/${pacienteId}/orcamentos`, { method: orc ? 'PUT' : 'POST', body });
      onSalvo();
    } catch (err) {
      setErro((err as Error).message);
      setSalvando(false);
    }
  };

  return (
    <div className="painel-fundo" onClick={onFechar}>
      <form className="painel painel--largo" role="dialog" aria-label={orc ? 'Editar orçamento' : 'Novo orçamento'} onSubmit={salvar} onClick={(e) => e.stopPropagation()}>
        <header className="painel-topo">
          <h2>{orc ? 'Editar orçamento' : 'Novo orçamento'}</h2>
          <button type="button" className="fechar" aria-label="Fechar" onClick={onFechar}>
            ×
          </button>
        </header>
        <datalist id="procs">
          {procs.map((p) => (
            <option key={p.id} value={p.nome} />
          ))}
        </datalist>
        <div className="orc-linhas">
          {linhas.map((l, i) => (
            <div key={i} className="orc-linha">
              <input aria-label={`Procedimento ${i + 1}`} list="procs" required minLength={2} value={l.descricao} placeholder="Procedimento" onChange={(e) => escolher(i, e.target.value)} />
              <input aria-label={`Dente ${i + 1}`} inputMode="numeric" value={l.dente} placeholder="Dente" onChange={(e) => muda(i, { dente: e.target.value.replace(/\D/g, '').slice(0, 2) })} />
              <input aria-label={`Faces ${i + 1}`} value={l.faces} placeholder="Faces" onChange={(e) => muda(i, { faces: e.target.value.toUpperCase().replace(/[^VLMDO]/g, '').slice(0, 5) })} />
              <input aria-label={`Valor ${i + 1}`} inputMode="decimal" required value={l.valor} placeholder="0,00" onChange={(e) => muda(i, { valor: e.target.value })} />
              <button type="button" className="fechar" aria-label={`Tirar item ${i + 1}`} disabled={linhas.length === 1} onClick={() => setLinhas((x) => x.filter((_, k) => k !== i))}>
                ×
              </button>
            </div>
          ))}
        </div>
        <button type="button" className="link" onClick={() => setLinhas((l) => [...l, LINHA_VAZIA])}>
          + Adicionar item
        </button>
        <div className="duas">
          <label className="campo">
            <span>Desconto (R$)</span>
            <input inputMode="decimal" value={desconto} placeholder="0,00" onChange={(e) => setDesconto(e.target.value)} />
          </label>
          <div className="campo">
            <span>Total</span>
            <strong className="orc-total">{reais(Math.max(subtotal - desc, 0))}</strong>
          </div>
        </div>
        <label className="campo">
          <span>Observações para o paciente</span>
          <textarea rows={2} maxLength={2000} value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Ex.: validade de 30 dias" />
        </label>
        {linhas.some((l) => (lerReais(l.valor) ?? 0) === 0) && <p className="aviso pequeno">Há itens sem preço. Defina os valores na tabela de preços (menu Financeiro) ou digite aqui.</p>}
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao" disabled={salvando}>
          {salvando ? 'Salvando…' : 'Salvar orçamento'}
        </button>
      </form>
    </div>
  );
}

function Aprovar({ orc, onFechar, onFeito }: { orc: Orcamento; onFechar: () => void; onFeito: () => void }) {
  const [parcelas, setParcelas] = useState(1);
  const [venc, setVenc] = useState(isoDia(new Date()));
  const [entrada, setEntrada] = useState(true);
  const [forma, setForma] = useState('pix');
  const [erro, setErro] = useState('');

  const valor = Math.floor(orc.total / parcelas);
  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/orcamentos/${orc.id}/aprovar`, { method: 'POST', body: { parcelas, primeiro_vencimento: venc, entrada_paga: entrada, forma_entrada: entrada ? forma : null } });
      onFeito();
    } catch (err) {
      setErro((err as Error).message);
    }
  };

  return (
    <div className="painel-fundo" onClick={onFechar}>
      <form className="painel" role="dialog" aria-label="Aprovar orçamento" onSubmit={enviar} onClick={(e) => e.stopPropagation()}>
        <header className="painel-topo">
          <h2>Aprovar {reais(orc.total)}</h2>
          <button type="button" className="fechar" aria-label="Fechar" onClick={onFechar}>
            ×
          </button>
        </header>
        <div className="campo">
          <span>Parcelas</span>
          <div className="chips" role="group" aria-label="Parcelas">
            {[1, 2, 3, 4, 5, 6, 10, 12].map((n) => (
              <button key={n} type="button" className="chip" aria-pressed={parcelas === n} onClick={() => setParcelas(n)}>
                {n === 1 ? 'À vista' : `${n}×`}
              </button>
            ))}
          </div>
          {parcelas > 1 && <small className="muted">{parcelas} de {reais(valor)} (centavos que sobram vão na 1ª)</small>}
        </div>
        <label className="campo">
          <span>{parcelas === 1 ? 'Vencimento' : '1º vencimento'} (as outras, todo mês no mesmo dia)</span>
          <input type="date" required value={venc} onChange={(e) => setVenc(e.target.value)} />
        </label>
        <label className="simnao-linha">
          <input type="checkbox" checked={entrada} onChange={(e) => setEntrada(e.target.checked)} /> {parcelas === 1 ? 'Já pagou agora' : 'Pagou a 1ª agora'}
        </label>
        {entrada && <FormaPagamento valor={forma} onMudar={setForma} />}
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao">
          Confirmar aprovação
        </button>
        <p className="muted pequeno">Depois de aprovado, os itens e o valor não mudam. Para mudar o tratamento, cancele e faça outro orçamento.</p>
      </form>
    </div>
  );
}

function FormaPagamento({ valor, onMudar }: { valor: string; onMudar: (f: string) => void }) {
  return (
    <div className="campo">
      <span>Forma de pagamento</span>
      <div className="chips" role="group" aria-label="Forma de pagamento">
        {Object.entries(FORMAS).map(([id, rotulo]) => (
          <button key={id} type="button" className="chip" aria-pressed={valor === id} onClick={() => onMudar(id)}>
            {rotulo}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Receber({ parcela, nome, onFechar, onFeito }: { parcela: Parcela; nome?: string; onFechar: () => void; onFeito: () => void }) {
  const [forma, setForma] = useState('pix');
  const [data, setData] = useState(isoDia(new Date()));
  const [erro, setErro] = useState('');
  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/parcelas/${parcela.id}/pagar`, { method: 'POST', body: { forma, pago_em: data } });
      onFeito();
    } catch (err) {
      setErro((err as Error).message);
    }
  };
  return (
    <div className="painel-fundo" onClick={onFechar}>
      <form className="painel" role="dialog" aria-label="Receber parcela" onSubmit={enviar} onClick={(e) => e.stopPropagation()}>
        <header className="painel-topo">
          <div>
            <h2>Receber {reais(parcela.valor)}</h2>
            <p className="muted">
              {nome ? `${nome}, ` : ''}parcela {parcela.numero}, vence {dataCurta(parcela.vencimento)}
            </p>
          </div>
          <button type="button" className="fechar" aria-label="Fechar" onClick={onFechar}>
            ×
          </button>
        </header>
        <FormaPagamento valor={forma} onMudar={setForma} />
        <label className="campo">
          <span>Data do pagamento</span>
          <input type="date" required max={isoDia(new Date())} value={data} onChange={(e) => setData(e.target.value)} />
        </label>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao">
          Registrar pagamento
        </button>
      </form>
    </div>
  );
}
