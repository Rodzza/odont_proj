"""Secretária autônoma: conversa com o dentista e marca consultas na agenda do DentFlow.

No workshop ela usava GoogleCalendarTools; aqui as ferramentas são funções Python que usam
a mesma validação da agenda (impede dois pacientes no mesmo horário) e ficam presas ao
consultório de quem está logado.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import auditar
from ..models import Clinica, Consulta, Paciente, StatusConsulta, Usuario
from ..routers.consultas import ATIVAS, _valida
from ..schemas import ConsultaIn
from . import motor

ABRE, FECHA, PASSO_MIN = time(8, 0), time(18, 0), 30
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


class Ferramentas:
    """Ferramentas da secretária, ligadas ao banco e ao usuário da requisição."""

    def __init__(self, db: Session, u: Usuario, request: Request | None = None):
        self.db, self.u, self.request = db, u, request
        self.marcadas: list[int] = []

    # Cada método público abaixo vira uma ferramenta do agente (docstring = descrição para o Claude).

    def buscar_paciente(self, nome: str) -> str:
        """Procura pacientes pelo nome (ou parte dele). Devolve id, nome e ano de nascimento."""
        q = select(Paciente).where(
            Paciente.clinica_id == self.u.clinica_id, Paciente.arquivado.is_(False), Paciente.nome.ilike(f"%{nome.strip()}%")
        ).limit(8)
        ps = list(self.db.scalars(q))
        if not ps:
            return f"Nenhum paciente encontrado com '{nome}'."
        return "\n".join(f"id={p.id} | {p.nome}" + (f" | nasc. {p.nascimento.year}" if p.nascimento else "") for p in ps)

    def consultas_do_dia(self, dia: str) -> str:
        """Lista as consultas de um dia (formato AAAA-MM-DD)."""
        d = _dia(dia)
        cs = self._do_dia(d, todas=True)
        if not cs:
            return f"Nenhuma consulta em {_fmt_dia(d)}."
        return "\n".join(f"{c.inicio:%H:%M} ({c.duracao_min} min) — {c.paciente.nome} — {c.procedimento or 'sem procedimento'} — {c.status.value}" for c in cs)

    def horarios_livres(self, dia: str, duracao_min: int = 30) -> str:
        """Horários livres num dia (AAAA-MM-DD) para uma consulta com a duração dada, no expediente de 08:00 às 18:00, segunda a sábado."""
        d = _dia(dia)
        if d.weekday() == 6:
            return "O consultório não atende aos domingos."
        ocupadas = [(c.inicio, c.inicio + timedelta(minutes=c.duracao_min)) for c in self._do_dia(d)]
        agora = _agora(self.db, self.u)
        livres = []
        t = datetime.combine(d, ABRE)
        while t + timedelta(minutes=duracao_min) <= datetime.combine(d, FECHA):
            fim = t + timedelta(minutes=duracao_min)
            if t > agora and not any(i < fim and t < f for i, f in ocupadas):
                livres.append(f"{t:%H:%M}")
            t += timedelta(minutes=PASSO_MIN)
        return f"Livres em {_fmt_dia(d)}: " + (", ".join(livres) if livres else "nenhum horário.")

    def marcar_consulta(self, paciente_id: int, inicio: str, duracao_min: int = 30, procedimento: str = "") -> str:
        """Marca uma consulta. `inicio` no formato AAAA-MM-DDTHH:MM (horário do consultório).
        Só use DEPOIS que o dentista confirmar paciente, dia, hora e procedimento."""
        try:
            dados = ConsultaIn(
                paciente_id=paciente_id, inicio=datetime.fromisoformat(inicio), duracao_min=duracao_min,
                procedimento=procedimento.strip() or None, status=StatusConsulta.agendada,
                observacoes="Marcada pela secretária (IA).",
            )
            _valida(self.db, self.u, dados)
        except HTTPException as e:
            return f"NÃO marcada: {e.detail}"
        except ValueError as e:
            return f"NÃO marcada: dados inválidos ({e})."
        c = Consulta(clinica_id=self.u.clinica_id, **dados.model_dump())
        self.db.add(c)
        self.db.flush()
        auditar(self.db, self.u, "criar:ia", "consulta", c.id, self.request)
        self.db.commit()
        self.marcadas.append(c.id)
        p = self.db.get(Paciente, paciente_id)
        return f"Marcada: {p.nome}, {_fmt_dia(c.inicio.date())} às {c.inicio:%H:%M}, {c.duracao_min} min (consulta id={c.id})."

    def lista(self) -> list:
        return [self.buscar_paciente, self.consultas_do_dia, self.horarios_livres, self.marcar_consulta]

    def _do_dia(self, d: date, todas: bool = False) -> list[Consulta]:
        q = select(Consulta).where(
            Consulta.clinica_id == self.u.clinica_id,
            Consulta.inicio >= datetime.combine(d, time.min),
            Consulta.inicio < datetime.combine(d + timedelta(days=1), time.min),
        )
        if not todas:
            q = q.where(Consulta.status.in_(ATIVAS))
        return list(self.db.scalars(q.order_by(Consulta.inicio)))


def _dia(s: str) -> date:
    return date.fromisoformat(s.strip()[:10])


def _fmt_dia(d: date) -> str:
    return f"{DIAS[d.weekday()]}, {d:%d/%m/%Y}"


def _agora(db: Session, u: Usuario) -> datetime:
    c = db.get(Clinica, u.clinica_id)
    return datetime.now(ZoneInfo(c.fuso if c else "America/Belem")).replace(tzinfo=None)


def conversar(db: Session, u: Usuario, historico: list[tuple[str, str]], mensagem: str, request: Request | None = None) -> tuple[str, list[int]]:
    f = Ferramentas(db, u, request)
    agora = _agora(db, u)
    instrucoes = [
        "Você é a secretária do consultório odontológico e fala com o(a) dentista em português do Brasil, de forma curta.",
        f"Agora é {_fmt_dia(agora.date())}, {agora:%H:%M} (horário do consultório). Expediente: segunda a sábado, 08:00 às 18:00.",
        "Use as ferramentas para buscar pacientes, ver a agenda e horários livres. Nunca invente ids nem horários.",
        "Se houver mais de um paciente com o nome, pergunte qual. Se o paciente não existir, diga que precisa ser cadastrado antes.",
        "ANTES de marcar, repita paciente, dia, hora, duração e procedimento e peça confirmação. Só chame marcar_consulta depois de um 'sim'.",
        "Você não cancela nem remarca consultas: oriente o dentista a fazer isso pela agenda.",
    ]
    conversa = "\n".join(f"{'Dentista' if quem == 'user' else 'Secretária'}: {txt}" for quem, txt in historico[-12:])
    msg = (f"Conversa até aqui:\n{conversa}\n\n" if conversa else "") + f"Dentista: {mensagem}"
    texto = motor.rodar(instrucoes=instrucoes, mensagem=msg, ferramentas=f.lista())
    return str(texto), f.marcadas
