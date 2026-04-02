"""OpenAI / 외부 API 환경변수 유틸리티.

이 모듈은 .env 파일을 읽지 않는다.
운영체제의 시스템 환경변수만 사용한다.
"""
import os


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} 시스템 환경변수가 필요합니다.")
    return value.strip()
