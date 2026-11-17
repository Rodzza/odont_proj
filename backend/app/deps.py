from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import Auditoria, Usuario
from .security import ler_token

_bearer = HTTPBearer(auto_error=False)


def usuario_atual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> Usuario:
    erro = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre de novo.", headers={"WWW-Authenticate": "Bearer"})
    if not cred:
        raise erro
    dados = ler_token(cred.credentials)
    if not dados:
        raise erro
    u = db.get(Usuario, int(dados["sub"]))
    if not u or not u.ativo or u.clinica_id != dados.get("cli"):
        raise erro
    return u


def auditar(db: Session, u: Usuario, acao: str, entidade: str, entidade_id: int | None, request: Request | None = None) -> None:
    ip = request.client.host if request and request.client else None
    db.add(Auditoria(clinica_id=u.clinica_id, usuario_id=u.id, acao=acao, entidade=entidade, entidade_id=entidade_id, ip=ip))
