import os
import sys
import tempfile

import pytest

# Banco temporário e chave de teste ANTES de importar o app.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/teste.db"
os.environ["PASTA_ANEXOS"] = f"{_tmp}/anexos"
os.environ["SECRET_KEY"] = "chave-de-teste-com-mais-de-32-caracteres!!"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from app.cli import criar_dentista  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import limite_login  # noqa: E402

SENHA = "SenhaForte123"


@pytest.fixture(autouse=True)
def banco_limpo():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limite_login._falhas.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def entrar(client, email="ana@consultorio.com", clinica="Consultório Sorriso"):
    criar_dentista(clinica, "Dra. Ana", email, SENHA, "CRO-PA 1234")
    r = client.post("/auth/login", json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def auth(client):
    return entrar(client)
