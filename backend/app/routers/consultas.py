from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import auditar, usuario_atual
from ..models import Consulta, Paciente, StatusConsulta, Usuario
from ..schemas import ConsultaIn, ConsultaOut, ConsultaStatus

router = APIRouter(prefix="/consultas", tags=["consultas"])

ATIVAS = (StatusConsulta.agendada, StatusConsulta.confirmada)


def _out(c: Consulta) -> ConsultaOut:
    return ConsultaOut(
        id=c.id, paciente_id=c.paciente_id, paciente_nome=c.paciente.nome, paciente_telefone=c.paciente.telefone,
        inicio=c.inicio, duracao_min=c.duracao_min, procedimento=c.procedimento, status=c.status, observacoes=c.observacoes,
    )


def _consulta(db: Session, u: Usuario, consulta_id: int) -> Consulta:
    c = db.get(Consulta, consulta_id)
    if not c or c.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Consulta não encontrada.")
    return c


def _conflito(db: Session, u: Usuario, dados: ConsultaIn, ignorar_id: int | None = None) -> Consulta | None:
    """Outra consulta ativa que se sobrepõe ao mesmo horário (um dentista, uma cadeira)."""
    if dados.status not in ATIVAS:
        return None
    fim = dados.inicio + timedelta(minutes=dados.duracao_min)
    dia = dados.inicio.date()
    q = select(Consulta).where(
        Consulta.clinica_id == u.clinica_id,
        Consulta.status.in_(ATIVAS),
        Consulta.inicio >= datetime.combine(dia, time.min),
        Consulta.inicio < datetime.combine(dia + timedelta(days=1), time.min),
    )
    for c in db.scalars(q):
        if c.id == ignorar_id:
            continue
        if c.inicio < fim and dados.inicio < c.inicio + timedelta(minutes=c.duracao_min):
            return c
    return None


def _valida(db: Session, u: Usuario, dados: ConsultaIn, ignorar_id: int | None = None) -> None:
    p = db.get(Paciente, dados.paciente_id)
    if not p or p.clinica_id != u.clinica_id:
        raise HTTPException(422, "Paciente não encontrado.")
    c = _conflito(db, u, dados, ignorar_id)
    if c:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe consulta às {c.inicio:%H:%M} com {c.paciente.nome}.")


@router.get("", response_model=list[ConsultaOut])
def listar(
    de: date = Query(...),
    ate: date | None = None,
    paciente_id: int | None = None,
    u: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    fim = ate or de
    if (fim - de).days > 62:
        raise HTTPException(422, "Período máximo: 62 dias.")
    q = (
        select(Consulta)
        .options(joinedload(Consulta.paciente))
        .where(
            Consulta.clinica_id == u.clinica_id,
            Consulta.inicio >= datetime.combine(de, time.min),
            Consulta.inicio < datetime.combine(fim + timedelta(days=1), time.min),
        )
    )
    if paciente_id:
        q = q.where(Consulta.paciente_id == paciente_id)
    return [_out(c) for c in db.scalars(q.order_by(Consulta.inicio))]


@router.post("", response_model=ConsultaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: ConsultaIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _valida(db, u, dados)
    c = Consulta(clinica_id=u.clinica_id, **dados.model_dump())
    db.add(c)
    db.flush()
    auditar(db, u, "criar", "consulta", c.id, request)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.put("/{consulta_id}", response_model=ConsultaOut)
def editar(consulta_id: int, dados: ConsultaIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    c = _consulta(db, u, consulta_id)
    _valida(db, u, dados, ignorar_id=c.id)
    for k, v in dados.model_dump().items():
        setattr(c, k, v)
    auditar(db, u, "editar", "consulta", c.id, request)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.patch("/{consulta_id}/status", response_model=ConsultaOut)
def mudar_status(consulta_id: int, dados: ConsultaStatus, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    c = _consulta(db, u, consulta_id)
    if dados.status in ATIVAS and c.status not in ATIVAS:
        _valida(db, u, ConsultaIn(paciente_id=c.paciente_id, inicio=c.inicio, duracao_min=c.duracao_min, status=dados.status), ignorar_id=c.id)
    c.status = dados.status
    auditar(db, u, f"status:{dados.status.value}", "consulta", c.id, request)
    db.commit()
    return _out(c)
