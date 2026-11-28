"""Busca por significado entre TODOS os pacientes do consultório (pgvector).

O chat de um paciente continua mandando o prontuário inteiro ao Claude (mais preciso).
Isto aqui serve para perguntas que atravessam pacientes: "quem teve reação à articaína?",
"casos parecidos com lesão periapical no 36".

Fluxo:
1. Ao salvar anamnese, evolução ou leitura de anexo, o texto vira um vetor (embedding) e vai
   para a tabela `trecho_vetor`, no MESMO banco do DentFlow (Postgres/Supabase com pgvector).
2. Na busca, a pergunta vira vetor e o banco devolve os trechos mais próximos.
3. O Claude lê só esses trechos e responde citando os pacientes.

Embeddings: Voyage AI (recomendada pela Anthropic, que não tem modelo próprio de embeddings).
Sem VOYAGE_API_KEY, nada é indexado e a busca responde 503; o resto do sistema segue normal.
No SQLite (desenvolvimento) o vetor é guardado como JSON e a distância é calculada em Python.
"""
import json
import math
from datetime import datetime

import httpx
from fastapi import HTTPException, status
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import TypeDecorator

from ..config import settings
from ..db import Base
from ..models import AnaliseIA, Anamnese, Evolucao, Paciente, agora

DIM = 1024  # voyage-3.5 / voyage-3.5-lite


class VetorTipo(TypeDecorator):
    """`vector(1024)` no Postgres (pgvector); texto JSON nos outros bancos."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(DIM))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return json.loads(value)


class TrechoVetor(Base):
    __tablename__ = "trecho_vetor"
    id: Mapped[int] = mapped_column(primary_key=True)
    clinica_id: Mapped[int] = mapped_column(ForeignKey("clinica.id"), index=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("paciente.id"), index=True)
    origem: Mapped[str] = mapped_column(String(40))  # "anamnese", "evolucao:12", "anexo:3"
    texto: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(VetorTipo())
    modelo: Mapped[str] = mapped_column(String(60))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    __table_args__ = (Index("ix_trecho_paciente_origem", "paciente_id", "origem", unique=True),)


class BuscaIndisponivel(HTTPException):
    def __init__(self, msg="Busca entre pacientes desligada: defina VOYAGE_API_KEY no .env do servidor."):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, msg)


def ativa() -> bool:
    return bool(settings().voyage_api_key)


def embeddings(textos: list[str], tipo: str) -> list[list[float]]:
    """Chama a Voyage. `tipo` = "document" ao indexar, "query" ao buscar. Os testes trocam esta função."""
    cfg = settings()
    if not cfg.voyage_api_key:
        raise BuscaIndisponivel()
    try:
        r = httpx.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {cfg.voyage_api_key}"},
            json={"input": textos, "model": cfg.voyage_modelo, "input_type": tipo, "output_dimension": DIM},
            timeout=30,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise BuscaIndisponivel(f"O serviço de embeddings não respondeu ({type(e).__name__}).") from e
    return [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]


# ---------- Indexação ----------


def _texto_anamnese(a: Anamnese) -> str:
    from ..routers.prontuario import ROTULO_DOENCA, alertas
    from ..schemas import AnamneseIn

    d = AnamneseIn(**json.loads(a.respostas))
    partes = [
        f"Queixa: {d.queixa_principal}" if d.queixa_principal else "",
        f"Alergias: {d.alergias}" if d.alergias else "",
        f"Medicamentos: {d.medicamentos}" if d.medicamentos else "",
        "Condições: " + ", ".join(ROTULO_DOENCA.get(x, x) for x in d.doencas) if d.doencas else "",
        f"Outras condições: {d.outras_doencas}" if d.outras_doencas else "",
        "Alertas: " + "; ".join(alertas(d)) if alertas(d) else "",
        f"Observações: {d.observacoes}" if d.observacoes else "",
    ]
    return "Anamnese. " + " | ".join(p for p in partes if p)


def _salvar(db: Session, paciente: Paciente, origem: str, texto: str) -> None:
    texto = texto.strip()[:6000]
    db.execute(delete(TrechoVetor).where(TrechoVetor.paciente_id == paciente.id, TrechoVetor.origem == origem))
    if not texto:
        return
    [vetor] = embeddings([texto], "document")
    db.add(TrechoVetor(clinica_id=paciente.clinica_id, paciente_id=paciente.id, origem=origem, texto=texto, embedding=vetor, modelo=settings().voyage_modelo))


def indexar(db: Session, paciente: Paciente, origem: str, texto: str) -> bool:
    """Indexa um trecho sem nunca quebrar o salvamento do prontuário (falha = só não indexa)."""
    if not ativa():
        return False
    try:
        with db.begin_nested():
            _salvar(db, paciente, origem, texto)
        return True
    except Exception:
        return False


def indexar_anamnese(db: Session, a: Anamnese) -> bool:
    return indexar(db, db.get(Paciente, a.paciente_id), "anamnese", _texto_anamnese(a))


def indexar_evolucao(db: Session, e: Evolucao) -> bool:
    extra = f" (dentes {e.dentes})" if e.dentes else ""
    return indexar(db, db.get(Paciente, e.paciente_id), f"evolucao:{e.id}", f"Evolução de {e.criado_em:%d/%m/%Y}{extra}: {e.texto}")


def indexar_leitura(db: Session, a: AnaliseIA) -> bool:
    r = json.loads(a.resultado)
    texto = f"Leitura de anexo ({r.get('tipo_documento', '')}): {r.get('resumo', '')} Achados: {'; '.join(r.get('achados', []))}"
    return indexar(db, db.get(Paciente, a.paciente_id), f"anexo:{a.anexo_id}", texto)


def reindexar_clinica(db: Session, clinica_id: int) -> int:
    """Indexa tudo de novo (ex.: depois de ligar a busca num banco que já tinha dados)."""
    if not ativa():
        raise BuscaIndisponivel()
    n = 0
    for a in db.scalars(select(Anamnese).where(Anamnese.clinica_id == clinica_id)):
        n += indexar_anamnese(db, a)
    for e in db.scalars(select(Evolucao).where(Evolucao.clinica_id == clinica_id)):
        n += indexar_evolucao(db, e)
    vistos: set[int] = set()
    for a in db.scalars(select(AnaliseIA).where(AnaliseIA.clinica_id == clinica_id, AnaliseIA.tipo == "anexo").order_by(AnaliseIA.criado_em.desc())):
        if a.anexo_id not in vistos:
            vistos.add(a.anexo_id)
            n += indexar_leitura(db, a)
    return n


# ---------- Busca ----------


def _cosseno(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


def buscar(db: Session, clinica_id: int, pergunta: str, k: int = 8) -> list[tuple[TrechoVetor, float]]:
    [q] = embeddings([pergunta], "query")
    base = select(TrechoVetor).join(Paciente, Paciente.id == TrechoVetor.paciente_id).where(
        TrechoVetor.clinica_id == clinica_id, Paciente.arquivado.is_(False)
    )
    if db.get_bind().dialect.name == "postgresql":
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import Float, cast, literal

        # operador <=> = distância de cosseno; usa o índice HNSW criado em main.py
        dist = TrechoVetor.embedding.op("<=>", return_type=Float)(cast(literal(str(q)), Vector(DIM)))
        return [(t, 1 - d) for t, d in db.execute(base.add_columns(dist).order_by(dist).limit(k))]
    todos = [(t, _cosseno(q, t.embedding)) for t in db.scalars(base)]
    return sorted(todos, key=lambda x: x[1], reverse=True)[:k]
