import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api, lerSessao, type AnaliseIA, type LeituraAnexo } from '../lib/api';

interface Anexo {
  id: number;
  nome: string;
  descricao: string | null;
  tipo: string;
  tamanho: number;
  criado_em: string;
}

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '/api';
const tamanho = (b: number) => (b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(b / 1024)} KB`);

/** Busca o arquivo com o token (anexos nunca têm link público) e devolve um endereço local. */
async function abrirArquivo(id: number): Promise<string> {
  const r = await fetch(`${BASE}/anexos/${id}/arquivo`, { headers: { Authorization: `Bearer ${lerSessao()?.token ?? ''}` } });
  if (!r.ok) throw new ApiError(r.status, 'Não foi possível abrir o anexo.');
  return URL.createObjectURL(await r.blob());
}

export function Anexos({ pacienteId }: { pacienteId: number }) {
  const [lista, setLista] = useState<Anexo[] | null>(null);
  const [descricao, setDescricao] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [vendo, setVendo] = useState<{ anexo: Anexo; url: string } | null>(null);
  const [leituras, setLeituras] = useState<Record<number, LeituraAnexo>>({});
  const [lendo, setLendo] = useState(false);
  const arquivoRef = useRef<HTMLInputElement>(null);

  const carregar = useCallback(() => {
    api<Anexo[]>(`/pacientes/${pacienteId}/anexos`).then(setLista).catch((e: Error) => setErro(e.message));
  }, [pacienteId]);
  useEffect(carregar, [carregar]);
  useEffect(() => {
    api<AnaliseIA<LeituraAnexo>[]>(`/ia/pacientes/${pacienteId}/analises?tipo=anexo`)
      .then((ls) => {
        const porAnexo: Record<number, LeituraAnexo> = {};
        for (const l of [...ls].reverse()) if (l.anexo_id) porAnexo[l.anexo_id] = l.resultado; // a mais recente vence
        setLeituras(porAnexo);
      })
      .catch(() => {});
  }, [pacienteId]);

  const lerComIA = async (a: Anexo) => {
    setErro('');
    setLendo(true);
    try {
      const r = await api<AnaliseIA<LeituraAnexo>>(`/ia/anexos/${a.id}/ler`, { method: 'POST' });
      setLeituras((l) => ({ ...l, [a.id]: r.resultado }));
    } catch (e) {
      setErro((e as Error).message);
    }
    setLendo(false);
  };
  useEffect(() => () => (vendo ? URL.revokeObjectURL(vendo.url) : undefined), [vendo]);

  const enviar = async (arquivo: File | undefined) => {
    if (!arquivo) return;
    setErro('');
    setEnviando(true);
    const form = new FormData();
    form.append('arquivo', arquivo);
    if (descricao.trim()) form.append('descricao', descricao.trim());
    try {
      const r = await fetch(`${BASE}/pacientes/${pacienteId}/anexos`, { method: 'POST', headers: { Authorization: `Bearer ${lerSessao()?.token ?? ''}` }, body: form });
      const corpo = await r.json().catch(() => null);
      if (!r.ok) throw new Error((corpo as { detail?: string })?.detail ?? 'Não foi possível enviar o arquivo.');
      setDescricao('');
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
    setEnviando(false);
    if (arquivoRef.current) arquivoRef.current.value = '';
  };

  const ver = async (a: Anexo) => {
    try {
      setVendo({ anexo: a, url: await abrirArquivo(a.id) });
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const arquivar = async (a: Anexo) => {
    await api(`/anexos/${a.id}/arquivar`, { method: 'POST' }).catch((e: Error) => setErro(e.message));
    setVendo(null);
    carregar();
  };

  return (
    <div className="anexos">
      <div className="anexo-envio">
        <label className="campo">
          <span>Descrição (opcional)</span>
          <input value={descricao} maxLength={300} onChange={(e) => setDescricao(e.target.value)} placeholder="Ex.: Radiografia panorâmica" />
        </label>
        <input ref={arquivoRef} type="file" accept="image/jpeg,image/png,image/webp,application/pdf" className="oculto" aria-label="Escolher arquivo" onChange={(e) => void enviar(e.target.files?.[0])} />
        <button type="button" className="botao secundario" disabled={enviando} onClick={() => arquivoRef.current?.click()}>
          {enviando ? 'Enviando…' : 'Enviar raio-X, foto ou PDF'}
        </button>
        <p className="muted pequeno">Até 10 MB. Os arquivos ficam protegidos: só abrem com o seu login.</p>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}
      {lista && lista.length === 0 && <p className="muted">Nenhum anexo.</p>}
      <ul className="anexo-lista">
        {lista?.map((a) => (
          <li key={a.id}>
            <button type="button" onClick={() => void ver(a)}>
              <span className="anexo-tipo" aria-hidden="true">
                {a.tipo === 'application/pdf' ? 'PDF' : 'IMG'}
              </span>
              <span className="anexo-nome">
                {a.descricao || a.nome}
                {leituras[a.id] && <small className="selo-ia">IA</small>}
              </span>
              <span className="muted pequeno">
                {new Date(a.criado_em).toLocaleDateString('pt-BR')}, {tamanho(a.tamanho)}
              </span>
            </button>
          </li>
        ))}
      </ul>

      {vendo && (
        <div className="painel-fundo" onClick={() => setVendo(null)}>
          <section className="painel painel--largo" role="dialog" aria-label={vendo.anexo.descricao || vendo.anexo.nome} onClick={(e) => e.stopPropagation()}>
            <header className="painel-topo">
              <h2>{vendo.anexo.descricao || vendo.anexo.nome}</h2>
              <button type="button" className="fechar" aria-label="Fechar" onClick={() => setVendo(null)}>
                ×
              </button>
            </header>
            {vendo.anexo.tipo === 'application/pdf' ? (
              <iframe className="anexo-ver" src={vendo.url} title={vendo.anexo.nome} />
            ) : (
              <img className="anexo-ver" src={vendo.url} alt={vendo.anexo.descricao || vendo.anexo.nome} />
            )}
            {erro && (
              <p className="erro" role="alert">
                {erro}
              </p>
            )}
            {leituras[vendo.anexo.id] ? (
              <LeituraIA l={leituras[vendo.anexo.id]} />
            ) : (
              <button type="button" className="botao secundario" disabled={lendo} onClick={() => void lerComIA(vendo.anexo)}>
                {lendo ? 'Lendo o anexo…' : 'Ler com IA'}
              </button>
            )}
            <button type="button" className="link" onClick={() => void arquivar(vendo.anexo)}>
              Arquivar anexo
            </button>
          </section>
        </div>
      )}
    </div>
  );
}

function LeituraIA({ l }: { l: LeituraAnexo }) {
  return (
    <div className="ia-cartao ia-leitura">
      <h3>Leitura da IA · {l.tipo_documento}</h3>
      <p>{l.resumo}</p>
      {l.achados.length > 0 && (
        <ul className="ia-lista">
          {l.achados.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      )}
      {l.pontos_para_conferir.length > 0 && <p className="pequeno"><b>Conferir no original:</b> {l.pontos_para_conferir.join('; ')}</p>}
      {l.texto_extraido && (
        <details>
          <summary>Texto extraído</summary>
          <p className="obs">{l.texto_extraido}</p>
        </details>
      )}
      <p className="muted pequeno">Qualidade da imagem: {l.qualidade}. Sugestão da IA: a avaliação é do dentista.</p>
    </div>
  );
}
