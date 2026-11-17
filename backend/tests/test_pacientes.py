from sqlalchemy import select

from app.db import SessionLocal
from app.models import Auditoria
from conftest import entrar

MARIA = {"nome": "Maria  da Silva", "cpf": "529.982.247-25", "telefone": "(91) 98888-7777", "nascimento": "1990-05-10"}


def test_cadastra_normaliza_e_busca(client, auth):
    r = client.post("/pacientes", json=MARIA, headers=auth)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["nome"] == "Maria da Silva" and p["cpf"] == "52998224725" and p["telefone"] == "91988887777"
    assert [x["nome"] for x in client.get("/pacientes?busca=maria", headers=auth).json()] == ["Maria da Silva"]
    assert len(client.get("/pacientes?busca=988887", headers=auth).json()) == 1
    assert client.get("/pacientes?busca=joao", headers=auth).json() == []


def test_valida_cpf_telefone_e_data(client, auth):
    assert client.post("/pacientes", json={**MARIA, "cpf": "111.111.111-11"}, headers=auth).status_code == 422
    assert client.post("/pacientes", json={**MARIA, "telefone": "123"}, headers=auth).status_code == 422
    assert client.post("/pacientes", json={**MARIA, "nascimento": "2999-01-01"}, headers=auth).status_code == 422


def test_cpf_repetido(client, auth):
    client.post("/pacientes", json=MARIA, headers=auth)
    assert client.post("/pacientes", json={**MARIA, "nome": "Outra"}, headers=auth).status_code == 409


def test_arquiva_em_vez_de_apagar(client, auth):
    pid = client.post("/pacientes", json=MARIA, headers=auth).json()["id"]
    assert client.delete(f"/pacientes/{pid}", headers=auth).status_code == 405
    client.post(f"/pacientes/{pid}/arquivar", headers=auth)
    assert client.get("/pacientes", headers=auth).json() == []
    assert len(client.get("/pacientes?arquivados=true", headers=auth).json()) == 1
    assert client.get(f"/pacientes/{pid}", headers=auth).status_code == 200


def test_outro_consultorio_nao_ve_meus_pacientes(client, auth):
    pid = client.post("/pacientes", json=MARIA, headers=auth).json()["id"]
    outro = entrar(client, "beto@outro.com", "Outro Consultório")
    assert client.get(f"/pacientes/{pid}", headers=outro).status_code == 404
    assert client.put(f"/pacientes/{pid}", json=MARIA, headers=outro).status_code == 404
    assert client.get("/pacientes", headers=outro).json() == []


def test_registra_auditoria(client, auth):
    pid = client.post("/pacientes", json=MARIA, headers=auth).json()["id"]
    client.get(f"/pacientes/{pid}", headers=auth)
    with SessionLocal() as db:
        acoes = [a.acao for a in db.scalars(select(Auditoria).where(Auditoria.entidade == "paciente"))]
    assert acoes == ["criar", "ver"]
