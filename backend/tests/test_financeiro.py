from datetime import date, timedelta

from conftest import entrar

from app.routers.financeiro import _mes_seguinte, dividir


def paciente(client, auth, nome="Maria da Silva"):
    return client.post("/pacientes", json={"nome": nome, "telefone": "91988887777"}, headers=auth).json()["id"]


def orcamento(client, auth, pid, itens=None, desconto=0):
    itens = itens or [{"descricao": "Restauração", "dente": 16, "valor": 25000}, {"descricao": "Limpeza", "valor": 15000}]
    r = client.post(f"/pacientes/{pid}/orcamentos", headers=auth, json={"itens": itens, "desconto": desconto})
    assert r.status_code == 201, r.text
    return r.json()


def test_divisao_de_parcelas_nao_perde_centavo():
    assert dividir(10000, 3) == [3334, 3333, 3333]
    assert sum(dividir(99999, 7)) == 99999


def test_vencimento_no_fim_do_mes():
    assert _mes_seguinte(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert _mes_seguinte(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_tabela_de_precos_vem_com_padrao_e_edita(client, auth):
    procs = client.get("/procedimentos", headers=auth).json()
    assert len(procs) >= 5 and all(p["valor"] == 0 for p in procs)
    rest = next(p for p in procs if p["sugere"] == "restauracao")
    r = client.put(f"/procedimentos/{rest['id']}", headers=auth, json={"nome": rest["nome"], "valor": 18000})
    assert r.json()["valor"] == 18000


def test_sugestao_a_partir_do_odontograma(client, auth):
    pid = paciente(client, auth)
    procs = client.get("/procedimentos", headers=auth).json()
    for p in procs:
        if p["sugere"]:
            client.put(f"/procedimentos/{p['id']}", headers=auth, json={"nome": p["nome"], "valor": 10000})
    client.put(f"/pacientes/{pid}/odontograma/16", headers=auth, json={"situacao": "higido", "faces": {"O": "carie", "M": "restaurar", "V": "restaurado"}})
    client.put(f"/pacientes/{pid}/odontograma/38", headers=auth, json={"situacao": "extrair", "faces": {}})
    client.put(f"/pacientes/{pid}/odontograma/11", headers=auth, json={"situacao": "coroa", "faces": {}})
    itens = client.get(f"/pacientes/{pid}/orcamentos/sugestao", headers=auth).json()
    assert [(i["dente"], i["valor"], i["faces"]) for i in itens] == [(16, 10000, "MO"), (38, 10000, None)]
    assert itens[0]["descricao"].endswith("2 faces")


def test_orcamento_totais_e_desconto(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid, desconto=5000)
    assert (o["subtotal"], o["total"], o["status"]) == (40000, 35000, "aberto")
    r = client.post(f"/pacientes/{pid}/orcamentos", headers=auth, json={"itens": [{"descricao": "X", "valor": 100}], "desconto": 200})
    assert r.status_code == 422


def test_aprovar_gera_parcelas_e_trava_edicao(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid)
    r = client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={
        "parcelas": 3, "primeiro_vencimento": date.today().isoformat(), "entrada_paga": True, "forma_entrada": "pix"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["status"] == "aprovado" and [p["valor"] for p in a["parcelas"]] == [13334, 13333, 13333]
    assert a["parcelas"][0]["pago_em"] == date.today().isoformat() and a["pago"] == 13334
    assert client.put(f"/orcamentos/{o['id']}", headers=auth, json={"itens": [{"descricao": "Outro", "valor": 1}]}).status_code == 409
    assert client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={"parcelas": 1, "primeiro_vencimento": "2026-01-01"}).status_code == 409


def test_nao_aprova_orcamento_sem_preco(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid, itens=[{"descricao": "Avaliação", "valor": 0}])
    assert client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={"parcelas": 1, "primeiro_vencimento": "2026-12-01"}).status_code == 422


def test_pagar_estornar_e_contas_a_receber(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid)
    venc = date.today() - timedelta(days=20)  # 1ª atrasada, 2ª ainda não venceu
    a = client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={"parcelas": 2, "primeiro_vencimento": venc.isoformat()}).json()
    p1, p2 = a["parcelas"]

    res = client.get(f"/financeiro?de={date.today().replace(day=1)}&ate={date.today()}", headers=auth).json()
    assert res["a_receber"] == 40000 and res["atrasado"] == 20000 and res["recebido_periodo"] == 0
    assert res["contas"][0]["paciente_nome"] == "Maria da Silva" and res["contas"][0]["total_parcelas"] == 2

    hoje = date.today().isoformat()
    assert client.post(f"/parcelas/{p1['id']}/pagar", headers=auth, json={"forma": "dinheiro", "pago_em": hoje}).status_code == 200
    assert client.post(f"/parcelas/{p1['id']}/pagar", headers=auth, json={"forma": "pix", "pago_em": hoje}).status_code == 409
    futuro = (date.today() + timedelta(days=1)).isoformat()
    assert client.post(f"/parcelas/{p2['id']}/pagar", headers=auth, json={"forma": "pix", "pago_em": futuro}).status_code == 422
    assert client.post(f"/parcelas/{p2['id']}/pagar", headers=auth, json={"forma": "cheque", "pago_em": hoje}).status_code == 422

    res = client.get(f"/financeiro?de={hoje}&ate={hoje}", headers=auth).json()
    assert res["recebido_periodo"] == 20000 and res["por_forma"] == {"dinheiro": 20000} and res["atrasado"] == 0

    assert client.post(f"/parcelas/{p1['id']}/estornar", headers=auth, json={"motivo": ""}).status_code == 422
    r = client.post(f"/parcelas/{p1['id']}/estornar", headers=auth, json={"motivo": "Lançado no paciente errado"})
    assert r.status_code == 200 and r.json()["pago_em"] is None


def test_cancelar_tira_parcelas_abertas_da_cobranca(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid)
    a = client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={
        "parcelas": 2, "primeiro_vencimento": date.today().isoformat(), "entrada_paga": True, "forma_entrada": "debito"}).json()
    c = client.post(f"/orcamentos/{o['id']}/cancelar", headers=auth).json()
    assert c["status"] == "cancelado" and c["pago"] == a["parcelas"][0]["valor"]
    res = client.get(f"/financeiro?de={date.today()}&ate={date.today()}", headers=auth).json()
    assert res["a_receber"] == 0 and res["recebido_periodo"] == a["parcelas"][0]["valor"]


def test_tratamentos_finalizar_registra_evolucao(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid, itens=[{"descricao": "Restauração 2 faces", "dente": 21, "faces": "vm", "valor": 20000}, {"descricao": "Limpeza", "valor": 12000}])
    assert client.get(f"/pacientes/{pid}/tratamentos", headers=auth).json() == []  # orçamento ainda não aprovado
    client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={"parcelas": 1, "primeiro_vencimento": "2026-12-01"})
    trats = client.get(f"/pacientes/{pid}/tratamentos", headers=auth).json()
    assert [(t["descricao"], t["faces"], t["dentista"]) for t in trats] == [("Restauração 2 faces", "VM", "Dra. Ana"), ("Limpeza", None, "Dra. Ana")]

    r = client.post(f"/tratamentos/{trats[0]['id']}/finalizar", headers=auth)
    assert r.status_code == 200 and r.json()["feito"] and r.json()["feito_em"]
    assert client.post(f"/tratamentos/{trats[0]['id']}/finalizar", headers=auth).status_code == 409
    evo = client.get(f"/pacientes/{pid}/evolucoes", headers=auth).json()[0]
    assert evo["texto"] == "Tratamento finalizado: Restauração 2 faces (faces VM)" and evo["dentes"] == [21]

    assert len(client.get(f"/pacientes/{pid}/tratamentos", headers=auth).json()) == 1
    assert len(client.get(f"/pacientes/{pid}/tratamentos?finalizados=true", headers=auth).json()) == 1
    assert client.post(f"/tratamentos/{trats[0]['id']}/reabrir", headers=auth).json()["feito"] is False


def test_tratamento_avulso(client, auth):
    pid = paciente(client, auth)
    r = client.post(f"/pacientes/{pid}/tratamentos", headers=auth, json={"descricao": "Contenção fixa inferior"})
    assert r.status_code == 201 and r.json()["orcamento_id"] is None
    assert client.post(f"/pacientes/{pid}/tratamentos", headers=auth, json={"descricao": "X", "faces": "Z"}).status_code == 422
    assert len(client.get(f"/pacientes/{pid}/tratamentos", headers=auth).json()) == 1


def test_orcamento_restante_com_o_que_nao_foi_feito(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid)
    assert client.post(f"/orcamentos/{o['id']}/restante", headers=auth).status_code == 409  # ainda em aberto
    a = client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={"parcelas": 1, "primeiro_vencimento": "2026-12-01"}).json()
    client.post(f"/tratamentos/{a['itens'][0]['id']}/finalizar", headers=auth)
    client.post(f"/orcamentos/{o['id']}/cancelar", headers=auth)
    r = client.post(f"/orcamentos/{o['id']}/restante", headers=auth)
    assert r.status_code == 201, r.text
    novo = r.json()
    assert novo["status"] == "aberto" and novo["origem_id"] == o["id"] and [i["descricao"] for i in novo["itens"]] == ["Limpeza"]


def test_outro_consultorio_nao_ve_nada(client, auth):
    pid = paciente(client, auth)
    o = orcamento(client, auth, pid)
    a = client.post(f"/orcamentos/{o['id']}/aprovar", headers=auth, json={"parcelas": 1, "primeiro_vencimento": "2026-12-01"}).json()
    outro = entrar(client, "bia@outro.com", "Outro Consultório")
    assert client.get(f"/pacientes/{pid}/orcamentos", headers=outro).status_code == 404
    assert client.post(f"/orcamentos/{o['id']}/recusar", headers=outro).status_code == 404
    assert client.post(f"/parcelas/{a['parcelas'][0]['id']}/pagar", headers=outro, json={"forma": "pix", "pago_em": "2026-01-01"}).status_code == 404
    assert client.get("/financeiro?de=2020-01-01&ate=2030-01-01", headers=outro).json()["a_receber"] == 0
    assert all(p["valor"] == 0 for p in client.get("/procedimentos", headers=outro).json())
