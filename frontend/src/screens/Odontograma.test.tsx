import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Odontograma } from './Odontograma';

const json = (corpo: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } }));

describe('Odontograma (interface)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('marca cárie na face oclusal do 16 e salva no servidor', async () => {
    const chamadas: { url: string; body?: string }[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((url, init) => {
      chamadas.push({ url: String(url), body: init?.body as string | undefined });
      return json(init?.method === 'PUT' ? JSON.parse(init.body as string) : []);
    });
    const user = userEvent.setup();
    render(<Odontograma pacienteId={7} />);
    await user.click(await screen.findByRole('button', { name: 'Dente 16, face oclusal' }));
    const put = chamadas.find((c) => c.url.endsWith('/pacientes/7/odontograma/16'));
    expect(JSON.parse(put!.body!)).toEqual({ situacao: 'higido', faces: { O: 'carie' }, observacao: null });
    expect(screen.getByRole('button', { name: 'Dente 16, face oclusal: carie' })).toBeInTheDocument();
    expect(screen.getAllByText('O cárie')).toHaveLength(2); // painel do dente e lista da situação
  });

  it('desfaz na tela se o servidor recusar', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((_u, init) => (init?.method === 'PUT' ? json({ detail: 'Sem conexão' }, 500) : json([])));
    const user = userEvent.setup();
    render(<Odontograma pacienteId={7} />);
    await user.click(await screen.findByRole('radio', { name: 'Ausente' }));
    await user.click(screen.getByRole('button', { name: 'Dente 36, face oclusal' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Não salvou o dente 36');
    expect(screen.queryByText('ausente')).not.toBeInTheDocument();
  });
});
