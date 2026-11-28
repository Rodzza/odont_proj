"""Funções de IA com o Claude simulado (os testes nunca chamam a API de verdade)."""
from datetime import date, datetime, timedelta

import pytest

from app.config import settings
from app.ia import agentes, motor
from conftest import entrar

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


class Falso:
    """Substitui motor.rodar: guarda o que foi enviado e devolve uma resposta pronta."""

    def __init__(self):
        self.chamadas: list[dict] = []
        self.respostas: dict[type | None, object] = {}

    def __call__(self, **kw):
        self.chamadas.append(kw)
        return self.respostas[kw.get("esquema")]


@pytest.fixture
def ia(monkeypatch):
    monkeypatch.setattr(settings(), "anthropic_api_key", "chave-falsa")
    f = Falso()
    monkeypatch.setattr(motor, "rodar", f)
    return f


def paciente(client, auth, **extra):
    dados = {"nome": "Maria da Silva", "cpf": "52998224725", "telefone": "91988887777", "nascimento": "1990-05-10", **extra}
    r = client.post("/pacientes", json=dados, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_ia_desligada_responde_503(client, auth, monkeypatch):
    monkeypatch.setattr(settings(), "anthropic_api_key", "")
    pid = paciente(client, auth)
    assert client.get("/ia/status", headers=auth).json()["ativa"] is False
    r = client.post(f"/ia/pacientes/{pid}/triagem", headers=auth, json={"queixa": "dor de dente"})
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_triagem_usa_alertas_e_nao_envia_dados_pessoais(client, auth, ia):
    pid = paciente(client, auth)
    client.put(f"/pacientes/{pid}/anamnese", headers=auth, json={"alergias": "Penicilina", "doencas": ["disturbio_coagulacao"]})
    ia.respostas[agentes.Triagem] = agentes.Triagem(
        cor="laranja", prazo="hoje", motivo="Dor intensa com distúrbio de coagulação.", sinais_de_alerta=["dor contínua"], orientacao_paciente="Venha hoje.",
    )
    r = client.post(f"/ia/pacientes/{pid}/triagem", headers=auth, json={"queixa": "Dor forte no dente de trás desde ontem"})
    assert r.status_code == 201, r.text
    assert r.json()["resultado"]["cor"] == "laranja" and r.json()["tipo"] == "triagem"
    enviado = ia.chamadas[0]["mensagem"]
    assert ia.chamadas[0]["rapido"] is True
    assert "Penicilina" in enviado and "Distúrbio de coagulação" in enviado
    assert "Maria," in enviado and "Silva" not in enviado
    assert "52998224725" not in enviado and "91988887777" not in enviado
    hist = client.get(f"/ia/pacientes/{pid}/analises?tipo=triagem", headers=auth).json()
    assert len(hist) == 1 and hist[0]["entrada"].startswith("Dor forte")


def test_ler_anexo_guarda_leitura_e_entra_no_chat(client, auth, ia):
    pid = paciente(client, auth)
    an = client.post(f"/pacientes/{pid}/anexos", headers=auth, files={"arquivo": ("rx.png", PNG, "image/png")}, data={"descricao": "Panorâmica"}).json()
    ia.respostas[agentes.LeituraAnexo] = agentes.LeituraAnexo(
        tipo_documento="radiografia panorâmica", resumo="Lesão periapical sugestiva no 36.", achados=["36: radiolucidez periapical"], qualidade="boa",
    )
    r = client.post(f"/ia/anexos/{an['id']}/ler", headers=auth)
    assert r.status_code == 201, r.text
    assert ia.chamadas[0]["imagens"] and ia.chamadas[0]["imagens"][0].content == PNG

    ia.respostas[agentes.RespostaChat] = agentes.RespostaChat(resposta="Há suspeita de lesão no 36.", fontes=[f"anexo:{an['id']}", "inventada:1"])
    r = client.post(f"/ia/pacientes/{pid}/chat", headers=auth, json={"pergunta": "Tem algo no 36?"})
    assert r.status_code == 200, r.text
    assert f'<fonte id="anexo:{an["id"]}"' in ia.chamadas[1]["mensagem"]
    detalhe = r.json()["fontes_detalhe"]
    assert [f["id"] for f in detalhe] == [f"anexo:{an['id']}"]  # fonte inventada pela IA é descartada


def test_resumo_exige_prontuario_e_cita_fontes(client, auth, ia):
    pid = paciente(client, auth)
    assert client.post(f"/ia/pacientes/{pid}/resumo", headers=auth).status_code == 422
    e = client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "Restauração oclusal", "dentes": [16]}).json()
    client.put(f"/pacientes/{pid}/odontograma/26", headers=auth, json={"situacao": "extrair", "faces": {}})
    ia.respostas[agentes.Resumo] = agentes.Resumo(resumo="Paciente em tratamento.", pendencias=["Extrair 26"], fontes=[f"evolucao:{e['id']}", "odontograma"])
    r = client.post(f"/ia/pacientes/{pid}/resumo", headers=auth)
    assert r.status_code == 200, r.text
    assert {f["id"] for f in r.json()["fontes_detalhe"]} == {f"evolucao:{e['id']}", "odontograma"}
    assert "Dente 26: extrair" in ia.chamadas[0]["mensagem"]


def test_paciente_de_outro_consultorio_nao_vaza(client, auth, ia):
    pid = paciente(client, auth)
    outro = entrar(client, email="beto@outro.com", clinica="Outro")
    assert client.post(f"/ia/pacientes/{pid}/chat", headers=outro, json={"pergunta": "oi?"}).status_code == 404
    assert client.post(f"/ia/pacientes/{pid}/triagem", headers=outro, json={"queixa": "dor"}).status_code == 404
    assert ia.chamadas == []


# ---------- Secretária: ferramentas testadas direto, sem IA ----------


def _ferramentas(client, auth):
    from app.db import SessionLocal
    from app.ia.secretaria import Ferramentas
    from app.models import Usuario

    db = SessionLocal()
    u = db.query(Usuario).first()
    return db, Ferramentas(db, u)


def _proximo_dia_util():
    d = date.today() + timedelta(days=1)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


def test_secretaria_ferramentas_respeitam_a_agenda(client, auth):
    pid = paciente(client, auth)
    d = _proximo_dia_util()
    client.post("/consultas", headers=auth, json={"paciente_id": pid, "inicio": f"{d}T09:00", "duracao_min": 60})
    db, f = _ferramentas(client, auth)
    try:
        assert f"id={pid} | Maria da Silva" in f.buscar_paciente("maria")
        livres = f.horarios_livres(d.isoformat(), 30)
        assert "08:30" in livres and "09:00" not in livres and "09:30" not in livres and "10:00" in livres
        assert "NÃO marcada" in f.marcar_consulta(pid, f"{d}T09:30", 30, "Limpeza")
        ok = f.marcar_consulta(pid, f"{d}T10:00", 30, "Limpeza")
        assert ok.startswith("Marcada") and len(f.marcadas) == 1
        assert "Limpeza" in f.consultas_do_dia(d.isoformat())
    finally:
        db.close()
    consultas = client.get(f"/consultas?de={d}", headers=auth).json()
    assert [c["inicio"][11:16] for c in consultas] == ["09:00", "10:00"]


def test_secretaria_nao_ve_outro_consultorio(client, auth):
    paciente(client, auth)
    entrar(client, email="beto@outro.com", clinica="Outro")
    from app.db import SessionLocal
    from app.ia.secretaria import Ferramentas
    from app.models import Usuario

    db = SessionLocal()
    try:
        beto = db.query(Usuario).filter_by(email="beto@outro.com").one()
        assert "Nenhum paciente" in Ferramentas(db, beto).buscar_paciente("Maria")
    finally:
        db.close()


def test_rota_secretaria(client, auth, ia, monkeypatch):
    from app.ia import secretaria

    monkeypatch.setattr(secretaria, "conversar", lambda db, u, hist, msg, req: ("Posso marcar às 10h?", []))
    r = client.post("/ia/secretaria", headers=auth, json={"mensagem": "Marca a Maria amanhã", "historico": []})
    assert r.status_code == 200 and r.json()["resposta"] == "Posso marcar às 10h?"
