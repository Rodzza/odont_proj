"""Rotas das funções de IA. Toda chamada é auditada (dado de saúde enviado a um serviço externo)."""
import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import armazenamento
from ..db import get_db
from ..deps import auditar, usuario_atual
from ..ia import agentes, motor, secretaria
from ..ia.contexto import como_texto, fontes_do_paciente, identificacao
from ..models import AnaliseIA, Anexo, Usuario
from ..config import settings
from .pacientes import _do_consultorio

router = APIRouter(prefix="/ia", tags=["ia"])


class Mensagem(BaseModel):
    papel: Literal["user", "assistant"]
    texto: str = Field(max_length=4000)


class TriagemIn(BaseModel):
    queixa: str = Field(min_length=3, max_length=2000)


class ChatIn(BaseModel):
    pergunta: str = Field(min_length=2, max_length=2000)
    historico: list[Mensagem] = Field(default_factory=list, max_length=30)


class FonteOut(BaseModel):
    id: str
    titulo: str
    texto: str


class ChatOut(agentes.RespostaChat):
    fontes_detalhe: list[FonteOut] = Field(default_factory=list)


class ResumoOut(agentes.Resumo):
    fontes_detalhe: list[FonteOut] = Field(default_factory=list)


class SecretariaIn(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    historico: list[Mensagem] = Field(default_factory=list, max_length=30)


class SecretariaOut(BaseModel):
    resposta: str
    consultas_marcadas: list[int]


class AnaliseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: str
    anexo_id: int | None
    entrada: str | None
    resultado: dict
    modelo: str
    criado_em: datetime


def _analise_out(a: AnaliseIA) -> AnaliseOut:
    return AnaliseOut(id=a.id, tipo=a.tipo, anexo_id=a.anexo_id, entrada=a.entrada, resultado=json.loads(a.resultado), modelo=a.modelo, criado_em=a.criado_em)


def _guardar(db: Session, u: Usuario, paciente_id: int, tipo: str, resultado: BaseModel, rapido=False, entrada=None, anexo_id=None) -> AnaliseIA:
    a = AnaliseIA(
        clinica_id=u.clinica_id, paciente_id=paciente_id, usuario_id=u.id, tipo=tipo, anexo_id=anexo_id,
        entrada=entrada, resultado=resultado.model_dump_json(), modelo=motor.nome_modelo(rapido),
    )
    db.add(a)
    db.flush()
    return a


@router.get("/status")
def ia_status(u: Usuario = Depends(usuario_atual)):
    cfg = settings()
    return {"ativa": bool(cfg.anthropic_api_key), "modelo": cfg.ia_modelo, "modelo_rapido": cfg.ia_modelo_rapido}


@router.post("/pacientes/{paciente_id}/triagem", response_model=AnaliseOut, status_code=status.HTTP_201_CREATED)
def triagem(paciente_id: int, dados: TriagemIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = _do_consultorio(db, u, paciente_id)
    # Para a triagem basta identificação + anamnese (alertas); o resto do prontuário não é necessário.
    fontes = [f for f in fontes_do_paciente(db, p) if f.id == "anamnese"]
    r = agentes.triagem(dados.queixa.strip(), como_texto(p, fontes))
    a = _guardar(db, u, p.id, "triagem", r, rapido=True, entrada=dados.queixa.strip())
    auditar(db, u, "ia:triagem", "paciente", p.id, request)
    db.commit()
    return _analise_out(a)


@router.post("/anexos/{anexo_id}/ler", response_model=AnaliseOut, status_code=status.HTTP_201_CREATED)
def ler_anexo(anexo_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    an = db.get(Anexo, anexo_id)
    if not an or an.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anexo não encontrado.")
    motor.modelo()  # falha cedo (503) se a IA estiver desligada, antes de ler o arquivo
    try:
        dados = armazenamento.ler(an.clinica_id, an.chave)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado no armazenamento.")
    r = agentes.ler_anexo(dados, an.tipo, an.descricao)
    a = _guardar(db, u, an.paciente_id, "anexo", r, anexo_id=an.id)
    auditar(db, u, "ia:ler", "anexo", an.id, request)
    db.commit()
    return _analise_out(a)


@router.post("/pacientes/{paciente_id}/resumo", response_model=ResumoOut)
def resumo(paciente_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = _do_consultorio(db, u, paciente_id)
    fontes = fontes_do_paciente(db, p)
    if not fontes:
        raise HTTPException(422, "O prontuário ainda está vazio: preencha anamnese, odontograma ou evolução primeiro.")
    r = agentes.resumo(como_texto(p, fontes))
    _guardar(db, u, p.id, "resumo", r)
    auditar(db, u, "ia:resumo", "paciente", p.id, request)
    db.commit()
    por_id = {f.id: f for f in fontes}
    return ResumoOut(**r.model_dump(), fontes_detalhe=[FonteOut(**vars(por_id[i])) for i in r.fontes if i in por_id])


@router.post("/pacientes/{paciente_id}/chat", response_model=ChatOut)
def chat(paciente_id: int, dados: ChatIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = _do_consultorio(db, u, paciente_id)
    fontes = fontes_do_paciente(db, p)
    texto = como_texto(p, fontes) if fontes else identificacao(p) + "\n\n(Prontuário vazio.)"
    r = agentes.chat(texto, [(m.papel, m.texto) for m in dados.historico], dados.pergunta.strip())
    auditar(db, u, "ia:chat", "paciente", p.id, request)
    db.commit()
    por_id = {f.id: f for f in fontes}
    return ChatOut(**r.model_dump(), fontes_detalhe=[FonteOut(**vars(por_id[i])) for i in r.fontes if i in por_id])


@router.get("/pacientes/{paciente_id}/analises", response_model=list[AnaliseOut])
def listar_analises(paciente_id: int, tipo: str | None = None, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    q = select(AnaliseIA).where(AnaliseIA.paciente_id == paciente_id)
    if tipo:
        q = q.where(AnaliseIA.tipo == tipo)
    return [_analise_out(a) for a in db.scalars(q.order_by(AnaliseIA.criado_em.desc(), AnaliseIA.id.desc()).limit(50))]


@router.post("/secretaria", response_model=SecretariaOut)
def falar_secretaria(dados: SecretariaIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    texto, marcadas = secretaria.conversar(db, u, [(m.papel, m.texto) for m in dados.historico], dados.mensagem.strip(), request)
    auditar(db, u, "ia:secretaria", "agenda", None, request)
    db.commit()
    return SecretariaOut(resposta=texto, consultas_marcadas=marcadas)
