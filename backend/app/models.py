"""Modelo de dados. Toda tabela de negócio tem clinica_id: hoje há um consultório; amanhã, SaaS."""
import enum
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Clinica(Base):
    __tablename__ = "clinica"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    fuso: Mapped[str] = mapped_column(String(40), default="America/Belem")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    clinica_id: Mapped[int] = mapped_column(ForeignKey("clinica.id"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    cro: Mapped[str | None] = mapped_column(String(30))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Paciente(Base):
    __tablename__ = "paciente"
    id: Mapped[int] = mapped_column(primary_key=True)
    clinica_id: Mapped[int] = mapped_column(ForeignKey("clinica.id"), index=True)
    nome: Mapped[str] = mapped_column(String(160))
    cpf: Mapped[str | None] = mapped_column(String(11))
    nascimento: Mapped[date | None] = mapped_column(Date)
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    endereco: Mapped[str | None] = mapped_column(String(255))
    responsavel: Mapped[str | None] = mapped_column(String(160))
    observacoes: Mapped[str | None] = mapped_column(Text)
    # Prontuário não se apaga (guarda mínima legal): paciente é só arquivado.
    arquivado: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)

    consultas: Mapped[list["Consulta"]] = relationship(back_populates="paciente")

    __table_args__ = (Index("ix_paciente_clinica_cpf", "clinica_id", "cpf", unique=True),)


class StatusConsulta(str, enum.Enum):
    agendada = "agendada"
    confirmada = "confirmada"
    atendida = "atendida"
    faltou = "faltou"
    cancelada = "cancelada"


class Consulta(Base):
    __tablename__ = "consulta"
    id: Mapped[int] = mapped_column(primary_key=True)
    clinica_id: Mapped[int] = mapped_column(ForeignKey("clinica.id"), index=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("paciente.id"), index=True)
    # Horário de parede no fuso do consultório (sem fuso no banco).
    inicio: Mapped[datetime] = mapped_column(DateTime, index=True)
    duracao_min: Mapped[int] = mapped_column(Integer, default=30)
    procedimento: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[StatusConsulta] = mapped_column(Enum(StatusConsulta, native_enum=False, length=12), default=StatusConsulta.agendada)
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)

    paciente: Mapped[Paciente] = relationship(back_populates="consultas")


class Auditoria(Base):
    """Quem viu ou mudou dado de paciente, e quando (LGPD: dado de saúde)."""

    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    clinica_id: Mapped[int] = mapped_column(ForeignKey("clinica.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    acao: Mapped[str] = mapped_column(String(40))
    entidade: Mapped[str] = mapped_column(String(40))
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(45))
    em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
