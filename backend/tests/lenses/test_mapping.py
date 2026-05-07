"""M4 테스트 — 28 척도 매핑 정합성."""
import pytest
from lenses.mapping import LENS_DEFINITIONS, LENS_GROUPS


def test_28_scales_defined():
    """28개 척도 모두 정의되어야 한다."""
    assert len(LENS_DEFINITIONS) == 28


def test_all_groups_present():
    """L1~L6 + C 그룹이 모두 있어야 한다 (정성 그룹은 L3 에 통합)."""
    expected = {"L1", "L2", "L3", "L4", "L5", "L6", "C"}
    assert expected.issubset(set(LENS_GROUPS.keys()))


def test_l1_has_6_scales():
    assert len(LENS_GROUPS["L1"]) == 6


def test_l2_has_4_scales():
    assert len(LENS_GROUPS["L2"]) == 4


def test_l3_has_4_scales():
    assert len(LENS_GROUPS["L3"]) == 4


def test_l4_has_6_scales():
    assert len(LENS_GROUPS["L4"]) == 6


def test_l5_has_2_scales():
    assert len(LENS_GROUPS["L5"]) == 2


def test_l6_has_3_scales():
    assert len(LENS_GROUPS["L6"]) == 3


def test_control_has_3_scales():
    assert len(LENS_GROUPS["C"]) == 3


def test_each_scale_has_persona_keys_or_is_qualitative():
    """모든 척도는 persona_keys 가 있거나, qualitative/categorical 그룹이어야 한다."""
    for scale_id, sd in LENS_DEFINITIONS.items():
        if sd.scoring_method in ("qualitative", "categorical"):
            continue  # C-1·L3-4 는 persona_params 외부 저장
        assert len(sd.persona_keys) > 0, f"{scale_id} 에 persona_keys 없음"


def test_each_scale_has_input_keys():
    """모든 척도는 input_keys 가 있어야 한다."""
    for scale_id, sd in LENS_DEFINITIONS.items():
        assert len(sd.input_keys) > 0, f"{scale_id} 에 input_keys 없음"
