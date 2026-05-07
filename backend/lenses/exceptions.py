"""Lens 파이프라인 예외 클래스."""


class LensValidationError(ValueError):
    """입력 스키마 검증 실패."""
    pass


class MissingResponseError(LensValidationError):
    """필수 응답 키가 없을 때."""
    def __init__(self, missing_keys: list[str]):
        self.missing_keys = missing_keys
        super().__init__(f"필수 응답 키 누락: {missing_keys}")


class InvalidResponseValueError(LensValidationError):
    """응답 값이 허용 범위를 벗어날 때."""
    def __init__(self, key: str, value, allowed):
        super().__init__(f"키 '{key}'의 값 {value!r}가 허용 범위({allowed})를 벗어남.")
