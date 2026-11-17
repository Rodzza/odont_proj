"""Cria o consultório e o dentista (primeiro acesso).

Uso: python -m app.cli criar-dentista --clinica "Consultório X" --nome "Dra. Ana" --email ana@ex.com [--cro "CRO-PA 1234"]
A senha é pedida no terminal (não fica no histórico).
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import Clinica, Usuario
from .security import hash_senha, problema_na_senha


def criar_dentista(clinica: str, nome: str, email: str, senha: str, cro: str | None = None) -> Usuario:
    Base.metadata.create_all(engine)
    erro = problema_na_senha(senha)
    if erro:
        raise ValueError(erro)
    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(Usuario.email == email.lower())):
            raise ValueError("Já existe um usuário com esse e-mail.")
        c = db.scalar(select(Clinica).where(Clinica.nome == clinica)) or Clinica(nome=clinica)
        db.add(c)
        db.flush()
        u = Usuario(clinica_id=c.id, nome=nome, email=email.lower(), senha_hash=hash_senha(senha), cro=cro)
        db.add(u)
        db.commit()
        return u


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("criar-dentista")
    c.add_argument("--clinica", required=True)
    c.add_argument("--nome", required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--cro")
    a = p.parse_args()
    senha = getpass.getpass("Senha (10+ caracteres, letras e números): ")
    if senha != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas não conferem.")
    try:
        u = criar_dentista(a.clinica, a.nome, a.email, senha, a.cro)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Pronto: {u.nome} ({u.email}) pode entrar no sistema.")


if __name__ == "__main__":
    main()
