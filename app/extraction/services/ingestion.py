import base64
import os
import tempfile
import uuid
from app.extraction.clients import get_llama_cloud_client, get_httpx_client
from app.extraction.events import FileInfo


class IngestionService:
    """Service for handling file downloads and local storage."""

    @staticmethod
    async def download_file(file_id: str) -> FileInfo:
        """Downloads a file from LlamaCloud to a temporary local path."""
        client = get_llama_cloud_client()
        
        # Fetch metadata and download URL
        file_meta = await client.files.get_file(file_id)
        content_url = await client.files.read_file_content(file_id)

        # Stream to temp file
        temp_dir = tempfile.gettempdir()
        file_path = str(os.path.join(temp_dir, file_meta.name))

        httpx_client = get_httpx_client()
        async with httpx_client.stream("GET", content_url.url) as response:
            with open(file_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

        return FileInfo(file_id=file_id, file_path=file_path, filename=file_meta.name)

    @staticmethod
    async def upload_from_base64(filename: str, content_b64: str) -> str:
        """Handles a base64 upload, saves to temp, uploads to LlamaCloud, returns file_id."""
        temp_path = f"/tmp/{uuid.uuid4()}_{filename}"
        try:
            file_bytes = base64.b64decode(content_b64)
            with open(temp_path, "wb") as f:
                f.write(file_bytes)

            client = get_llama_cloud_client()
            with open(temp_path, "rb") as f:
                llama_file = await client.files.upload_file(upload_file=(filename, f))
            
            return llama_file.id
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
