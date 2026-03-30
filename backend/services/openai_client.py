"""OpenAI 클라이언트 싱글턴"""
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

_client = None
_async_client = None

def get_client() -> OpenAI:
    """동기 OpenAI 클라이언트 싱글턴 반환"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

def get_async_client() -> AsyncOpenAI:
    """비동기 OpenAI 클라이언트 싱글턴 반환"""
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _async_client
