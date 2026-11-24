from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import auth, consultas, financeiro, pacientes, prontuario


def criar_app() -> FastAPI:
    cfg = settings()
    if not cfg.secret_key or (cfg.ambiente == "prod" and len(cfg.secret_key) < 32):
        raise RuntimeError("Defina SECRET_KEY (32+ caracteres em produção) antes de subir o servidor.")

    app = FastAPI(title=f"{cfg.app_name} API", docs_url=None if cfg.ambiente == "prod" else "/docs", redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.origens,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def cabecalhos_seguranca(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"  # dado de saúde não fica em cache
        return resp

    @app.get("/health")
    def health():
        return {"ok": True}

    for r in (auth.router, pacientes.router, consultas.router, prontuario.router, financeiro.router):
        app.include_router(r)

    Base.metadata.create_all(engine)
    return app


app = criar_app()
