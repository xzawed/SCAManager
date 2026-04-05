from fastapi import FastAPI
from src.webhook.router import router as webhook_router

app = FastAPI(title="SCAManager", version="0.1.0")
app.include_router(webhook_router)


@app.get("/health")
def health():
    return {"status": "ok"}
