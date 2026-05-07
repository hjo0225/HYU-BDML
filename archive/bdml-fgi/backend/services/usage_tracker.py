"""API 토큰 사용량 추적 모듈"""
import time
from dataclasses import dataclass, field
from threading import Lock

# gpt-4o 가격 (USD per 1K tokens)
_PRICING = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}
_DEFAULT_PRICE = {"input": 0.00015, "output": 0.0006}

# 환율 (대략적 추정용)
_KRW_PER_USD = 1450


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD 비용 계산"""
    price = _PRICING.get(model, _DEFAULT_PRICE)
    return (input_tokens / 1000 * price["input"]) + (output_tokens / 1000 * price["output"])


@dataclass
class CallRecord:
    """개별 API 호출 기록"""
    service: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float


@dataclass
class UsageTracker:
    """세션 내 토큰 사용량 누적 추적"""
    records: list[CallRecord] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def _cumulative_cost(self) -> float:
        """누적 비용 (USD)"""
        return sum(r.cost_usd for r in self.records)

    def log(self, service: str, model: str, input_tokens: int, output_tokens: int):
        """호출 기록 추가 + 콘솔 출력"""
        cost = _calc_cost(model, input_tokens, output_tokens)
        record = CallRecord(
            service=service,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=time.time(),
        )
        with self._lock:
            self.records.append(record)
            cumulative = self._cumulative_cost()

        cost_krw = cost * _KRW_PER_USD
        cum_krw = cumulative * _KRW_PER_USD
        print(
            f"[💰 API] {service} | "
            f"토큰 {input_tokens:,}+{output_tokens:,} | "
            f"이번 ${cost:.4f} (≈{cost_krw:.1f}원) | "
            f"누적 ${cumulative:.4f} (≈{cum_krw:.0f}원)"
        )

    def summary(self) -> dict:
        """누적 사용량 요약 반환"""
        with self._lock:
            records = list(self.records)

        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)
        total_cost = sum(r.cost_usd for r in records)
        total_calls = len(records)

        # 서비스별 집계
        by_service: dict[str, dict] = {}
        for r in records:
            if r.service not in by_service:
                by_service[r.service] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            s = by_service[r.service]
            s["calls"] += 1
            s["input_tokens"] += r.input_tokens
            s["output_tokens"] += r.output_tokens
            s["cost_usd"] = round(s["cost_usd"] + r.cost_usd, 4)

        return {
            "total_calls": total_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "estimated_cost_usd": round(total_cost, 4),
            "estimated_cost_krw": round(total_cost * _KRW_PER_USD),
            "by_service": by_service,
        }

    def reset(self):
        """기록 초기화"""
        with self._lock:
            self.records.clear()
        print("[💰 API] 사용량 기록 초기화됨")


# 싱글턴 인스턴스
tracker = UsageTracker()
