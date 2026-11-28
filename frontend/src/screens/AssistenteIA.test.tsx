import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AssistenteIA } from './AssistenteIA';

function resposta(corpo: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } }));
}

afterEach(() => vi.restoreAllMocks());

describe('AssistenteIA', () => {
  it('avisa quando a IA está desligada', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => resposta({ ativa: false }));
    render(<AssistenteIA pacienteId={1} />);
    expect(await screen.findByText(/IA está desligada/)).toBeInTheDocument();
  });

  it('classifica a triagem e mostra a cor', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url, init) => {
      const u = String(url);
      if (u.endsWith('/ia/status')) return resposta({ ativa: true });
      if (u.includes('/analises')) return resposta([]);
      if (u.endsWith('/triagem') && init?.method === 'POST')
        return resposta({
          id: 1, tipo: 'triagem', anexo_id: null, entrada: 'Rosto inchado', modelo: 'claude-haiku-5-5', criado_em: new Date().toISOString(),
          resultado: { cor: 'vermelho', prazo: 'imediato', motivo: 'Inchaço se espalhando.', sinais_de_alerta: [], orientacao_paciente: 'Procure o pronto-socorro.' },
        }, 201);
      return resposta({});
    });
    render(<AssistenteIA pacienteId={1} />);
    await userEvent.type(await screen.findByLabelText('O que o paciente relatou?'), 'Rosto inchado');
    await userEvent.click(screen.getByRole('button', { name: 'Classificar urgência' }));
    await waitFor(() => expect(screen.getByText('Vermelho · imediato')).toBeInTheDocument());
    expect(screen.getByText(/Procure o pronto-socorro/)).toBeInTheDocument();
  });
});
