"""The FastAPI app. Mounts capability routers; holds no domain logic."""

from fastapi import FastAPI

from app.capabilities.writing.router import router as writing_router

app = FastAPI(title="Narrare", version="2.0.0")
app.include_router(writing_router)
