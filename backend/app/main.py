from fastapi import FastAPI
from .api.routes import auth, chat, matches
from .core.config import settings


app = FastAPI(title=settings.app_name)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(matches.router, prefix="/api/v1")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
