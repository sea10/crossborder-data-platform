"""维度模型定义（② 数据层核心）

三张表的设计思路:
- dim_product    商品维度表：竞品/自营商品的基础信息，按 ASIN 唯一
- fact_snapshot  快照事实表：每天采集的榜单排名/价格/评分，用于趋势分析
- fact_order     订单事实表：店铺订单明细，经营指标(GMV/复购等)的来源
"""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DimProduct(Base):
    """商品维度表：一条记录一个 ASIN"""

    __tablename__ = "dim_product"

    asin: Mapped[str] = mapped_column(String(10), primary_key=True, comment="亚马逊商品唯一标识")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="商品标题")
    brand: Mapped[str | None] = mapped_column(String(100), comment="品牌（后续从详情页补充）")
    category: Mapped[str] = mapped_column(String(100), index=True, comment="采集来源类目")
    url: Mapped[str | None] = mapped_column(String(500), comment="商品链接")
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="首次发现时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="最后更新时间"
    )


class FactSnapshot(Base):
    """榜单快照事实表：每次采集追加一条，支持趋势分析"""

    __tablename__ = "fact_snapshot"
    __table_args__ = (
        UniqueConstraint("asin", "captured_at", "position", name="uq_snapshot"),
        Index("ix_snapshot_asin_time", "asin", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asin: Mapped[str] = mapped_column(String(10), comment="商品")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="采集时间")
    position: Mapped[int] = mapped_column(Integer, comment="榜单排名")
    price: Mapped[float | None] = mapped_column(Float, comment="价格(USD)")
    rating: Mapped[float | None] = mapped_column(Float, comment="评分(0-5)")
    review_count: Mapped[int | None] = mapped_column(Integer, comment="评论总数")


class FactOrder(Base):
    """订单事实表：来自卖家后台导出的订单报表"""

    __tablename__ = "fact_order"
    __table_args__ = (
        UniqueConstraint("order_id", "asin", name="uq_order_asin"),
        Index("ix_order_date", "order_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(50), comment="订单号")
    order_date: Mapped[datetime] = mapped_column(DateTime, comment="下单时间")
    asin: Mapped[str] = mapped_column(String(10), comment="商品")
    title: Mapped[str | None] = mapped_column(String(500), comment="商品标题快照")
    category: Mapped[str | None] = mapped_column(String(50), comment="品类（自营SKU归属）")
    quantity: Mapped[int] = mapped_column(Integer, default=1, comment="购买数量")
    unit_price: Mapped[float] = mapped_column(Float, comment="成交单价")
    currency: Mapped[str] = mapped_column(String(10), default="USD", comment="币种")
    channel: Mapped[str] = mapped_column(String(30), default="amazon", comment="销售渠道")
    status: Mapped[str] = mapped_column(String(30), default="Shipped", comment="订单状态")
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="导入时间")
