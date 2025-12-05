import logging
from fastapi import APIRouter, Request, WebSocket, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import HTMLResponse
from app.extraction.presentation import ExtractionWebSocketHandler
from app.extraction.services.storage import StorageService
from app.templating import templates
from app.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def extraction_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Renders the main dashboard for Extraction Review."""
    documents = await StorageService().get_dashboard_view_data(db)

    return templates.TemplateResponse(
        request=request,
        name="extraction/index.html",
        context={"documents": documents}
    )


@router.websocket("/ws", name="extraction_websocket")
async def extraction_websocket(websocket: WebSocket):
    await websocket.accept()
    handler = ExtractionWebSocketHandler(websocket)
    await handler.listen()