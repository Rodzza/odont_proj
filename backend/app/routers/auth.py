from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import auditar, usuario_atual
from ..models import Clinica, Usuario
from ..schemas import Login, TokenOut, UsuarioOut
from ..security import confere_senha, criar_token, hash_senha, limite_login

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash fixo para gastar o mesmo tempo quando o e-mail não existe (não revela quem tem conta).
_HASH_FALSO = hash_senha("senha-que-nao-existe-123")


@router.post("/login", response_model=TokenOut)
def login(dados: Login, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    chave = f"{dados.email.lower()}|{ip}"
    if limite_login.bloqueado(chave):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Espere 15 minutos e tente de novo.")
    u = db.scalar(select(Usuario).where(Usuario.email == dados.email.lower()))
    ok = confere_senha(dados.senha, u.senha_hash if u else _HASH_FALSO)
    if not u or not ok or not u.ativo:
        limite_login.falhou(chave)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    limite_login.sucesso(chave)
    auditar(db, u, "login", "usuario", u.id, request)
    db.commit()
    clinica = db.get(Clinica, u.clinica_id)
    return TokenOut(token=criar_token(u.id, u.clinica_id), nome=u.nome, clinica=clinica.nome if clinica else "")


@router.get("/eu", response_model=UsuarioOut)
def eu(u: Usuario = Depends(usuario_atual)):
    return u
