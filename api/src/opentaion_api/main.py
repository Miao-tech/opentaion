# src/opentaion_api/main.py
from fastapi import FastAPI

app = FastAPI(title="opentaion-api", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
