"""Senhas (Argon2), tokens (JWT) e limite de tentativas de login."""
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from .config import settings

_ph = PasswordHasher()
ALGORITMO = "HS256"


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def confere_senha(senha: str, hash_: str) -> bool:
    try:
        return _ph.verify(hash_, senha)
    except VerificationError:
        return False
    except Exception:  # hash inválido no banco
        return False


def problema_na_senha(senha: str) -> str | None:
    """Regra mínima: 10+ caracteres, com letra e número."""
    if len(senha) < 10:
        return "A senha precisa de pelo menos 10 caracteres."
    if not re.search(r"[A-Za-zÀ-ÿ]", senha) or not re.search(r"\d", senha):
        return "A senha precisa ter letras e números."
    return None


def criar_token(usuario_id: int, clinica_id: int) -> str:
    agora = datetime.now(timezone.utc)
    payload = {"sub": str(usuario_id), "cli": clinica_id, "iat": agora, "exp": agora + timedelta(minutes=settings().token_minutes)}
    return jwt.encode(payload, settings().secret_key, algorithm=ALGORITMO)


def ler_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings().secret_key, algorithms=[ALGORITMO], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None


class LimiteTentativas:
    """No máximo `maximo` falhas de login por chave (e-mail + IP) a cada `janela` segundos."""

    def __init__(self, maximo: int = 5, janela: int = 15 * 60):
        self.maximo, self.janela = maximo, janela
        self._falhas: dict[str, deque[float]] = defaultdict(deque)

    def _limpa(self, chave: str, agora: float) -> deque[float]:
        q = self._falhas[chave]
        while q and agora - q[0] > self.janela:
            q.popleft()
        return q

    def bloqueado(self, chave: str) -> bool:
        return len(self._limpa(chave, time.monotonic())) >= self.maximo

    def falhou(self, chave: str) -> None:
        self._limpa(chave, time.monotonic()).append(time.monotonic())

    def sucesso(self, chave: str) -> None:
        self._falhas.pop(chave, None)


limite_login = LimiteTentativas()
