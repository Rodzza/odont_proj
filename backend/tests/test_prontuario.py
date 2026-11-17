import io

from conftest import entrar

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
PDF = b"%PDF-1.7\n" + b"x" * 50


def paciente(client, auth):
    return client.post("/pacientes", json={"nome": "Maria da Silva"}, headers=auth).json()["id"]


# ---------- Anamnese ----------

def test_anamnese_vazia_e_salva_com_alertas(client, auth):
    pid = paciente(client, auth)
    assert client.get(f"/pacientes/{pid}/anamnese", headers=auth).json()["alertas"] == []
    r = client.put(f"/pacientes/{pid}/anamnese", headers=auth, json={
        "alergias": "Penicilina", "doencas": ["hipertensao", "asma"], "reacao_anestesia": True, "fumante": True,
    })
    assert r.status_code == 200, r.text
    alertas = r.json()["alertas"]
    assert "Alergia: Penicilina" in alertas and "Hipertensão" in alertas and "Já teve reação à anestesia" in alertas
    assert "Asma" not in alertas  # registrada, mas não é alerta de atendimento
    assert client.get(f"/pacientes/{pid}/anamnese", headers=auth).json()["alergias"] == "Penicilina"


def test_anamnese_recusa_condicao_desconhecida(client, auth):
    pid = paciente(client, auth)
    assert client.put(f"/pacientes/{pid}/anamnese", headers=auth, json={"doencas": ["inventada"]}).status_code == 422


# ---------- Evolução ----------

def test_evolucao_e_imutavel_e_aceita_retificacao(client, auth):
    pid = paciente(client, auth)
    r = client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "Restauração na face oclusal", "dentes": [16, 16, 17]})
    assert r.status_code == 201
    e = r.json()
    assert e["dentes"] == [16, 17] and e["autor"] == "Dra. Ana"
    assert client.put(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "x"}).status_code == 405
    ret = client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "Correção: era o dente 26", "retifica_id": e["id"]}).json()
    lista = client.get(f"/pacientes/{pid}/evolucoes", headers=auth).json()
    assert [x["id"] for x in lista] == [ret["id"], e["id"]]  # mais recente primeiro
    assert lista[1]["retificada_por"] == ret["id"]


def test_evolucao_valida_dente_fdi(client, auth):
    pid = paciente(client, auth)
    assert client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "abc", "dentes": [19]}).status_code == 422
    assert client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "abc", "dentes": [55]}).status_code == 201


def test_retificacao_de_outro_paciente_e_recusada(client, auth):
    a, b = paciente(client, auth), paciente(client, auth)
    eid = client.post(f"/pacientes/{a}/evolucoes", headers=auth, json={"texto": "abc"}).json()["id"]
    assert client.post(f"/pacientes/{b}/evolucoes", headers=auth, json={"texto": "abc", "retifica_id": eid}).status_code == 422


# ---------- Odontograma ----------

def test_odontograma_salva_dente_e_faces(client, auth):
    pid = paciente(client, auth)
    assert client.get(f"/pacientes/{pid}/odontograma", headers=auth).json() == []
    r = client.put(f"/pacientes/{pid}/odontograma/16", headers=auth, json={"situacao": "higido", "faces": {"O": "carie", "M": "restaurado"}})
    assert r.json()["faces"] == {"O": "carie", "M": "restaurado"}
    client.put(f"/pacientes/{pid}/odontograma/16", headers=auth, json={"situacao": "canal", "faces": {"O": "restaurado"}})
    dentes = client.get(f"/pacientes/{pid}/odontograma", headers=auth).json()
    assert dentes == [{"numero": 16, "situacao": "canal", "faces": {"O": "restaurado"}, "observacao": None}]


def test_dente_ausente_perde_as_faces(client, auth):
    pid = paciente(client, auth)
    r = client.put(f"/pacientes/{pid}/odontograma/36", headers=auth, json={"situacao": "ausente", "faces": {"O": "carie"}})
    assert r.json()["faces"] == {}


def test_odontograma_valida(client, auth):
    pid = paciente(client, auth)
    assert client.put(f"/pacientes/{pid}/odontograma/99", headers=auth, json={}).status_code == 422
    assert client.put(f"/pacientes/{pid}/odontograma/11", headers=auth, json={"situacao": "quebrado"}).status_code == 422
    assert client.put(f"/pacientes/{pid}/odontograma/11", headers=auth, json={"faces": {"X": "carie"}}).status_code == 422


# ---------- Anexos ----------

def test_anexo_envia_lista_e_baixa_com_login(client, auth):
    pid = paciente(client, auth)
    r = client.post(f"/pacientes/{pid}/anexos", headers=auth, files={"arquivo": ("raio-x.png", io.BytesIO(PNG), "image/png")}, data={"descricao": "Panorâmica"})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["tipo"] == "image/png" and a["descricao"] == "Panorâmica"
    assert client.get(f"/anexos/{a['id']}/arquivo").status_code == 401
    baixado = client.get(f"/anexos/{a['id']}/arquivo", headers=auth)
    assert baixado.content == PNG and baixado.headers["cache-control"] == "no-store"
    client.post(f"/anexos/{a['id']}/arquivar", headers=auth)
    assert client.get(f"/pacientes/{pid}/anexos", headers=auth).json() == []


def test_anexo_confere_conteudo_nao_extensao(client, auth):
    pid = paciente(client, auth)
    falso = client.post(f"/pacientes/{pid}/anexos", headers=auth, files={"arquivo": ("foto.png", io.BytesIO(b"<script>alert(1)</script>"), "image/png")})
    assert falso.status_code == 415
    pdf = client.post(f"/pacientes/{pid}/anexos", headers=auth, files={"arquivo": ("exame.txt", io.BytesIO(PDF), "text/plain")})
    assert pdf.json()["tipo"] == "application/pdf"


def test_anexo_limite_de_tamanho(client, auth, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings(), "anexo_max_mb", 0)
    pid = paciente(client, auth)
    assert client.post(f"/pacientes/{pid}/anexos", headers=auth, files={"arquivo": ("a.png", io.BytesIO(PNG), "image/png")}).status_code == 413


def test_prontuario_isolado_entre_consultorios(client, auth):
    pid = paciente(client, auth)
    aid = client.post(f"/pacientes/{pid}/anexos", headers=auth, files={"arquivo": ("a.png", io.BytesIO(PNG), "image/png")}).json()["id"]
    outro = entrar(client, "beto@outro.com", "Outro")
    for metodo, url in [("get", f"/pacientes/{pid}/anamnese"), ("get", f"/pacientes/{pid}/evolucoes"), ("get", f"/pacientes/{pid}/odontograma"), ("get", f"/anexos/{aid}/arquivo")]:
        assert getattr(client, metodo)(url, headers=outro).status_code == 404, url


def test_horarios_saem_com_fuso_utc(client, auth):
    """Sem o fuso, o navegador mostrava a anotação 3 horas adiantada."""
    pid = paciente(client, auth)
    e = client.post(f"/pacientes/{pid}/evolucoes", headers=auth, json={"texto": "abc"}).json()
    assert e["criado_em"].endswith(("Z", "+00:00"))
    assert client.put(f"/pacientes/{pid}/anamnese", headers=auth, json={}).json()["atualizado_em"].endswith(("Z", "+00:00"))
