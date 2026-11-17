"""Prontuário: anamnese, evolução clínica, odontograma e anexos."""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import armazenamento
from ..config import settings
from ..db import get_db
from ..deps import auditar, usuario_atual
from ..models import Anamnese, Anexo, Dente, Evolucao, Usuario
from ..schemas import AnamneseIn, AnamneseOut, AnexoOut, DenteIn, DenteOut, EvolucaoIn, EvolucaoOut, DENTES_VALIDOS
from .pacientes import _do_consultorio

router = APIRouter(tags=["prontuário"])

ROTULO_DOENCA = {
    "diabetes": "Diabetes", "hipertensao": "Hipertensão", "cardiopatia": "Cardiopatia", "asma": "Asma",
    "epilepsia": "Epilepsia", "hepatite": "Hepatite", "problemas_renais": "Problemas renais",
    "disturbio_coagulacao": "Distúrbio de coagulação", "osteoporose": "Osteoporose", "ansiedade": "Ansiedade",
}
DOENCAS_ALERTA = {"diabetes", "hipertensao", "cardiopatia", "disturbio_coagulacao", "epilepsia", "hepatite"}


def alertas(a: AnamneseIn) -> list[str]:
    """O que o dentista precisa ver antes de atender (aparece em destaque na ficha)."""
    out = []
    if a.alergias and a.alergias.strip():
        out.append(f"Alergia: {a.alergias.strip()}")
    if a.reacao_anestesia:
        out.append("Já teve reação à anestesia")
    if a.sangramento_excessivo:
        out.append("Sangramento excessivo")
    if a.gestante:
        out.append("Gestante")
    out += [ROTULO_DOENCA[d] for d in a.doencas if d in DOENCAS_ALERTA]
    return out


# ---------- Anamnese ----------


@router.get("/pacientes/{paciente_id}/anamnese", response_model=AnamneseOut)
def ver_anamnese(paciente_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    a = db.scalar(select(Anamnese).where(Anamnese.paciente_id == paciente_id))
    dados = AnamneseIn(**json.loads(a.respostas)) if a else AnamneseIn()
    auditar(db, u, "ver", "anamnese", paciente_id, request)
    db.commit()
    return AnamneseOut(**dados.model_dump(), atualizado_em=a.atualizado_em if a else None, alertas=alertas(dados))


@router.put("/pacientes/{paciente_id}/anamnese", response_model=AnamneseOut)
def salvar_anamnese(paciente_id: int, dados: AnamneseIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    a = db.scalar(select(Anamnese).where(Anamnese.paciente_id == paciente_id))
    if not a:
        a = Anamnese(clinica_id=u.clinica_id, paciente_id=paciente_id)
        db.add(a)
    a.respostas = dados.model_dump_json()
    a.atualizado_por = u.id
    auditar(db, u, "editar", "anamnese", paciente_id, request)
    db.commit()
    db.refresh(a)
    return AnamneseOut(**dados.model_dump(), atualizado_em=a.atualizado_em, alertas=alertas(dados))


# ---------- Evolução (imutável) ----------


def _evolucao_out(e: Evolucao, autores: dict[int, str], retificadas: dict[int, int]) -> EvolucaoOut:
    return EvolucaoOut(
        id=e.id, texto=e.texto, dentes=[int(x) for x in e.dentes.split(",")] if e.dentes else [],
        retifica_id=e.retifica_id, retificada_por=retificadas.get(e.id), autor=autores.get(e.usuario_id, "?"), criado_em=e.criado_em,
    )


@router.get("/pacientes/{paciente_id}/evolucoes", response_model=list[EvolucaoOut])
def listar_evolucoes(paciente_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    itens = list(db.scalars(select(Evolucao).where(Evolucao.paciente_id == paciente_id).order_by(Evolucao.criado_em.desc(), Evolucao.id.desc())))
    autores = {x.id: x.nome for x in db.scalars(select(Usuario).where(Usuario.clinica_id == u.clinica_id))}
    retificadas = {e.retifica_id: e.id for e in itens if e.retifica_id}
    auditar(db, u, "ver", "evolucao", paciente_id, request)
    db.commit()
    return [_evolucao_out(e, autores, retificadas) for e in itens]


@router.post("/pacientes/{paciente_id}/evolucoes", response_model=EvolucaoOut, status_code=status.HTTP_201_CREATED)
def criar_evolucao(paciente_id: int, dados: EvolucaoIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    if dados.retifica_id:
        orig = db.get(Evolucao, dados.retifica_id)
        if not orig or orig.paciente_id != paciente_id:
            raise HTTPException(422, "A anotação a retificar não é deste paciente.")
    e = Evolucao(
        clinica_id=u.clinica_id, paciente_id=paciente_id, usuario_id=u.id, texto=dados.texto.strip(),
        dentes=",".join(map(str, dados.dentes)) or None, retifica_id=dados.retifica_id,
    )
    db.add(e)
    db.flush()
    auditar(db, u, "criar", "evolucao", e.id, request)
    db.commit()
    return _evolucao_out(e, {u.id: u.nome}, {})


# ---------- Odontograma ----------


@router.get("/pacientes/{paciente_id}/odontograma", response_model=list[DenteOut])
def ver_odontograma(paciente_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    dentes = db.scalars(select(Dente).where(Dente.paciente_id == paciente_id).order_by(Dente.numero))
    return [DenteOut(numero=d.numero, situacao=d.situacao, faces=json.loads(d.faces), observacao=d.observacao) for d in dentes]


@router.put("/pacientes/{paciente_id}/odontograma/{numero}", response_model=DenteOut)
def salvar_dente(paciente_id: int, numero: int, dados: DenteIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    if numero not in DENTES_VALIDOS:
        raise HTTPException(422, f"Dente {numero} não existe na numeração FDI.")
    faces = {} if dados.situacao in ("ausente", "implante") else dados.faces  # dente que não existe não tem face
    d = db.scalar(select(Dente).where(Dente.paciente_id == paciente_id, Dente.numero == numero))
    if not d:
        d = Dente(clinica_id=u.clinica_id, paciente_id=paciente_id, numero=numero)
        db.add(d)
    d.situacao, d.faces, d.observacao = dados.situacao, json.dumps(faces, sort_keys=True), dados.observacao
    auditar(db, u, "editar", f"dente:{numero}", paciente_id, request)
    db.commit()
    return DenteOut(numero=numero, situacao=d.situacao, faces=faces, observacao=d.observacao)


# ---------- Anexos (privados) ----------


def _anexo(db: Session, u: Usuario, anexo_id: int) -> Anexo:
    a = db.get(Anexo, anexo_id)
    if not a or a.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anexo não encontrado.")
    return a


@router.get("/pacientes/{paciente_id}/anexos", response_model=list[AnexoOut])
def listar_anexos(paciente_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    return db.scalars(select(Anexo).where(Anexo.paciente_id == paciente_id, Anexo.arquivado.is_(False)).order_by(Anexo.criado_em.desc()))


@router.post("/pacientes/{paciente_id}/anexos", response_model=AnexoOut, status_code=status.HTTP_201_CREATED)
async def enviar_anexo(
    paciente_id: int,
    request: Request,
    arquivo: UploadFile = File(...),
    descricao: str | None = Form(default=None, max_length=300),
    u: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    _do_consultorio(db, u, paciente_id)
    limite = settings().anexo_max_mb * 1024 * 1024
    dados = await arquivo.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(413, f"Arquivo maior que {settings().anexo_max_mb} MB.")
    tipo = armazenamento.tipo_pelo_conteudo(dados)
    if not tipo:
        raise HTTPException(415, "Envie uma imagem (JPG, PNG, WEBP) ou um PDF.")
    nome = (arquivo.filename or "anexo").replace("/", "_").replace("\\", "_")[:200]
    a = Anexo(
        clinica_id=u.clinica_id, paciente_id=paciente_id, usuario_id=u.id, nome=nome, descricao=(descricao or "").strip() or None,
        tipo=tipo, tamanho=len(dados), chave=armazenamento.salvar(u.clinica_id, dados),
    )
    db.add(a)
    db.flush()
    auditar(db, u, "enviar", "anexo", a.id, request)
    db.commit()
    return a


@router.get("/anexos/{anexo_id}/arquivo")
def baixar_anexo(anexo_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    a = _anexo(db, u, anexo_id)
    try:
        dados = armazenamento.ler(a.clinica_id, a.chave)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado no armazenamento.")
    auditar(db, u, "abrir", "anexo", a.id, request)
    db.commit()
    return Response(dados, media_type=a.tipo, headers={"Content-Disposition": "inline", "Cache-Control": "no-store"})


@router.post("/anexos/{anexo_id}/arquivar", response_model=AnexoOut)
def arquivar_anexo(anexo_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Tira da lista, mas o arquivo continua guardado (faz parte do prontuário)."""
    a = _anexo(db, u, anexo_id)
    a.arquivado = True
    auditar(db, u, "arquivar", "anexo", a.id, request)
    db.commit()
    return a
