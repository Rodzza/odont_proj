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

// Financeiro (centavos)
export interface Procedimento {
  id: number;
  nome: string;
  valor: number;
  ativo: boolean;
  sugere: string | null;
}
export interface ItemOrcamento {
  id?: number;
  descricao: string;
  dente: number | null;
  faces: string | null;
  valor: number;
  quantidade: number;
  feito?: boolean;
}
export interface Parcela {
  id: number;
  orcamento_id: number;
  paciente_id: number;
  numero: number;
  vencimento: string;
  valor: number;
  pago_em: string | null;
  forma: string | null;
  cancelada: boolean;
}
export type StatusOrcamento = 'aberto' | 'aprovado' | 'recusado' | 'cancelado';
export interface Orcamento {
  id: number;
  origem_id: number | null;
  paciente_id: number;
  status: StatusOrcamento;
  itens: ItemOrcamento[];
  subtotal: number;
  desconto: number;
  total: number;
  pago: number;
  observacoes: string | null;
  autor: string;
  criado_em: string;
  aprovado_em: string | null;
  parcelas: Parcela[];
}
export interface ContaReceber extends Parcela {
  paciente_nome: string;
  paciente_telefone: string | null;
  total_parcelas: number;
}
export interface ResumoFinanceiro {
  recebido_periodo: number;
  a_receber: number;
  atrasado: number;
  por_forma: Record<string, number>;
  contas: ContaReceber[];
}
export interface Tratamento {
  id: number;
  orcamento_id: number | null;
  descricao: string;
  dente: number | null;
  faces: string | null;
  dentista: string;
  feito: boolean;
  feito_em: string | null;
  criado_em: string;
}

// IA (Claude)
export type CorTriagem = 'verde' | 'amarelo' | 'laranja' | 'vermelho';
export interface Triagem {
  cor: CorTriagem;
  prazo: string;
  motivo: string;
  sinais_de_alerta: string[];
  orientacao_paciente: string;
}
export interface LeituraAnexo {
  tipo_documento: string;
  resumo: string;
  achados: string[];
  texto_extraido: string;
  pontos_para_conferir: string[];
  qualidade: 'boa' | 'regular' | 'ruim';
}
export interface AnaliseIA<T = unknown> {
  id: number;
  tipo: 'triagem' | 'anexo' | 'resumo';
  anexo_id: number | null;
  entrada: string | null;
  resultado: T;
  modelo: string;
  criado_em: string;
}
export interface FonteIA {
  id: string;
  titulo: string;
  texto: string;
}
export interface ResumoIA {
  resumo: string;
  alertas: string[];
  pendencias: string[];
  historico: string[];
  fontes: string[];
  fontes_detalhe: FonteIA[];
}
export interface RespostaChatIA {
  resposta: string;
  fontes: string[];
  sem_informacao: boolean;
  fontes_detalhe: FonteIA[];
}
export interface MensagemIA {
  papel: 'user' | 'assistant';
  texto: string;
}
export interface BuscaIA {
  resposta: string;
  sem_informacao: boolean;
  pacientes: { paciente_id: number; nome: string; motivo: string; fontes: string[] }[];
  trechos: { id: string; paciente_id: number; paciente_nome: string; origem: string; texto: string; similaridade: number }[];
}
