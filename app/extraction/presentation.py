import logging

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.extraction.events import StatusEvent, ProcessingCompleteEvent
from app.db import sessionmanager
from app.extraction.utils import WebSocketConnectionManager
from app.extraction.workflow import DocumentAutomationWorkflow
from app.extraction.services.storage import StorageService
from app.extraction.services.ingestion import IngestionService
from app.templating import templates

logger = logging.getLogger(__name__)


class ExtractionWebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.ws_manager = WebSocketConnectionManager(websocket)
        self.storage = StorageService()
        self.ingestion = IngestionService()

    async def listen(self):
        try:
            logger.info("Extraction WebSocket connection received")
            logger.info("WebSocket handler initialized, starting loop")

            while True:
                data = await self.ws_manager.websocket.receive_json()
                if data.get("type") == "upload":
                    await self._handle_upload(data)
                elif data.get("type") == "start_batch":
                    await self._handle_start_batch(data)
                elif data.get("type") == "retry_match":
                    await self._handle_retry_match(data)
                else:
                    raise ValueError("Invalid data received")

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)

    async def _handle_upload(self, data: dict):
        filename = data.get("filename")
        content_b64 = data.get("content")

        if filename and content_b64:
            logger.info(f"Received file upload via WebSocket: {filename}")

            async with sessionmanager.session() as db:
                try:
                    file_id = await self.ingestion.upload_from_base64(filename, content_b64)
                    await self.storage.create_document(db, file_id, filename)
                    await self._broadcast_list_update()

                except Exception as e:
                    logger.error(f"Error processing upload: {e}", exc_info=True)
                    error_html = templates.get_template("extraction/partials/upload_error.html").render(
                        filename=filename,
                        error=str(e)
                    )
                    await self.ws_manager.send_text(error_html)

    async def _handle_start_batch(self, data: dict):
        filenames = data.get("filenames", [])
        
        async with sessionmanager.session() as db:
            file_ids = await self.storage.get_file_ids_by_filenames(db, filenames)

        if file_ids:
            logger.info(f"Triggering workflow with {len(file_ids)} files")

            workflow = DocumentAutomationWorkflow(timeout=600, verbose=True)
            await self._run_workflow(workflow, file_ids)

    async def _handle_retry_match(self, data: dict):
        file_id = data.get("file_id")
        if not file_id:
            return

        logger.info(f"Retrying match for file: {file_id}")
        
        async with sessionmanager.session() as db:
            await self.storage.update_doc(db, file_id, reconciliation_notes=None, discrepancies=None)
            file_ids = [file_id]

        if file_ids:
            logger.info(f"Triggering workflow with {len(file_ids)} files")
            workflow = DocumentAutomationWorkflow(timeout=600, verbose=True)
            await self._run_workflow(workflow, file_ids)

    async def _run_workflow(self, workflow: DocumentAutomationWorkflow, file_ids: list[str]):
        try:
            logger.info(f"Starting workflow for files: {file_ids}")
            handler = workflow.run(file_ids=file_ids)

            async for event in handler.stream_events():
                if isinstance(event, StatusEvent):
                    await self._handle_status_event(event)
                elif isinstance(event, ProcessingCompleteEvent):
                    await self._handle_completion_event(event)

            await handler
            logger.info(f"Workflow completed successfully.")
            await self._broadcast_list_update()

        except WebSocketDisconnect:
            logger.warning(f"WebSocket disconnected during workflow")
        except Exception as e:
            logger.error(f"Error in websocket workflow: {e}", exc_info=True)
            pass

    async def _handle_status_event(self, event: StatusEvent):
        if not event.file_id:
            return

        color = "bg-purple-900 text-purple-200 border border-purple-700"
        if event.level == "error":
            color = "bg-red-900 text-red-200 border border-red-700"

        html = self._create_status_html(event.file_id, event.message, color)
        await self.ws_manager.send_text(html)

    async def _handle_completion_event(self, event: ProcessingCompleteEvent):
        await self._broadcast_list_update()

    @staticmethod
    def _create_status_html(file_id: str, message: str, color_class: str) -> str:
        return templates.get_template("extraction/partials/status_badge.html").render(
            run_id=file_id,
            message=message,
            color_class=color_class
        )

    async def _broadcast_list_update(self):
        async with sessionmanager.session() as db:
            root_docs, children_map = await self.storage.get_dashboard_view_data(db)
            
            html = templates.get_template("extraction/partials/list.html").render(
                documents=root_docs,
                children_map=children_map
            )
            
            wrapper = f'<div id="file-list" hx-swap-oob="innerHTML">{html}</div>'
            await self.ws_manager.send_text(wrapper)