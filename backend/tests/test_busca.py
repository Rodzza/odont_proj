"""Busca entre pacientes com embeddings falsos (determinísticos) e Claude simulado."""
import pytest

from app.config import settings
from app.ia import agentes, motor, vetores
from conftest import entrar

PALAVRAS = ["articaína", "anestesia", "reação", "canal", "36", "extração", "implante", "limpeza"]


def falso_embedding(textos, tipo):
    """Vetor = presença de palavras-chave: textos parecidos ficam próximos."""
    out = []
    for t in textos:
        t = t.lower()
        v = [1.0 if p in t else 0.0 for p in PALAVRAS] + [0.01]
        out.append(v + [0.0] * (vetores.DIM - len(v)))
    return out


@pytest.fixture
def busca(monkeypatch):
    monkeypatch.setattr(settings(), "anthropic_api_key", "falsa")
    monkeypatch.setattr(settings(), "voyage_api_key", "falsa")
    monkeypatch.setattr(vetores, "embeddings", falso_embedding)
    chamadas = []

    def rodar(**kw):
        chamadas.append(kw)
        return agentes.RespostaBusca(
            resposta="A Ana teve reação à articaína.",
            pacientes=[agentes.PacienteCitado(paciente_id=1, motivo="reação", fontes=["t1"]), agentes.PacienteCitado(paciente_id=999, motivo="inventado")],
        )

    monkeypatch.setattr(motor, "rodar", rodar)
    return chamadas


def novo(client, auth, nome, cpf=None):
    return client.post("/pacientes", json={"nome": nome, "cpf": cpf}, headers=auth).json()["id"]


def test_indexa_ao_salvar_e_busca_entre_pacientes(client, auth, busca):
    ana = novo(client, auth, "Ana Souza", "52998224725")
    bia = novo(client, auth, "Bia Lima")
    client.post(f"/pacientes/{ana}/evolucoes", headers=auth, json={"texto": "Reação à articaína durante a anestesia."})
    client.post(f"/pacientes/{bia}/evolucoes", headers=auth, json={"texto": "Limpeza e profilaxia."})
    client.put(f"/pacientes/{bia}/anamnese", headers=auth, json={"alergias": "Dipirona"})

    r = client.post("/ia/busca", headers=auth, json={"pergunta": "Quem teve reação à articaína?"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["trechos"][0]["paciente_id"] == ana and corpo["trechos"][0]["origem"].startswith("evolucao:")
    assert [p["paciente_id"] for p in corpo["pacientes"]] == [ana]  # paciente inventado pela IA é descartado
    enviado = busca[0]["mensagem"]
    assert 'paciente="Ana"' in enviado and "Souza" not in enviado and "52998224725" not in enviado


def test_busca_nao_cruza_consultorios(client, auth, busca):
    ana = novo(client, auth, "Ana Souza")
    client.post(f"/pacientes/{ana}/evolucoes", headers=auth, json={"texto": "Reação à articaína."})
    outro = entrar(client, email="beto@outro.com", clinica="Outro")
    r = client.post("/ia/busca", headers=outro, json={"pergunta": "articaína"})
    assert r.json()["trechos"] == [] and busca == []


def test_sem_voyage_salva_prontuario_e_busca_da_503(client, auth, monkeypatch):
    monkeypatch.setattr(settings(), "anthropic_api_key", "falsa")
    monkeypatch.setattr(settings(), "voyage_api_key", "")
    pid = novo(client, auth, "Ana")
    assert client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "Canal no 36"}).status_code == 201
    assert client.post("/ia/busca", headers=auth, json={"pergunta": "canal"}).status_code == 503


def test_falha_no_embedding_nao_impede_salvar(client, auth, monkeypatch):
    monkeypatch.setattr(settings(), "voyage_api_key", "falsa")

    def quebra(textos, tipo):
        raise vetores.BuscaIndisponivel("fora do ar")

    monkeypatch.setattr(vetores, "embeddings", quebra)
    pid = novo(client, auth, "Ana")
    assert client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "Canal no 36"}).status_code == 201


def test_reindexar(client, auth, monkeypatch, busca):
    monkeypatch.setattr(settings(), "voyage_api_key", "")
    pid = novo(client, auth, "Ana")
    client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "Extração do 38"})
    client.put(f"/pacientes/{pid}/anamnese", headers=auth, json={"alergias": "Látex"})
    monkeypatch.setattr(settings(), "voyage_api_key", "falsa")
    assert client.post("/ia/reindexar", headers=auth).json() == {"indexados": 2}
