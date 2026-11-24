# DentFlow

Sistema de gestão para consultório odontológico: pacientes, agenda, prontuário com odontograma, orçamentos,
tratamentos e financeiro. Roda no navegador e vira app Android com o mesmo código.

> Para trocar o nome: `APP_NOME` em `frontend/src/App.tsx`, `<title>` em `frontend/index.html` e `app_name`
> em `backend/app/config.py`.

## O que já funciona

| Área | O que faz |
|---|---|
| Login | E-mail e senha (Argon2), sessão de 12 h, bloqueio após 5 tentativas erradas, mesma resposta para e-mail inexistente |
| Pacientes | Cadastro com validação de CPF e telefone, busca por nome, CPF ou telefone, ficha com histórico de consultas; pacientes são **arquivados, nunca apagados** |
| Agenda | Semana de segunda a sábado e dia como página de agenda (blocos do tamanho da duração); toque num horário vazio para marcar; **impede dois pacientes no mesmo horário**; situação (agendada, confirmada, atendida, faltou, cancelada); confirmação pelo WhatsApp com mensagem pronta |
| Anamnese | Queixa, alergias, medicamentos, condições de saúde e perguntas de sim/não; gera **alertas** que ficam no topo da ficha (alergia, reação à anestesia, hipertensão…) |
| Odontograma | Visão geométrica ou anatômica (coroa e raízes), numeração FDI, dentição permanente e decídua, 5 faces por dente (cárie, restaurado, a restaurar) e situação do dente (canal, coroa, implante, prótese, ausente, a extrair); salva a cada toque e desfaz se o servidor recusar |
| Orçamentos | Gerados a partir do odontograma (cárie/a restaurar e a extrair) com os preços da tabela, ou à mão; desconto; aprovação à vista ou em até 24 parcelas; **aprovado não muda**; "orçamento restante" com o que não foi feito |
| Tratamentos | Itens dos orçamentos aprovados e tratamentos avulsos, com dente e faces; **Finalizar** registra na evolução; ver finalizados |
| Financeiro | Recebido no mês por forma de pagamento, a receber, atrasado; contas a receber com lembrete pelo WhatsApp; pagamento **não se apaga**, estorna com motivo; tabela de preços |
| Evolução | Linha do tempo das anotações clínicas com autor e dentes; **não se edita nem se apaga**: correções viram retificações ligadas à original |
| Anexos | Raio-X, fotos e PDF até 10 MB, tipo conferido pelo conteúdo do arquivo; só abrem com login e cada abertura é auditada |
| Auditoria | Registra quem criou, viu ou alterou cada paciente, consulta, anamnese, dente, anotação e anexo, com data e IP |

## Roadmap

1. ~~Base: login, pacientes e agenda~~
2. ~~Prontuário: anamnese, evolução, odontograma interativo, anexos (raio-X) em armazenamento privado~~
3. ~~Financeiro: orçamento a partir do odontograma, tratamentos, parcelas e contas a receber~~
4. App Android (Capacitor) e publicação (Render + Supabase + Vercel)
5. SaaS: cadastro de novos consultórios (o banco já separa tudo por `clinica_id`)

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, Postgres (SQLite em desenvolvimento), Argon2, JWT
- **Frontend**: React 19 + TypeScript + Vite, CSS próprio (sem framework), fonte Instrument Sans
- **Qualidade**: pytest e Vitest + React Testing Library; GitHub Actions em todo PR; **SonarQube** antes do merge

## Segurança e LGPD

Prontuário é dado de saúde (dado sensível na LGPD). Desde a primeira versão:

- toda tabela de negócio tem `clinica_id`, e um consultório nunca enxerga dado de outro (testado)
- senhas com Argon2; segredos só em variáveis de ambiente; servidor recusa subir sem `SECRET_KEY`
- respostas com `Cache-Control: no-store`, `X-Frame-Options: DENY` e CORS restrito ao site
- trilha de auditoria de acessos e alterações
- paciente não pode ser apagado pela API: a Lei 13.787/2018 exige guarda do prontuário por no mínimo 20 anos

## Rodando localmente

```bash
# backend
cd backend
pip install -r requirements-dev.txt
cp .env.example .env   # preencha SECRET_KEY
python -m app.cli criar-dentista --clinica "Consultório Sorriso" --nome "Dra. Ana" --email ana@exemplo.com
uvicorn app.main:app --reload --port 8000
python -m pytest        # testes

# frontend (outro terminal)
cd frontend
npm install
npm run dev             # http://localhost:5173 (as chamadas /api vão para o backend)
npm test
```

## Estrutura

```
backend/app/
  models.py      tabelas (Clinica, Usuario, Paciente, Consulta, Anamnese, Evolucao, Dente, Anexo, Auditoria)
  routers/       auth, pacientes, consultas, prontuario, financeiro
  armazenamento.py  anexos em pasta privada (troca por bucket privado no deploy)
  security.py    senhas, tokens, limite de tentativas
  cli.py         cria o consultório e o dentista
frontend/src/
  screens/       Login, Agenda, ConsultaForm, Pacientes, Anamnese, Odontograma, Orcamentos, Tratamentos, Evolucao, Anexos, Financeiro
  lib/           cliente da API e formatação (com testes)
ci/              SonarQube
```
