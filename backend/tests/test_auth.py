from app.security import problema_na_senha
from conftest import SENHA


def test_login_errado_nao_revela_se_email_existe(client, auth):
    a = client.post("/auth/login", json={"email": "ana@consultorio.com", "senha": "errada123456"})
    b = client.post("/auth/login", json={"email": "ninguem@x.com", "senha": "errada123456"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_bloqueia_depois_de_5_tentativas(client, auth):
    for _ in range(5):
        client.post("/auth/login", json={"email": "ana@consultorio.com", "senha": "errada123456"})
    r = client.post("/auth/login", json={"email": "ana@consultorio.com", "senha": SENHA})
    assert r.status_code == 429


def test_rotas_exigem_login(client):
    assert client.get("/pacientes").status_code == 401
    assert client.get("/pacientes", headers={"Authorization": "Bearer token-falso"}).status_code == 401


def test_quem_sou_eu(client, auth):
    r = client.get("/auth/eu", headers=auth)
    assert r.json()["nome"] == "Dra. Ana"
    assert "senha_hash" not in r.json()


def test_regra_de_senha():
    assert problema_na_senha("curta1")
    assert problema_na_senha("semnumerosaqui")
    assert problema_na_senha("1234567890")
    assert problema_na_senha("SenhaForte123") is None


def test_cabecalhos_de_seguranca(client):
    r = client.get("/health")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"
