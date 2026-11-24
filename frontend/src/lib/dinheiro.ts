/** Dinheiro em centavos (inteiros), como a API guarda. */

export const reais = (centavos: number): string =>
  (centavos / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

/** Lê o que a pessoa digitou ("1.234,56", "250", "R$ 80,5") e devolve centavos; null se não for valor. */
export function lerReais(texto: string): number | null {
  const t = texto.replace(/[R$\s]/g, '');
  if (!t) return null;
  const normal = t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : t;
  if (!/^\d+(\.\d{1,2})?$/.test(normal)) return null;
  return Math.round(Number(normal) * 100);
}

/** Valor para mostrar num campo de edição ("250,00"). */
export const paraCampo = (centavos: number): string => (centavos / 100).toFixed(2).replace('.', ',');

export const FORMAS: Record<string, string> = {
  pix: 'Pix',
  dinheiro: 'Dinheiro',
  debito: 'Débito',
  credito: 'Crédito',
  boleto: 'Boleto',
  transferencia: 'Transferência',
};

export const dataCurta = (iso: string): string => {
  const [a, m, d] = iso.split('-');
  return `${d}/${m}/${a}`;
};

/** Link do WhatsApp lembrando uma parcela em aberto. */
export function linkCobranca(nome: string, tel: string | null, valor: number, vencimento: string, clinica: string): string | null {
  const d = (tel ?? '').replace(/\D/g, '');
  if (d.length < 10) return null;
  const numero = d.startsWith('55') && d.length >= 12 ? d : `55${d}`;
  const texto = `Olá, ${nome.split(' ')[0]}! Aqui é do ${clinica}. Passando para lembrar da parcela de ${reais(valor)} com vencimento em ${dataCurta(vencimento)}. Qualquer dúvida, estamos à disposição.`;
  return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
}
