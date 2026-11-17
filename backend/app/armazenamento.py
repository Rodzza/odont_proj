"""Guarda os anexos dos pacientes. Hoje em disco (pasta privada); a interface é a mesma para
trocar por um bucket privado (Supabase Storage) no deploy."""
import secrets
from pathlib import Path

from .config import settings

# Tipos aceitos, conferidos pelo conteúdo do arquivo (não pela extensão que o navegador manda).
ASSINATURAS: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "application/pdf": (b"%PDF-",),
}


def tipo_pelo_conteudo(dados: bytes) -> str | None:
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    for tipo, inicios in ASSINATURAS.items():
        if any(dados.startswith(i) for i in inicios):
            return tipo
    return None


def _pasta(clinica_id: int) -> Path:
    p = Path(settings().pasta_anexos).resolve() / str(clinica_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def salvar(clinica_id: int, dados: bytes) -> str:
    chave = secrets.token_urlsafe(24)
    (_pasta(clinica_id) / chave).write_bytes(dados)
    return chave


def ler(clinica_id: int, chave: str) -> bytes:
    # A chave vem do banco (gerada por nós), nunca do usuário; ainda assim, confere o caminho.
    base = _pasta(clinica_id)
    arquivo = (base / chave).resolve()
    if base not in arquivo.parents:
        raise FileNotFoundError(chave)
    return arquivo.read_bytes()
