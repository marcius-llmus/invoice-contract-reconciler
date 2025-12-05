import functools
import os

import httpx
from llama_cloud.client import AsyncLlamaCloud
from llama_cloud_services.beta.classifier.client import ClassifyClient
from llama_cloud_services.beta.sheets import LlamaSheets
from llama_cloud_services.parse import LlamaParse, ResultType
from llama_index.llms.openai import OpenAI


@functools.lru_cache(maxsize=None)
def get_llama_cloud_client() -> AsyncLlamaCloud:
    token = os.getenv("LLAMA_CLOUD_API_KEY")
    if not token:
        raise ValueError("LLAMA_CLOUD_API_KEY is not set")
    return AsyncLlamaCloud(
        token=token,
        base_url=os.getenv("LLAMA_CLOUD_BASE_URL"),
        timeout=60,
    )


@functools.lru_cache(maxsize=None)
def get_sheets_client() -> LlamaSheets:
    return LlamaSheets(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        base_url=os.getenv("LLAMA_CLOUD_BASE_URL"),
    )


@functools.lru_cache(maxsize=None)
def get_classifier_client() -> ClassifyClient:
    return ClassifyClient(
        client=get_llama_cloud_client(),
        project_id=os.getenv("LLAMA_DEPLOY_PROJECT_ID"),
    )


@functools.lru_cache(maxsize=None)
def get_parser() -> LlamaParse:
    return LlamaParse(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        result_type=ResultType.MD,
        verbose=True,
    )


@functools.lru_cache(maxsize=None)
def get_llm() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set")
    return OpenAI(model="gpt-4.1-mini", temperature=0)


@functools.lru_cache(maxsize=None)
def get_httpx_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=60)
