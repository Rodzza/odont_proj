"""Financeiro: tabela de preços, orçamentos (a partir do odontograma), parcelas e contas a receber.

Regras de dinheiro:
- valores em centavos (inteiros);
- orçamento aprovado não muda de itens nem de valor (é o que o paciente aceitou);
- pagamento não se apaga: corrige-se com estorno, que fica registrado na auditoria com o motivo.
"""
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import auditar, usuario_atual
from ..models import Dente, Evolucao, ItemOrcamento, Orcamento, Paciente, Parcela, Procedimento, Usuario
from ..schemas import (
    Aprovacao,
    ContaReceber,
    Estorno,
    ItemIn,
    OrcamentoIn,
    OrcamentoOut,
    Pagamento,
    ParcelaOut,
    ProcedimentoIn,
    ProcedimentoOut,
    ResumoFinanceiro,
    TratamentoIn,
    TratamentoOut,
)
from .pacientes import _do_consultorio

router = APIRouter(tags=["financeiro"])

# Primeira vez que o consultório abre a tabela: nomes comuns, preço a definir pelo dentista.
PADRAO = [
    ("Avaliação", None), ("Limpeza (profilaxia)", None), ("Restauração em resina", "restauracao"),
    ("Extração simples", "extracao"), ("Tratamento de canal", None), ("Clareamento", None),
    ("Coroa", None), ("Raspagem por quadrante", None),
]


# ---------- Tabela de preços ----------


def _procedimentos(db: Session, u: Usuario) -> list[Procedimento]:
    itens = list(db.scalars(select(Procedimento).where(Procedimento.clinica_id == u.clinica_id).order_by(Procedimento.nome)))
    if not itens:
        db.add_all(Procedimento(clinica_id=u.clinica_id, nome=n, valor=0, sugere=s) for n, s in PADRAO)
        db.commit()
        itens = list(db.scalars(select(Procedimento).where(Procedimento.clinica_id == u.clinica_id).order_by(Procedimento.nome)))
    return itens


@router.get("/procedimentos", response_model=list[ProcedimentoOut])
def listar_procedimentos(u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return _procedimentos(db, u)


@router.post("/procedimentos", response_model=ProcedimentoOut, status_code=201)
def criar_procedimento(dados: ProcedimentoIn, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = Procedimento(clinica_id=u.clinica_id, **dados.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/procedimentos/{proc_id}", response_model=ProcedimentoOut)
def editar_procedimento(proc_id: int, dados: ProcedimentoIn, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = db.get(Procedimento, proc_id)
    if not p or p.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Procedimento não encontrado.")
    for k, v in dados.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


# ---------- Orçamentos ----------


def _orcamento(db: Session, u: Usuario, orc_id: int) -> Orcamento:
    o = db.get(Orcamento, orc_id)
    if not o or o.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Orçamento não encontrado.")
    return o


def _subtotal(itens) -> int:
    return sum(i.valor * i.quantidade for i in itens)


def _out(o: Orcamento, autores: dict[int, str]) -> OrcamentoOut:
    sub = _subtotal(o.itens)
    parcelas = [p for p in o.parcelas if not p.cancelada] if o.status != "cancelado" else list(o.parcelas)
    return OrcamentoOut(
        id=o.id, paciente_id=o.paciente_id, status=o.status, itens=o.itens, subtotal=sub, desconto=o.desconto,
        origem_id=o.origem_id, total=sub - o.desconto, pago=sum(p.valor for p in o.parcelas if p.pago_em), observacoes=o.observacoes,
        autor=autores.get(o.usuario_id, "?"), criado_em=o.criado_em, aprovado_em=o.aprovado_em, parcelas=parcelas,
    )


def _autores(db: Session, u: Usuario) -> dict[int, str]:
    return {x.id: x.nome for x in db.scalars(select(Usuario).where(Usuario.clinica_id == u.clinica_id))}


def _itens(dados: OrcamentoIn, u: Usuario, paciente_id: int) -> list[ItemOrcamento]:
    return [ItemOrcamento(clinica_id=u.clinica_id, paciente_id=paciente_id, dentista_id=u.id, **i.model_dump()) for i in dados.itens]


def _validar(dados: OrcamentoIn) -> None:
    if dados.desconto > _subtotal(dados.itens):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "O desconto não pode ser maior que o valor do orçamento.")


@router.get("/pacientes/{paciente_id}/orcamentos", response_model=list[OrcamentoOut])
def listar_orcamentos(paciente_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    itens = db.scalars(select(Orcamento).where(Orcamento.paciente_id == paciente_id).order_by(Orcamento.criado_em.desc(), Orcamento.id.desc()))
    autores = _autores(db, u)
    return [_out(o, autores) for o in itens]


@router.get("/pacientes/{paciente_id}/orcamentos/sugestao", response_model=list[ItemIn])
def sugerir_do_odontograma(paciente_id: int, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Itens a partir do que está marcado como pendente no odontograma: cárie/a restaurar e dente a extrair."""
    _do_consultorio(db, u, paciente_id)
    procs = {p.sugere: p for p in _procedimentos(db, u) if p.sugere and p.ativo}
    out: list[ItemIn] = []
    for d in db.scalars(select(Dente).where(Dente.paciente_id == paciente_id).order_by(Dente.numero)):
        if d.situacao == "extrair":
            p = procs.get("extracao")
            out.append(ItemIn(descricao=p.nome if p else "Extração", dente=d.numero, valor=p.valor if p else 0))
            continue
        faces = [f for f, e in json.loads(d.faces or "{}").items() if e in ("carie", "restaurar")]
        if faces:
            p = procs.get("restauracao")
            nome = p.nome if p else "Restauração"
            n = len(faces)
            out.append(ItemIn(descricao=f"{nome} {n} {'face' if n == 1 else 'faces'}", dente=d.numero, faces="".join(faces), valor=p.valor if p else 0))
    return out


@router.post("/pacientes/{paciente_id}/orcamentos", response_model=OrcamentoOut, status_code=201)
def criar_orcamento(paciente_id: int, dados: OrcamentoIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    _do_consultorio(db, u, paciente_id)
    _validar(dados)
    o = Orcamento(clinica_id=u.clinica_id, paciente_id=paciente_id, usuario_id=u.id, desconto=dados.desconto, observacoes=dados.observacoes)
    o.itens = _itens(dados, u, paciente_id)
    db.add(o)
    db.flush()
    auditar(db, u, "criar", "orcamento", o.id, request)
    db.commit()
    db.refresh(o)
    return _out(o, _autores(db, u))


@router.put("/orcamentos/{orc_id}", response_model=OrcamentoOut)
def editar_orcamento(orc_id: int, dados: OrcamentoIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    o = _orcamento(db, u, orc_id)
    if o.status != "aberto":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só dá para editar orçamento que ainda não foi aprovado nem recusado.")
    _validar(dados)
    o.itens = _itens(dados, u, o.paciente_id)
    o.desconto, o.observacoes = dados.desconto, dados.observacoes
    auditar(db, u, "editar", "orcamento", o.id, request)
    db.commit()
    db.refresh(o)
    return _out(o, _autores(db, u))


def dividir(total: int, n: int) -> list[int]:
    """Divide em n parcelas inteiras; os centavos que sobram vão na primeira."""
    base, resto = divmod(total, n)
    return [base + resto] + [base] * (n - 1)


def _mes_seguinte(d: date, k: int) -> date:
    """Mesmo dia k meses depois; se o mês não tem o dia (31/02), usa o último dia."""
    m = d.month - 1 + k
    ano, mes = d.year + m // 12, m % 12 + 1
    for dia in (d.day, 30, 29, 28):
        try:
            return date(ano, mes, dia)
        except ValueError:
            continue
    raise ValueError  # inalcançável


@router.post("/orcamentos/{orc_id}/aprovar", response_model=OrcamentoOut)
def aprovar(orc_id: int, dados: Aprovacao, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    o = _orcamento(db, u, orc_id)
    if o.status != "aberto":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este orçamento já foi decidido.")
    total = _subtotal(o.itens) - o.desconto
    if total <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Orçamento sem valor. Defina os preços antes de aprovar.")
    if dados.entrada_paga and not dados.forma_entrada:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Informe a forma de pagamento da entrada.")
    for k, valor in enumerate(dividir(total, dados.parcelas)):
        p = Parcela(clinica_id=u.clinica_id, orcamento_id=o.id, paciente_id=o.paciente_id, numero=k + 1,
                    vencimento=_mes_seguinte(dados.primeiro_vencimento, k), valor=valor)
        if k == 0 and dados.entrada_paga:
            p.pago_em, p.forma = date.today(), dados.forma_entrada
        db.add(p)
    o.status, o.aprovado_em = "aprovado", datetime.now(timezone.utc)
    auditar(db, u, "aprovar", "orcamento", o.id, request)
    db.commit()
    db.refresh(o)
    return _out(o, _autores(db, u))


@router.post("/orcamentos/{orc_id}/recusar", response_model=OrcamentoOut)
def recusar(orc_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    o = _orcamento(db, u, orc_id)
    if o.status != "aberto":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este orçamento já foi decidido.")
    o.status = "recusado"
    auditar(db, u, "recusar", "orcamento", o.id, request)
    db.commit()
    db.refresh(o)
    return _out(o, _autores(db, u))


@router.post("/orcamentos/{orc_id}/cancelar", response_model=OrcamentoOut)
def cancelar(orc_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Desiste do tratamento aprovado: as parcelas em aberto deixam de ser cobradas; as pagas continuam registradas."""
    o = _orcamento(db, u, orc_id)
    if o.status != "aprovado":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só se cancela orçamento aprovado. Um orçamento em aberto pode ser recusado.")
    for p in o.parcelas:
        if not p.pago_em:
            p.cancelada = True
    o.status = "cancelado"
    auditar(db, u, "cancelar", "orcamento", o.id, request)
    db.commit()
    db.refresh(o)
    return _out(o, _autores(db, u))


@router.post("/orcamentos/{orc_id}/restante", response_model=OrcamentoOut, status_code=201)
def orcamento_restante(orc_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Novo orçamento (em aberto) com o que não foi feito de um orçamento aprovado ou cancelado."""
    o = _orcamento(db, u, orc_id)
    if o.status not in ("aprovado", "cancelado"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Orçamento restante sai de um orçamento aprovado ou cancelado.")
    faltam = [i for i in o.itens if not i.feito]
    if not faltam:
        raise HTTPException(status.HTTP_409_CONFLICT, "Todos os itens deste orçamento já foram feitos.")
    novo = Orcamento(clinica_id=u.clinica_id, paciente_id=o.paciente_id, usuario_id=u.id, origem_id=o.id,
                     observacoes=f"Orçamento restante do orçamento de {o.criado_em:%d/%m/%Y}.")
    novo.itens = [ItemOrcamento(clinica_id=u.clinica_id, paciente_id=o.paciente_id, dentista_id=i.dentista_id, descricao=i.descricao,
                                dente=i.dente, faces=i.faces, valor=i.valor, quantidade=i.quantidade) for i in faltam]
    db.add(novo)
    db.flush()
    auditar(db, u, "criar", "orcamento", novo.id, request)
    db.commit()
    db.refresh(novo)
    return _out(novo, _autores(db, u))


# ---------- Tratamentos ----------


def _tratamento_out(i: ItemOrcamento, autores: dict[int, str]) -> TratamentoOut:
    return TratamentoOut(id=i.id, orcamento_id=i.orcamento_id, descricao=i.descricao, dente=i.dente, faces=i.faces,
                         dentista=autores.get(i.dentista_id or 0, "?"), feito=i.feito, feito_em=i.feito_em, criado_em=i.criado_em)


@router.get("/pacientes/{paciente_id}/tratamentos", response_model=list[TratamentoOut])
def listar_tratamentos(paciente_id: int, finalizados: bool = False, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """A fazer: itens de orçamentos aprovados e tratamentos avulsos. Com finalizados=true, só os já feitos."""
    _do_consultorio(db, u, paciente_id)
    aprovados = select(Orcamento.id).where(Orcamento.paciente_id == paciente_id, Orcamento.status == "aprovado")
    q = select(ItemOrcamento).where(ItemOrcamento.paciente_id == paciente_id, ItemOrcamento.feito.is_(finalizados))
    if finalizados:
        q = q.order_by(ItemOrcamento.feito_em.desc())
    else:
        q = q.where(ItemOrcamento.orcamento_id.is_(None) | ItemOrcamento.orcamento_id.in_(aprovados)).order_by(ItemOrcamento.id)
    autores = _autores(db, u)
    return [_tratamento_out(i, autores) for i in db.scalars(q)]


@router.post("/pacientes/{paciente_id}/tratamentos", response_model=TratamentoOut, status_code=201)
def criar_tratamento(paciente_id: int, dados: TratamentoIn, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Tratamento sem orçamento (ex.: retorno, ajuste de aparelho)."""
    _do_consultorio(db, u, paciente_id)
    i = ItemOrcamento(clinica_id=u.clinica_id, paciente_id=paciente_id, dentista_id=u.id, valor=0, **dados.model_dump())
    db.add(i)
    db.flush()
    auditar(db, u, "criar", "tratamento", i.id, request)
    db.commit()
    db.refresh(i)
    return _tratamento_out(i, _autores(db, u))


def _tratamento(db: Session, u: Usuario, item_id: int) -> ItemOrcamento:
    i = db.get(ItemOrcamento, item_id)
    if not i or i.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tratamento não encontrado.")
    if i.orcamento_id:
        o = db.get(Orcamento, i.orcamento_id)
        if o and o.status != "aprovado":
            raise HTTPException(status.HTTP_409_CONFLICT, "Este item é de um orçamento que não está aprovado.")
    return i


@router.post("/tratamentos/{item_id}/finalizar", response_model=TratamentoOut)
def finalizar(item_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Marca como feito e registra a anotação na evolução clínica (que não se apaga)."""
    i = _tratamento(db, u, item_id)
    if i.feito:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este tratamento já foi finalizado.")
    i.feito, i.feito_em = True, datetime.now(timezone.utc)
    texto = f"Tratamento finalizado: {i.descricao}" + (f" (faces {i.faces})" if i.faces else "")
    db.add(Evolucao(clinica_id=u.clinica_id, paciente_id=i.paciente_id, usuario_id=u.id, texto=texto, dentes=str(i.dente) if i.dente else None))
    auditar(db, u, "finalizar", "tratamento", i.id, request)
    db.commit()
    db.refresh(i)
    return _tratamento_out(i, _autores(db, u))


@router.post("/tratamentos/{item_id}/reabrir", response_model=TratamentoOut)
def reabrir(item_id: int, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Desfaz o "finalizado" por engano. A anotação na evolução continua; registre uma correção lá se precisar."""
    i = _tratamento(db, u, item_id)
    if not i.feito:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este tratamento não está finalizado.")
    i.feito, i.feito_em = False, None
    auditar(db, u, "reabrir", "tratamento", i.id, request)
    db.commit()
    db.refresh(i)
    return _tratamento_out(i, _autores(db, u))


# ---------- Parcelas ----------


def _parcela(db: Session, u: Usuario, parcela_id: int) -> Parcela:
    p = db.get(Parcela, parcela_id)
    if not p or p.clinica_id != u.clinica_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela não encontrada.")
    return p


@router.post("/parcelas/{parcela_id}/pagar", response_model=ParcelaOut)
def pagar(parcela_id: int, dados: Pagamento, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = _parcela(db, u, parcela_id)
    if p.cancelada:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta parcela foi cancelada.")
    if p.pago_em:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta parcela já está paga.")
    p.pago_em, p.forma = dados.pago_em, dados.forma
    auditar(db, u, "pagar", "parcela", p.id, request)
    db.commit()
    db.refresh(p)
    return p


@router.post("/parcelas/{parcela_id}/estornar", response_model=ParcelaOut)
def estornar(parcela_id: int, dados: Estorno, request: Request, u: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    p = _parcela(db, u, parcela_id)
    if not p.pago_em:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta parcela não está paga.")
    o = db.get(Orcamento, p.orcamento_id)
    p.pago_em, p.forma = None, None
    if o and o.status == "cancelado":
        p.cancelada = True  # tratamento cancelado: não volta a ser cobrada
    auditar(db, u, f"estornar: {dados.motivo}"[:40], "parcela", p.id, request)
    db.commit()
    db.refresh(p)
    return p


# ---------- Contas a receber ----------


@router.get("/financeiro", response_model=ResumoFinanceiro)
def resumo(
    de: date = Query(...),
    ate: date = Query(...),
    u: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    """Recebido no período (por data de pagamento) e tudo o que está em aberto, do mais antigo ao mais novo."""
    if ate < de:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A data final vem antes da inicial.")
    hoje = date.today()
    pagas = db.scalars(select(Parcela).where(Parcela.clinica_id == u.clinica_id, Parcela.pago_em >= de, Parcela.pago_em <= ate))
    por_forma: dict[str, int] = {}
    recebido = 0
    for p in pagas:
        recebido += p.valor
        por_forma[p.forma or "?"] = por_forma.get(p.forma or "?", 0) + p.valor

    abertas = list(db.scalars(
        select(Parcela).where(Parcela.clinica_id == u.clinica_id, Parcela.pago_em.is_(None), Parcela.cancelada.is_(False))
        .order_by(Parcela.vencimento, Parcela.id)
    ))
    pacientes = {x.id: x for x in db.scalars(select(Paciente).where(Paciente.id.in_({p.paciente_id for p in abertas})))} if abertas else {}
    totais: dict[int, int] = {}
    for p in db.scalars(select(Parcela).where(Parcela.orcamento_id.in_({p.orcamento_id for p in abertas}))) if abertas else []:
        totais[p.orcamento_id] = max(totais.get(p.orcamento_id, 0), p.numero)
    contas = [
        ContaReceber(**ParcelaOut.model_validate(p).model_dump(), paciente_nome=pacientes[p.paciente_id].nome,
                     paciente_telefone=pacientes[p.paciente_id].telefone, total_parcelas=totais.get(p.orcamento_id, 1))
        for p in abertas
    ]
    return ResumoFinanceiro(
        recebido_periodo=recebido,
        a_receber=sum(p.valor for p in abertas),
        atrasado=sum(p.valor for p in abertas if p.vencimento < hoje),
        por_forma=por_forma,
        contas=contas,
    )
