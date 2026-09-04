"""指标体系测试：用合成订单 DataFrame 验证口径（无需数据库）"""
import pandas as pd

from database import metrics as m


def _orders() -> pd.DataFrame:
    return pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4"],
        "order_date": pd.to_datetime(
            ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]),
        "asin": ["A1", "A1", "A2", "A2"],
        "title": ["t1", "t1", "t2", "t2"],
        "category": ["Kitchen", "Kitchen", "Beauty", "Beauty"],
        "quantity": [2, 1, 3, 1],
        "unit_price": [10.0, 20.0, 5.0, 5.0],
        "currency": ["USD"] * 4,
        "channel": ["amazon"] * 4,
        "status": ["Shipped", "Shipped", "Cancelled", "Shipped"],
    })


def test_gmv_only_counts_shipped():
    """口径: GMV 只统计 Shipped = 2*10 + 1*20 + 1*5 = 45（O3 取消单不计入）"""
    assert m.gmv(_orders()) == 45.0


def test_order_count_and_units():
    assert m.order_count(_orders()) == 3
    assert m.units_sold(_orders()) == 4


def test_aov():
    assert m.aov(_orders()) == 15.0  # 45 / 3 单


def test_cancellation_rate_full_scope():
    """取消率用全量订单（含取消单）计算 = 1/4 = 25%"""
    assert m.cancellation_rate(_orders()) == 25.0


def test_repeat_purchase_sku_ratio():
    """A1 有 2 单，A2 有 1 单已发货（其取消单不计）-> 复购SKU占比 50%"""
    assert m.repeat_purchase_sku_ratio(_orders()) == 50.0


def test_price_band_distribution_excludes_cancelled():
    out = m.price_band_distribution(_orders())
    assert out["订单数"].sum() == 3  # O3 取消单不进价格带统计
