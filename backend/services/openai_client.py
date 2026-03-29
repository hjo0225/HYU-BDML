"""OpenAI 클라이언트 싱글턴"""
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

_client = None

def get_client() -> OpenAI:
    """OpenAI 클라이언트 싱글턴 반환"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client
