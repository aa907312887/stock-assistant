"""指数 PE 百分位推理：加权重归一口径单测（与 plan 公式一致）。"""

from decimal import Decimal

from app.services.index_pe_percentile_service import weighted_pe_percentile_core


def test_weighted_renormalize_two_of_three():
    """两只有 PE，一只缺失：仅用两只权重重归一加权。"""
    # 原始权重 0.5, 0.3, 0.2 已归一；缺失 PE 的不参与分子分母中的 participating 集合
    pairs = [
        ("A.SZ", Decimal("0.5")),
        ("B.SZ", Decimal("0.3")),
        ("C.SZ", Decimal("0.2")),
    ]
    pe_map = {"A.SZ": Decimal("40"), "B.SZ": None, "C.SZ": Decimal("60")}
    items, idx_pe, ratio, with_pe = weighted_pe_percentile_core(pairs, pe_map)
    assert with_pe == 2
    # participating: 0.5+0.2=0.7 → tilde w_A=0.5/0.7, tilde w_C=0.2/0.7
    # index = 40*0.5/0.7 + 60*0.2/0.7 = (20+12)/0.7 ≈ 45.7143
    assert idx_pe is not None
    assert abs(idx_pe - (32 / 0.7)) < 0.02
    assert ratio is not None and abs(ratio - 0.7) < 1e-6
    assert len(items) == 3


def test_all_pe_missing():
    pairs = [("A.SZ", Decimal("1.0"))]
    pe_map = {"A.SZ": None}
    _, idx_pe, ratio, with_pe = weighted_pe_percentile_core(pairs, pe_map)
    assert idx_pe is None
    assert ratio is None
    assert with_pe == 0


def test_single_constituent():
    pairs = [("A.SZ", Decimal("1.0"))]
    pe_map = {"A.SZ": Decimal("12.34")}
    _, idx_pe, _, with_pe = weighted_pe_percentile_core(pairs, pe_map)
    assert with_pe == 1
    assert idx_pe == 12.34
