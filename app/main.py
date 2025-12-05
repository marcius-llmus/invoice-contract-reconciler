import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.extraction.routes.htmx import router as extraction_htmx_router
from app.db import sessionmanager, Base


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI): # noqa
    await sessionmanager.create_tables(Base)
    yield
    await sessionmanager.cleanup()

app = FastAPI(lifespan=lifespan)

app.include_router(extraction_htmx_router, prefix="/extraction", tags=["extraction"])

@app.get("/")
async def root():
    return RedirectResponse(url="/extraction")
