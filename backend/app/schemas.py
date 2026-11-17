import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import StatusConsulta


def _so_digitos(v: str | None) -> str | None:
    if v is None:
        return None
    d = re.sub(r"\D", "", v)
    return d or None


def cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(cpf[i]) * (n + 1 - i) for i in range(n))
        dig = (soma * 10) % 11 % 10
        if dig != int(cpf[n]):
            return False
    return True


class Login(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    token: str
    nome: str
    clinica: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str
    cro: str | None


class PacienteIn(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    cpf: str | None = None
    nascimento: date | None = None
    telefone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    endereco: str | None = Field(default=None, max_length=255)
    responsavel: str | None = Field(default=None, max_length=160)
    observacoes: str | None = Field(default=None, max_length=5000)

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Nome muito curto.")
        return v

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str | None) -> str | None:
        v = _so_digitos(v)
        if v and not cpf_valido(v):
            raise ValueError("CPF inválido.")
        return v

    @field_validator("telefone")
    @classmethod
    def _tel(cls, v: str | None) -> str | None:
        v = _so_digitos(v)
        if v and not 10 <= len(v) <= 13:
            raise ValueError("Telefone inválido. Use DDD + número.")
        return v

    @field_validator("nascimento")
    @classmethod
    def _nasc(cls, v: date | None) -> date | None:
        if v and (v > date.today() or v.year < 1900):
            raise ValueError("Data de nascimento inválida.")
        return v


class PacienteOut(PacienteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    arquivado: bool
    criado_em: datetime


class PacienteResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    telefone: str | None
    nascimento: date | None
    arquivado: bool


class ConsultaIn(BaseModel):
    paciente_id: int
    inicio: datetime
    duracao_min: int = Field(default=30, ge=10, le=480)
    procedimento: str | None = Field(default=None, max_length=160)
    status: StatusConsulta = StatusConsulta.agendada
    observacoes: str | None = Field(default=None, max_length=5000)

    @field_validator("inicio")
    @classmethod
    def _sem_fuso(cls, v: datetime) -> datetime:
        # Agenda usa o horário de parede do consultório.
        return v.replace(tzinfo=None, second=0, microsecond=0)


class ConsultaStatus(BaseModel):
    status: StatusConsulta


class ConsultaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    paciente_id: int
    paciente_nome: str
    paciente_telefone: str | None
    inicio: datetime
    duracao_min: int
    procedimento: str | None
    status: StatusConsulta
    observacoes: str | None
