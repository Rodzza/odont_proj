import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Login } from './Login';

const resposta = (status: number, corpo: unknown) => Promise.resolve(new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } }));

describe('Login (interface)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('mostra a mensagem do servidor quando a senha está errada', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => resposta(401, { detail: 'E-mail ou senha incorretos.' }));
    const user = userEvent.setup();
    const onEntrar = vi.fn();
    render(<Login onEntrar={onEntrar} />);
    await user.type(screen.getByLabelText('E-mail'), 'ana@consultorio.com');
    await user.type(screen.getByLabelText('Senha'), 'errada');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha incorretos.');
    expect(onEntrar).not.toHaveBeenCalled();
  });

  it('entra e devolve a sessão', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => resposta(200, { token: 't', nome: 'Dra. Ana', clinica: 'Sorriso' }));
    const user = userEvent.setup();
    const onEntrar = vi.fn();
    render(<Login onEntrar={onEntrar} />);
    await user.type(screen.getByLabelText('E-mail'), 'ana@consultorio.com');
    await user.type(screen.getByLabelText('Senha'), 'SenhaForte123');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));
    await vi.waitFor(() => expect(onEntrar).toHaveBeenCalledWith({ token: 't', nome: 'Dra. Ana', clinica: 'Sorriso' }));
  });

  it('botão desabilitado sem e-mail e senha', () => {
    render(<Login onEntrar={() => {}} />);
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeDisabled();
  });
});
