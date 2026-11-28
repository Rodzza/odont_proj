"""Ponto único que fala com o Claude. Os testes trocam `rodar` por uma versão falsa."""
from typing import Any

from fastapi import HTTPException, status

from ..config import settings


class IAIndisponivel(HTTPException):
    def __init__(self, msg: str = "IA desligada: defina ANTHROPIC_API_KEY no .env do servidor."):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, msg)


def modelo(rapido: bool = False):
    cfg = settings()
    if not cfg.anthropic_api_key:
        raise IAIndisponivel()
    from agno.models.anthropic import Claude

    return Claude(id=cfg.ia_modelo_rapido if rapido else cfg.ia_modelo, api_key=cfg.anthropic_api_key, max_tokens=4096)


def nome_modelo(rapido: bool = False) -> str:
    cfg = settings()
    return cfg.ia_modelo_rapido if rapido else cfg.ia_modelo


def rodar(
    *,
    instrucoes: list[str],
    mensagem: str | list,
    rapido: bool = False,
    esquema: type | None = None,
    ferramentas: list | None = None,
    imagens: list | None = None,
    arquivos: list | None = None,
) -> Any:
    """Cria um agente Agno com o Claude e devolve o conteúdo da resposta
    (objeto Pydantic se `esquema` for dado; texto caso contrário)."""
    from agno.agent import Agent

    agente = Agent(
        model=modelo(rapido),
        instructions=instrucoes,
        output_schema=esquema,
        tools=ferramentas or [],
        markdown=False,
        telemetry=False,
    )
    try:
        r = agente.run(mensagem, images=imagens, files=arquivos)
    except HTTPException:
        raise
    except Exception as e:  # rede, chave inválida, limite de uso…
        raise IAIndisponivel(f"A IA não respondeu agora ({type(e).__name__}). Tente de novo em instantes.") from e
    if str(getattr(r, "status", "")).lower().endswith("error"):
        raise IAIndisponivel("A IA não respondeu agora (confira a ANTHROPIC_API_KEY ou tente de novo em instantes).")
    if esquema is not None and not isinstance(r.content, esquema):
        raise IAIndisponivel("A IA respondeu fora do formato esperado. Tente de novo.")
    return r.content
