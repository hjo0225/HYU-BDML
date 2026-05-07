"""역채점 유틸리티."""


def reverse(value: int | float, max_value: int | float, min_value: int | float = 1) -> float:
    """리커트 역채점: max_val + min_val - value."""
    return max_value + min_value - value
