"""OpenAI / Anthropic API 환경변수 유틸리티."""
import os


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} 환경변수가 필요합니다.")
    return value.strip()
