/** Cliente da API. O token fica no aparelho e expira no servidor (12 h). */
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '/api';
const KEY = 'odonto.sessao';

export interface Sessao {
  token: string;
  nome: string;
  clinica: string;
}

export const lerSessao = (): Sessao | null => {
  try {
    const s = localStorage.getItem(KEY);
    return s ? (JSON.parse(s) as Sessao) : null;
  } catch {
    return null;
  }
};
export const salvarSessao = (s: Sessao | null) => {
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {
    /* sem armazenamento: sessão só na memória */
  }
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let aoExpirar: () => void = () => {};
export const quandoSessaoExpirar = (f: () => void) => {
  aoExpirar = f;
};

function mensagem(corpo: unknown, status: number): string {
  const d = (corpo as { detail?: unknown })?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg).replace(/^Value error, /, '');
  if (status >= 500) return 'O servidor não respondeu. Tente de novo em instantes.';
  return 'Não deu certo. Confira os dados e tente de novo.';
}

export async function api<T>(caminho: string, opcoes: { method?: string; body?: unknown } = {}): Promise<T> {
  const sessao = lerSessao();
  let r: Response;
  try {
    r = await fetch(`${BASE}${caminho}`, {
      method: opcoes.method ?? 'GET',
      headers: { 'Content-Type': 'application/json', ...(sessao ? { Authorization: `Bearer ${sessao.token}` } : {}) },
      body: opcoes.body === undefined ? undefined : JSON.stringify(opcoes.body),
    });
  } catch {
    throw new ApiError(0, 'Sem conexão com o servidor. Confira a internet.');
  }
  const corpo = r.status === 204 ? null : await r.json().catch(() => null);
  if (r.status === 401 && sessao) {
    salvarSessao(null);
    aoExpirar();
  }
  if (!r.ok) throw new ApiError(r.status, mensagem(corpo, r.status));
  return corpo as T;
}

// Tipos da API
export type Status = 'agendada' | 'confirmada' | 'atendida' | 'faltou' | 'cancelada';

export interface PacienteResumo {
  id: number;
  nome: string;
  telefone: string | null;
  nascimento: string | null;
  arquivado: boolean;
}
export interface Paciente extends PacienteResumo {
  cpf: string | null;
  email: string | null;
  endereco: string | null;
  responsavel: string | null;
  observacoes: string | null;
}
export type PacienteIn = Omit<Paciente, 'id' | 'arquivado'>;

export interface Consulta {
  id: number;
  paciente_id: number;
  paciente_nome: string;
  paciente_telefone: string | null;
  inicio: string;
  duracao_min: number;
  procedimento: string | null;
  status: Status;
  observacoes: string | null;
}
export interface ConsultaIn {
  paciente_id: number;
  inicio: string;
  duracao_min: number;
  procedimento: string | null;
  status: Status;
  observacoes: string | null;
}
