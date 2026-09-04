"""订单清洗规则测试：覆盖去重、脏数据过滤、类型标准化"""
import pandas as pd
import pytest

from collectors.order_importer import clean


def _dirty_df() -> pd.DataFrame:
    """构造覆盖各种脏数据场景的订单表"""
    return pd.DataFrame({
        "order_id": ["O1", "O1", "O2", "", "O3", None],
        "order_date": ["2026-08-01", "2026-08-01", "2026-08-02",
                       "2026-08-03", "bad-date", "2026-08-04"],
        "asin": ["A1", "A1", "A2", "A3", "A4", "A5"],
        "quantity": [1, 1, 2, 1, 1, 1],
        "unit_price": ["$10.50", "$10.50", 25, 0, 8, 15],
    })


def test_clean_dedup_and_filters():
    """预期只剩 2 行: O1 去重后 1 行 + O2。
    剔除: 空串 order_id、None order_id、价格 0、坏日期"""
    out = clean(_dirty_df())
    assert len(out) == 2
    assert set(out["order_id"]) == {"O1", "O2"}


def test_clean_price_parsing():
    out = clean(_dirty_df())
    row = out[out["order_id"] == "O1"].iloc[0]
    assert row["unit_price"] == 10.5
    assert row["quantity"] == 1


def test_clean_fills_defaults():
    out = clean(_dirty_df())
    assert set(out["currency"]) == {"USD"}
    assert set(out["channel"]) == {"amazon"}


def test_clean_missing_required_columns():
    with pytest.raises(ValueError):
        clean(pd.DataFrame({"order_id": ["x"]}))
