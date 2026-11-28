"""Monta o prontuário de um paciente como uma lista de FONTES numeradas para o Claude.

No workshop, o chat usava RAG com embeddings (LanceDB). Aqui o prontuário de um paciente
é pequeno e estruturado, então cabe inteiro no contexto: cada registro vira uma fonte com
id próprio (ex.: "evolucao:12") e a IA cita esses ids. Assim não precisamos de banco
vetorial nem de modelo de embeddings (a Anthropic não oferece um).

LGPD: só vai para a IA o necessário clinicamente. CPF, telefone, e-mail e endereço NUNCA
entram; o paciente aparece pelo primeiro nome e idade.
"""
import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AnaliseIA, Anamnese, Anexo, Consulta, Dente, Evolucao, Paciente
from ..routers.prontuario import ROTULO_DOENCA, alertas
from ..schemas import AnamneseIn

MAX_EVOLUCOES = 60
MAX_CONSULTAS = 20


@dataclass
class Fonte:
    id: str
    titulo: str
    texto: str


def _idade(nasc: date | None) -> str:
    if not nasc:
        return "idade não informada"
    hoje = date.today()
    anos = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
    return f"{anos} anos"


def identificacao(p: Paciente) -> str:
    primeiro = (p.nome or "Paciente").split()[0]
    return f"Paciente: {primeiro}, {_idade(p.nascimento)}."


def fontes_do_paciente(db: Session, p: Paciente) -> list[Fonte]:
    out: list[Fonte] = []

    a = db.scalar(select(Anamnese).where(Anamnese.paciente_id == p.id))
    if a:
        d = AnamneseIn(**json.loads(a.respostas))
        partes = []
        if d.queixa_principal:
            partes.append(f"Queixa principal: {d.queixa_principal}")
        if d.alergias:
            partes.append(f"Alergias: {d.alergias}")
        if d.medicamentos:
            partes.append(f"Medicamentos: {d.medicamentos}")
        if d.doencas:
            partes.append("Condições: " + ", ".join(ROTULO_DOENCA.get(x, x) for x in d.doencas))
        if d.outras_doencas:
            partes.append(f"Outras condições: {d.outras_doencas}")
        for campo, rotulo in (("gestante", "Gestante"), ("fumante", "Fumante"), ("reacao_anestesia", "Reação à anestesia"), ("sangramento_excessivo", "Sangramento excessivo")):
            v = getattr(d, campo)
            if v is not None:
                partes.append(f"{rotulo}: {'sim' if v else 'não'}")
        if d.pressao_arterial:
            partes.append(f"Pressão arterial: {d.pressao_arterial}")
        if d.observacoes:
            partes.append(f"Observações: {d.observacoes}")
        al = alertas(d)
        if al:
            partes.append("ALERTAS: " + "; ".join(al))
        out.append(Fonte("anamnese", f"Anamnese (atualizada em {a.atualizado_em:%d/%m/%Y})", "\n".join(partes) or "Sem respostas."))

    dentes = list(db.scalars(select(Dente).where(Dente.paciente_id == p.id).order_by(Dente.numero)))
    marcados = [x for x in dentes if x.situacao != "higido" or json.loads(x.faces) or x.observacao]
    if marcados:
        linhas = []
        for x in marcados:
            faces = json.loads(x.faces)
            f = ", ".join(f"{k}: {v}" for k, v in sorted(faces.items()))
            linhas.append(f"Dente {x.numero}: {x.situacao}" + (f" | faces {f}" if f else "") + (f" | obs: {x.observacao}" if x.observacao else ""))
        out.append(Fonte("odontograma", "Odontograma (FDI; dentes não listados estão hígidos)", "\n".join(linhas)))

    evs = list(db.scalars(select(Evolucao).where(Evolucao.paciente_id == p.id).order_by(Evolucao.criado_em.desc()).limit(MAX_EVOLUCOES)))
    for e in reversed(evs):
        extra = f" (dentes {e.dentes})" if e.dentes else ""
        ret = f" [RETIFICA evolucao:{e.retifica_id}]" if e.retifica_id else ""
        out.append(Fonte(f"evolucao:{e.id}", f"Evolução de {e.criado_em:%d/%m/%Y}{extra}{ret}", e.texto))

    cons = list(db.scalars(select(Consulta).where(Consulta.paciente_id == p.id).order_by(Consulta.inicio.desc()).limit(MAX_CONSULTAS)))
    for c in reversed(cons):
        out.append(Fonte(f"consulta:{c.id}", f"Consulta {c.inicio:%d/%m/%Y %H:%M}", f"{c.procedimento or 'sem procedimento'} — situação: {c.status.value}" + (f". Obs.: {c.observacoes}" if c.observacoes else "")))

    anexos = {x.id: x for x in db.scalars(select(Anexo).where(Anexo.paciente_id == p.id, Anexo.arquivado.is_(False)))}
    leituras = db.scalars(
        select(AnaliseIA).where(AnaliseIA.paciente_id == p.id, AnaliseIA.tipo == "anexo").order_by(AnaliseIA.criado_em.desc())
    )
    vistos: set[int] = set()
    for l in leituras:
        if l.anexo_id in vistos or l.anexo_id not in anexos:
            continue
        vistos.add(l.anexo_id)
        r = json.loads(l.resultado)
        nome = anexos[l.anexo_id].descricao or anexos[l.anexo_id].nome
        out.append(Fonte(f"anexo:{l.anexo_id}", f"Leitura por IA do anexo \"{nome}\" (conferir no original)", f"{r.get('resumo', '')}\nAchados: " + "; ".join(r.get("achados", []))))

    return out


def como_texto(p: Paciente, fontes: list[Fonte]) -> str:
    blocos = [identificacao(p)]
    for f in fontes:
        blocos.append(f"<fonte id=\"{f.id}\" titulo=\"{f.titulo}\">\n{f.texto}\n</fonte>")
    return "\n\n".join(blocos)
