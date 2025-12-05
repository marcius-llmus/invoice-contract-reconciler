import logging

from starlette.websockets import WebSocket


logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def send_json(self, data: dict):
        logger.debug(f"Sending JSON message: {data}")
        await self.websocket.send_json(data)

    async def send_text(self, data: str):
        logger.debug(f"Sending text message: {data}")
        await self.websocket.send_text(data)
