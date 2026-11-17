from conftest import entrar


def paciente(client, auth, nome="Maria da Silva"):
    return client.post("/pacientes", json={"nome": nome, "telefone": "91988887777"}, headers=auth).json()["id"]


def nova(client, auth, pid, inicio="2026-12-01T09:00", **extra):
    return client.post("/consultas", json={"paciente_id": pid, "inicio": inicio, "duracao_min": 30, **extra}, headers=auth)


def test_agenda_do_dia_em_ordem(client, auth):
    pid = paciente(client, auth)
    nova(client, auth, pid, "2026-12-01T14:00")
    nova(client, auth, pid, "2026-12-01T09:00", procedimento="Limpeza")
    nova(client, auth, pid, "2026-12-02T09:00")
    dia = client.get("/consultas?de=2026-12-01", headers=auth).json()
    assert [c["inicio"][11:16] for c in dia] == ["09:00", "14:00"]
    assert dia[0]["paciente_nome"] == "Maria da Silva" and dia[0]["procedimento"] == "Limpeza"
    assert len(client.get("/consultas?de=2026-12-01&ate=2026-12-07", headers=auth).json()) == 3


def test_nao_deixa_marcar_horario_ocupado(client, auth):
    pid = paciente(client, auth)
    assert nova(client, auth, pid, "2026-12-01T09:00").status_code == 201
    r = nova(client, auth, paciente(client, auth, "João"), "2026-12-01T09:15")
    assert r.status_code == 409 and "09:00" in r.json()["detail"]
    assert nova(client, auth, pid, "2026-12-01T09:30").status_code == 201  # encosta, não sobrepõe


def test_cancelada_libera_o_horario(client, auth):
    pid = paciente(client, auth)
    cid = nova(client, auth, pid).json()["id"]
    client.patch(f"/consultas/{cid}/status", json={"status": "cancelada"}, headers=auth)
    assert nova(client, auth, pid).status_code == 201
    # reativar a cancelada agora bate com a nova
    assert client.patch(f"/consultas/{cid}/status", json={"status": "agendada"}, headers=auth).status_code == 409


def test_fluxo_de_status(client, auth):
    cid = nova(client, auth, paciente(client, auth)).json()["id"]
    for s in ("confirmada", "atendida"):
        assert client.patch(f"/consultas/{cid}/status", json={"status": s}, headers=auth).json()["status"] == s


def test_editar_consulta(client, auth):
    pid = paciente(client, auth)
    cid = nova(client, auth, pid).json()["id"]
    r = client.put(f"/consultas/{cid}", json={"paciente_id": pid, "inicio": "2026-12-01T10:00", "duracao_min": 60}, headers=auth)
    assert r.json()["inicio"].startswith("2026-12-01T10:00") and r.json()["duracao_min"] == 60


def test_isolamento_entre_consultorios(client, auth):
    pid = paciente(client, auth)
    cid = nova(client, auth, pid).json()["id"]
    outro = entrar(client, "beto@outro.com", "Outro")
    assert nova(client, outro, pid).status_code == 422
    assert client.patch(f"/consultas/{cid}/status", json={"status": "cancelada"}, headers=outro).status_code == 404
    assert client.get("/consultas?de=2026-12-01", headers=outro).json() == []


def test_periodo_maximo(client, auth):
    assert client.get("/consultas?de=2026-01-01&ate=2026-12-31", headers=auth).status_code == 422
