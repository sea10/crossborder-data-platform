"""订单数据导入器（① RPA 采集层）

把卖家后台导出的订单报表 CSV 清洗后写入 fact_order。
（模拟 RPA 流程中「人工从后台导出 Excel -> 自动入库」这一步）

CSV 契约（列名必须一致，顺序不限）:
    order_id, order_date, asin, title, category, quantity, unit_price, currency, channel, status

用法: python -m collectors.order_importer data/raw/sample_orders.csv
"""
import argparse
from datetime import datetime

import pandas as pd
from sqlalchemy.dialects.mysql import insert

from database.db import get_engine
from database.models import FactOrder
from utils.logger import get_logger

logger = get_logger("importer")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """清洗规则:
    1. 列名规范化（去首尾空格）
    2. 去掉 order_id/asin 为空的脏行
    3. 去重: 同一订单同一商品只保留一行
    4. 类型标准化: 日期解析、价格去货币符号、数量转整数
    5. 过滤业务脏数据: 数量 < 1 或 价格 <= 0
    """
    df = df.copy()
    df.columns = df.columns.str.strip()

    required = ["order_id", "order_date", "asin", "quantity", "unit_price"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少必需列: {missing}")

    df = df.dropna(subset=["order_id", "asin"])
    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["asin"] = df["asin"].astype(str).str.strip()
    df = df[(df["order_id"] != "") & (df["asin"] != "")]  # 转字符串后过滤空串（空串同样是脏数据）

    before = len(df)
    df = df.drop_duplicates(subset=["order_id", "asin"], keep="first")

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)
    df["unit_price"] = (
        df["unit_price"].astype(str)
        .str.replace(r"[$,￥\s]", "", regex=True)
        .replace("", None)
        .astype(float)
    )

    for col, default in (("title", ""), ("category", "未知"), ("currency", "USD"),
                         ("channel", "amazon"), ("status", "Shipped")):
        if col not in df.columns:
            df[col] = default

    df = df[(df["quantity"] >= 1) & (df["unit_price"] > 0) & df["order_date"].notna()]
    logger.info("清洗完成: %s 行 -> %s 行（去重 + 过滤脏数据）", before, len(df))
    return df


def import_csv(path: str):
    df = pd.read_csv(path)
    df = clean(df)
    if df.empty:
        logger.warning("清洗后无有效数据，跳过导入")
        return

    now = datetime.now()
    rows = [
        {**r, "order_date": r["order_date"], "imported_at": now}
        for r in df.to_dict("records")
    ]
    # MySQL 专用 upsert：重复(order_id, asin) 时忽略，保证可重复执行
    stmt = insert(FactOrder).values(rows)
    stmt = stmt.on_duplicate_key_update(quantity=stmt.inserted.quantity)

    with get_engine().begin() as conn:
        conn.execute(stmt)
    logger.info("导入完成: %s 行已写入 fact_order（重复自动更新数量）", len(rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入订单 CSV 到 fact_order")
    parser.add_argument("path", help="CSV 文件路径")
    args = parser.parse_args()
    import_csv(args.path)
