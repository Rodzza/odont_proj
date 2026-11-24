import re
from datetime import date, datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import StatusConsulta


def _utc(v: datetime | None) -> datetime | None:
    """Momentos gravados em UTC. O SQLite devolve sem fuso; marca como UTC para o navegador converter."""
    return v.replace(tzinfo=timezone.utc) if v and v.tzinfo is None else v


Momento = Annotated[datetime, AfterValidator(_utc)]


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
    criado_em: Momento


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


# ---------- Fase 2: prontuário ----------

DOENCAS = (
    "diabetes", "hipertensao", "cardiopatia", "asma", "epilepsia", "hepatite", "problemas_renais",
    "disturbio_coagulacao", "osteoporose", "ansiedade",
)


class AnamneseIn(BaseModel):
    queixa_principal: str | None = Field(default=None, max_length=1000)
    alergias: str | None = Field(default=None, max_length=1000)
    medicamentos: str | None = Field(default=None, max_length=1000)
    doencas: list[str] = Field(default_factory=list)
    outras_doencas: str | None = Field(default=None, max_length=1000)
    gestante: bool | None = None
    fumante: bool | None = None
    reacao_anestesia: bool | None = None
    sangramento_excessivo: bool | None = None
    pressao_arterial: str | None = Field(default=None, max_length=20)
    observacoes: str | None = Field(default=None, max_length=3000)

    @field_validator("doencas")
    @classmethod
    def _doencas(cls, v: list[str]) -> list[str]:
        desconhecidas = [d for d in v if d not in DOENCAS]
        if desconhecidas:
            raise ValueError(f"Condição desconhecida: {desconhecidas[0]}")
        return sorted(set(v))


class AnamneseOut(AnamneseIn):
    atualizado_em: Momento | None = None
    alertas: list[str] = Field(default_factory=list)


class EvolucaoIn(BaseModel):
    texto: str = Field(min_length=3, max_length=10000)
    dentes: list[int] = Field(default_factory=list, max_length=32)
    retifica_id: int | None = None

    @field_validator("dentes")
    @classmethod
    def _dentes(cls, v: list[int]) -> list[int]:
        for n in v:
            if n not in DENTES_VALIDOS:
                raise ValueError(f"Dente {n} não existe na numeração FDI.")
        return sorted(set(v))


class EvolucaoOut(BaseModel):
    id: int
    texto: str
    dentes: list[int]
    retifica_id: int | None
    retificada_por: int | None = None
    autor: str
    criado_em: Momento


PERMANENTES = [q * 10 + n for q in (1, 2, 3, 4) for n in range(1, 9)]
DECIDUOS = [q * 10 + n for q in (5, 6, 7, 8) for n in range(1, 6)]
DENTES_VALIDOS = frozenset(PERMANENTES + DECIDUOS)
SITUACOES_DENTE = ("higido", "ausente", "extrair", "implante", "coroa", "canal", "protese")
ESTADOS_FACE = ("carie", "restaurado", "restaurar")
FACES = ("V", "L", "M", "D", "O")


class DenteIn(BaseModel):
    situacao: str = "higido"
    faces: dict[str, str] = Field(default_factory=dict)
    observacao: str | None = Field(default=None, max_length=500)

    @field_validator("situacao")
    @classmethod
    def _sit(cls, v: str) -> str:
        if v not in SITUACOES_DENTE:
            raise ValueError("Situação do dente inválida.")
        return v

    @field_validator("faces")
    @classmethod
    def _faces(cls, v: dict[str, str]) -> dict[str, str]:
        for f, e in v.items():
            if f not in FACES or e not in ESTADOS_FACE:
                raise ValueError(f"Face ou estado inválido: {f}={e}")
        return v


class DenteOut(DenteIn):
    numero: int


class AnexoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    descricao: str | None
    tipo: str
    tamanho: int
    criado_em: Momento


# ---------- Fase 3: financeiro (valores em centavos) ----------

FORMAS_PAGAMENTO = ("pix", "dinheiro", "debito", "credito", "boleto", "transferencia")


class ProcedimentoIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    valor: int = Field(ge=0, le=100_000_00)
    ativo: bool = True

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        return " ".join(v.split())


class ProcedimentoOut(ProcedimentoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sugere: str | None


class ItemIn(BaseModel):
    descricao: str = Field(min_length=2, max_length=160)
    dente: int | None = None
    faces: str | None = None
    valor: int = Field(ge=0, le=100_000_00)
    quantidade: int = Field(default=1, ge=1, le=99)

    @field_validator("faces")
    @classmethod
    def _faces(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.upper().replace(" ", "")
        if any(f not in FACES for f in v) or len(set(v)) != len(v):
            raise ValueError("Faces inválidas. Use V, L, M, D, O.")
        return "".join(f for f in FACES if f in v)

    @field_validator("dente")
    @classmethod
    def _dente(cls, v: int | None) -> int | None:
        if v is not None and v not in DENTES_VALIDOS:
            raise ValueError(f"Dente {v} não existe na numeração FDI.")
        return v


class ItemOut(ItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    feito: bool
    feito_em: Momento | None = None


class TratamentoIn(BaseModel):
    descricao: str = Field(min_length=2, max_length=160)
    dente: int | None = None
    faces: str | None = None

    _dente = field_validator("dente")(ItemIn._dente.__func__)
    _faces = field_validator("faces")(ItemIn._faces.__func__)


class TratamentoOut(BaseModel):
    id: int
    orcamento_id: int | None
    descricao: str
    dente: int | None
    faces: str | None
    dentista: str
    feito: bool
    feito_em: Momento | None
    criado_em: Momento


class OrcamentoIn(BaseModel):
    itens: list[ItemIn] = Field(min_length=1, max_length=60)
    desconto: int = Field(default=0, ge=0)
    observacoes: str | None = Field(default=None, max_length=2000)


class Aprovacao(BaseModel):
    parcelas: int = Field(ge=1, le=24)
    primeiro_vencimento: date
    entrada_paga: bool = False
    forma_entrada: str | None = None

    @field_validator("forma_entrada")
    @classmethod
    def _forma(cls, v: str | None) -> str | None:
        if v is not None and v not in FORMAS_PAGAMENTO:
            raise ValueError("Forma de pagamento inválida.")
        return v


class ParcelaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    orcamento_id: int
    paciente_id: int
    numero: int
    vencimento: date
    valor: int
    pago_em: date | None
    forma: str | None
    cancelada: bool


class OrcamentoOut(BaseModel):
    id: int
    origem_id: int | None = None
    paciente_id: int
    status: str
    itens: list[ItemOut]
    subtotal: int
    desconto: int
    total: int
    pago: int
    observacoes: str | None
    autor: str
    criado_em: Momento
    aprovado_em: Momento | None
    parcelas: list[ParcelaOut]


class Pagamento(BaseModel):
    forma: str
    pago_em: date

    @field_validator("forma")
    @classmethod
    def _forma(cls, v: str) -> str:
        if v not in FORMAS_PAGAMENTO:
            raise ValueError("Forma de pagamento inválida.")
        return v

    @field_validator("pago_em")
    @classmethod
    def _data(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("A data do pagamento não pode estar no futuro.")
        return v


class Estorno(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


class ContaReceber(ParcelaOut):
    paciente_nome: str
    paciente_telefone: str | None
    total_parcelas: int


class ResumoFinanceiro(BaseModel):
    recebido_periodo: int
    a_receber: int
    atrasado: int
    por_forma: dict[str, int]
    contas: list[ContaReceber]
