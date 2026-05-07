"""M4 테스트 — 리커트 채점 + 역채점."""
import pytest
from scoring.likert import likert_mean, likert_sum
from scoring.reverse_score import reverse


def test_reverse_score_basic():
    """5점 척도 역채점: 5 → 1."""
    assert reverse(5, 5, 1) == 1
    assert reverse(1, 5, 1) == 5
    assert reverse(3, 5, 1) == 3


def test_likert_mean_no_reverse():
    responses = {"Q1": 3, "Q2": 4, "Q3": 5}
    result = likert_mean(responses, ["Q1", "Q2", "Q3"])
    assert result == pytest.approx(4.0)


def test_likert_mean_with_reverse():
    """Q2 역채점(5점): 4 → 2. 평균 = (3 + 2 + 5) / 3 = 10/3."""
    responses = {"Q1": 3, "Q2": 4, "Q3": 5}
    result = likert_mean(responses, ["Q1", "Q2", "Q3"], max_val=5, reverse_items=[2])
    assert result == pytest.approx(10 / 3)


def test_likert_sum_basic():
    responses = {"Q1": 2, "Q2": 3}
    result = likert_sum(responses, ["Q1", "Q2"])
    assert result == pytest.approx(5.0)


def test_likert_mean_7point():
    """7점 척도."""
    responses = {f"Q{i}": i for i in range(1, 8)}
    keys = [f"Q{i}" for i in range(1, 8)]
    result = likert_mean(responses, keys, max_val=7)
    assert result == pytest.approx(4.0)
