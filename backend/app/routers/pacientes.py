from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import auditar, usuario_atual
from ..models import Paciente, Usuario
from ..schemas import PacienteIn, PacienteOut, PacienteResumo

router = APIRouter(prefix="/pacientes", tags=["pacientes"])


def _do_consultorio(db: Session, u: Usuario, paciente_id: int) -> Paciente:
    p = db.get(Paciente, paciente_id)
    # Paciente de outro consultório responde 404, como se não existisse.
    if not p or p.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paciente não encontrado.")
    return p


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um paciente com esse CPF.")


@router.get("", response_model=list[PacienteResumo])
def listar(
    busca: str = Query("", max_length=100),
    arquivados: bool = False,
    limite: int = Query(50, ge=1, le=200),
    u: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    q = select(Paciente).where(Paciente.clinica_id == u.clinica_id, Paciente.arquivado == arquivados)
    termo = busca.strip()
    if termo:
        digitos = "".join(c for c in termo if c.isdigit())
        cond = [func.lower(Paciente.nome).contains(termo.lower())]
        if len(digitos) >= 3:
            cond += [Paciente.cpf.contains(digitos), Paciente.telefone.contains(digitos)]
        q = q.where(or_(*cond))
    return db.scalars(q.order_by(func.lower(Paciente.nome)).limit(limite)).all()


@router.post("", response_model=PacienteOut, status_code=status.HTTP_201_CREATED)
def criar(dados: PacienteIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = Paciente(clinica_id=u.clinica_id, **dados.model_dump())
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um paciente com esse CPF.")
    auditar(db, u, "criar", "paciente", p.id, request)
    _salvar(db)
    return p


@router.get("/{paciente_id}", response_model=PacienteOut)
def ver(paciente_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = _do_consultorio(db, u, paciente_id)
    auditar(db, u, "ver", "paciente", p.id, request)
    db.commit()
    return p


@router.put("/{paciente_id}", response_model=PacienteOut)
def editar(paciente_id: int, dados: PacienteIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = _do_consultorio(db, u, paciente_id)
    for k, v in dados.model_dump().items():
        setattr(p, k, v)
    auditar(db, u, "editar", "paciente", p.id, request)
    _salvar(db)
    return p


@router.post("/{paciente_id}/arquivar", response_model=PacienteOut)
def arquivar(paciente_id: int, request: Request, arquivar: bool = True, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Não existe apagar: prontuário tem guarda mínima legal. Arquivar tira das listas."""
    p = _do_consultorio(db, u, paciente_id)
    p.arquivado = arquivar
    auditar(db, u, "arquivar" if arquivar else "desarquivar", "paciente", p.id, request)
    db.commit()
    return p
