/** Formatação e regras de tela (sem React), testáveis. */
import type { Status } from './api';

export const STATUS: Record<Status, { rotulo: string; ativa: boolean }> = {
  agendada: { rotulo: 'Agendada', ativa: true },
  confirmada: { rotulo: 'Confirmada', ativa: true },
  atendida: { rotulo: 'Atendida', ativa: false },
  faltou: { rotulo: 'Faltou', ativa: false },
  cancelada: { rotulo: 'Cancelada', ativa: false },
};

export const telefone = (t: string | null): string => {
  if (!t) return '';
  const d = t.replace(/\D/g, '');
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return t;
};

export const cpf = (c: string | null): string => (c && c.length === 11 ? `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6, 9)}-${c.slice(9)}` : c ?? '');

export function idade(nasc: string | null, hoje = new Date()): number | null {
  if (!nasc) return null;
  const [a, m, d] = nasc.split('-').map(Number);
  let i = hoje.getFullYear() - a!;
  if (hoje.getMonth() + 1 < m! || (hoje.getMonth() + 1 === m && hoje.getDate() < d!)) i--;
  return i;
}

/** YYYY-MM-DD no horário local. */
export const isoDia = (d: Date): string => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export const somaDias = (d: Date, n: number): Date => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};

/** Segunda a sábado da semana de `d`. */
export const semana = (d: Date): Date[] => {
  const seg = somaDias(d, -((d.getDay() + 6) % 7));
  return Array.from({ length: 6 }, (_, i) => somaDias(seg, i));
};

export const hora = (iso: string): string => iso.slice(11, 16);
export const minutosDoDia = (iso: string): number => Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16));

export const diaLongo = (d: Date): string => d.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });

/** Link do WhatsApp para confirmar a consulta, com a mensagem pronta. */
export function linkConfirmacao(nome: string, tel: string | null, inicio: string, clinica: string): string | null {
  const d = (tel ?? '').replace(/\D/g, '');
  if (d.length < 10) return null;
  const numero = d.startsWith('55') && d.length >= 12 ? d : `55${d}`;
  const data = new Date(`${inicio.slice(0, 10)}T12:00:00`).toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
  const primeiro = nome.split(' ')[0];
  const texto = `Olá, ${primeiro}! Aqui é do ${clinica}. Confirmando sua consulta ${data}, às ${hora(inicio)}. Responda SIM para confirmar ou nos avise se precisar remarcar.`;
  return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
}
