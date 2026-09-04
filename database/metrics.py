"""指标体系（② 数据层核心）—— 经营指标 12 项 + 市场竞品指标 6 项，共 18 项

用法:
    python -m database.metrics               # 控制台输出完整经营分析报告
    from database.metrics import gmv, aov    # 其他模块（大屏/AI）按需调用单个指标

口径说明（面试素材，详见 docs/指标字典.md）:
- 收入类指标只统计 status='Shipped' 的订单（取消/待处理不计入 GMV）
- 亚马逊不公开销量，评论数(review_count)作为需求热度代理指标
"""
import sys

import pandas as pd

from database.db import get_engine

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ENGINE = None


def _engine():
    """懒加载引擎：模块导入时不连库，第一次查询才连接（常驻服务更稳健）"""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = get_engine()
    return _ENGINE

PRICE_BANDS = [0, 15, 30, 60, float("inf")]
PRICE_LABELS = ["$0-15", "$15-30", "$30-60", "$60+"]


# ---------- 数据加载 ----------

def load_orders() -> pd.DataFrame:
    """加载订单数据，附带 gmv 计算列"""
    df = pd.read_sql("SELECT * FROM fact_order", _engine())
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["gmv"] = df["quantity"] * df["unit_price"]
    return df


def load_snapshots() -> pd.DataFrame:
    """加载榜单快照（关联商品维度，带标题和品类）"""
    df = pd.read_sql(
        """SELECT s.asin, s.captured_at, s.position, s.price, s.rating, s.review_count,
                  p.title, p.category
           FROM fact_snapshot s LEFT JOIN dim_product p ON p.asin = s.asin""",
        _engine(),
    )
    df["captured_at"] = pd.to_datetime(df["captured_at"])
    return df


def shipped(df: pd.DataFrame) -> pd.DataFrame:
    """收入口径：只统计已发货订单；同时确保 gmv 计算列存在（函数自洽，不依赖调用方预计算）"""
    d = df[df["status"] == "Shipped"]
    if "gmv" not in d.columns:
        d = d.copy()
        d["gmv"] = d["quantity"] * d["unit_price"]
    return d


# ---------- 一、经营指标（fact_order） ----------

def gmv(df=None) -> float:
    """GMV 总销售额 = Σ(数量×单价)，只含已发货订单"""
    return round(float(shipped(df if df is not None else load_orders())["gmv"].sum()), 2)


def order_count(df=None) -> int:
    """已发货订单数"""
    return int(len(shipped(df if df is not None else load_orders())))


def units_sold(df=None) -> int:
    """销量件数"""
    return int(shipped(df if df is not None else load_orders())["quantity"].sum())


def aov(df=None) -> float:
    """客单价 AOV = GMV ÷ 订单数"""
    d = shipped(df if df is not None else load_orders())
    return round(float(d["gmv"].sum() / len(d)), 2) if len(d) else 0.0


def avg_daily_gmv(df=None) -> float:
    """日均 GMV = GMV ÷ 有销售的天数"""
    d = shipped(df if df is not None else load_orders())
    days = d["order_date"].dt.date.nunique()
    return round(gmv(d) / days, 2) if days else 0.0


def cancellation_rate(df=None) -> float:
    """取消率 = Cancelled 订单占比（含取消单的全量口径）"""
    d = df if df is not None else load_orders()
    return round(float((d["status"] == "Cancelled").mean() * 100), 1)


def repeat_purchase_sku_ratio(df=None) -> float:
    """复购SKU占比 = 出现 ≥2 次购买的 SKU 数 ÷ 全部 SKU 数
    （订单表无客户维度时的代理口径，真实场景应升级为按客户维度计算）"""
    d = shipped(df if df is not None else load_orders())
    counts = d.groupby("asin")["order_id"].nunique()
    return round(float((counts >= 2).mean() * 100), 1)


def top_sku_concentration(df=None, top=10) -> float:
    """头部集中度 = TOP N SKU 的 GMV 占比（爆款依赖风险）"""
    d = shipped(df if df is not None else load_orders())
    per = d.groupby("asin")["gmv"].sum().sort_values(ascending=False)
    return round(float(per.head(top).sum() / per.sum() * 100), 1)


def monthly_trend(df=None) -> pd.DataFrame:
    """月度 GMV/订单趋势 + GMV 环比"""
    d = shipped(df if df is not None else load_orders()).copy()
    d["month"] = d["order_date"].dt.to_period("M").astype(str)
    out = d.groupby("month", as_index=False).agg(
        订单数=("order_id", "count"), GMV=("gmv", "sum"), 销量=("quantity", "sum"))
    out["GMV环比%"] = (out["GMV"].pct_change() * 100).round(1)
    return out


def weekday_analysis(df=None) -> pd.DataFrame:
    """一周各天平均订单量（验证周末效应，指导运营排期）"""
    d = shipped(df if df is not None else load_orders()).copy()
    d["weekday"] = d["order_date"].dt.dayofweek  # 0=周一
    d["day"] = d["order_date"].dt.date
    daily = d.groupby(["day", "weekday"]).size().reset_index(name="orders")
    out = daily.groupby("weekday")["orders"].mean().round(1).reset_index()
    out.columns = ["星期(0=周一)", "日均订单"]
    return out


def category_breakdown(df=None) -> pd.DataFrame:
    """品类销售结构：GMV / 订单数 / 占比"""
    d = shipped(df if df is not None else load_orders())
    out = d.groupby("category", as_index=False).agg(
        GMV=("gmv", "sum"), 订单数=("order_id", "count"), 销量=("quantity", "sum"))
    out["GMV占比%"] = (out["GMV"] / out["GMV"].sum() * 100).round(1)
    return out.sort_values("GMV", ascending=False).reset_index(drop=True)


def price_band_distribution(df=None) -> pd.DataFrame:
    """价格带分布：各价格区间订单数与 GMV 占比（定价策略依据）"""
    d = shipped(df if df is not None else load_orders()).copy()
    d["price_band"] = pd.cut(d["unit_price"], bins=PRICE_BANDS,
                             labels=PRICE_LABELS, right=False)
    out = d.groupby("price_band", observed=True).agg(
        订单数=("order_id", "count"), GMV=("gmv", "sum")).reset_index()
    out["订单占比%"] = (out["订单数"] / out["订单数"].sum() * 100).round(1)
    return out


# ---------- 二、市场竞品指标（fact_snapshot × dim_product） ----------

def market_price_stats(snap=None) -> pd.DataFrame:
    """各品类榜单价格：均值 / 中位数 / 极值（选品定价参考）"""
    d = snap if snap is not None else load_snapshots()
    d = d[d["price"].notna()]
    return d.groupby("category", as_index=False).agg(
        商品数=("asin", "nunique"), 均价=("price", "mean"), 中位价=("price", "median"),
        最低价=("price", "min"), 最高价=("price", "max")).round(2)


def market_rating_stats(snap=None) -> pd.DataFrame:
    """各品类评分：平均分 + 高分占比（≥4.5 是市场进入门槛）"""
    d = snap if snap is not None else load_snapshots()
    d = d[d["rating"].notna()]
    out = d.groupby("category", as_index=False).agg(
        平均评分=("rating", "mean"),
        高分占比=("rating", lambda s: (s >= 4.5).mean() * 100))
    out["平均评分"] = out["平均评分"].round(2)
    out["高分占比"] = out["高分占比"].round(1)
    return out


def hot_products(snap=None, top=10) -> pd.DataFrame:
    """热门商品榜：按评论数（需求热度代理）TOP N，每个 ASIN 取最新快照"""
    d = snap if snap is not None else load_snapshots()
    d = d[d["review_count"].notna()].sort_values("captured_at")
    latest = d.drop_duplicates(subset="asin", keep="last")
    out = latest.nlargest(top, "review_count")[
        ["title", "category", "position", "price", "rating", "review_count"]]
    return out.reset_index(drop=True)


def price_review_relationship(snap=None) -> pd.DataFrame:
    """价格带 × 平均评论数：判断各价格带的需求热度分布"""
    d = (snap if snap is not None else load_snapshots()).copy()
    d = d[d["price"].notna() & d["review_count"].notna()].sort_values("captured_at")
    d = d.drop_duplicates(subset="asin", keep="last")
    d["price_band"] = pd.cut(d["price"], bins=PRICE_BANDS,
                             labels=PRICE_LABELS, right=False)
    out = d.groupby("price_band", observed=True).agg(
        商品数=("asin", "nunique"), 平均评论数=("review_count", "mean")).reset_index()
    out["平均评论数"] = out["平均评论数"].round(0).astype(int)
    return out


def category_competitiveness(snap=None) -> pd.DataFrame:
    """类目竞争度：低价占比高 + 高分占比高 = 竞争激烈（进入决策依据）"""
    d = (snap if snap is not None else load_snapshots()).copy()
    d = d.sort_values("captured_at").drop_duplicates(subset="asin", keep="last")
    low_price = d[d["price"].notna()].groupby("category")["price"].apply(
        lambda s: (s < 20).mean() * 100)
    high_rating = d[d["rating"].notna()].groupby("category")["rating"].apply(
        lambda s: (s >= 4.5).mean() * 100)
    n = d.groupby("category")["asin"].nunique()
    out = pd.DataFrame({"商品数": n, "低价占比%": low_price, "高分占比%": high_rating}).round(1)
    return out.reset_index()


def rank_changes(category=None, snap=None):
    """榜单动态：按品类对比最近两次采集批次的排名变化，返回 (上升榜, 下降榜)
    需要同一品类至少两批采集数据，否则返回 None"""
    d = snap if snap is not None else load_snapshots()
    if category:
        d = d[d["category"] == category]
    frames = []
    for cat, g in d.groupby("category"):
        times = sorted(g["captured_at"].unique())
        if len(times) < 2:
            continue
        prev, cur = times[-2], times[-1]
        a = g[g["captured_at"] == prev][["asin", "position"]].rename(
            columns={"position": "prev_pos"})
        b = g[g["captured_at"] == cur][["asin", "position"]].rename(
            columns={"position": "cur_pos"})
        m = a.merge(b, on="asin")
        if m.empty:
            continue
        m["change"] = m["prev_pos"] - m["cur_pos"]  # 正值 = 排名上升
        m["category"] = cat
        frames.append(m)
    if not frames:
        return None
    all_m = pd.concat(frames)
    info = d[["asin", "title"]].drop_duplicates("asin")
    all_m = all_m.merge(info, on="asin", how="left").sort_values("change", ascending=False)
    risers = all_m.head(5)[
        ["title", "category", "prev_pos", "cur_pos", "change"]].reset_index(drop=True)
    fallers = all_m.tail(5).sort_values("change")[
        ["title", "category", "prev_pos", "cur_pos", "change"]].reset_index(drop=True)
    return risers, fallers


# ---------- 报告 ----------

def generate_report():
    """控制台版经营分析报告（Week 3 上大屏、Week 4 交给 AI 解读）"""
    orders = load_orders()
    snaps = load_snapshots()

    print("=" * 28, "店铺经营概览", "=" * 28)
    print(f"GMV: ${gmv(orders):,.0f} | 订单数: {order_count(orders)} | "
          f"销量: {units_sold(orders)} 件")
    print(f"客单价: ${aov(orders)} | 取消率: {cancellation_rate(orders)}% | "
          f"复购SKU占比: {repeat_purchase_sku_ratio(orders)}%")
    print(f"日均GMV: ${avg_daily_gmv(orders):,.0f} | "
          f"头部集中度(TOP10 SKU): {top_sku_concentration(orders)}%")

    print("\n月度趋势(近6个月):")
    print(monthly_trend(orders).tail(6).to_string(index=False))

    print("\n一周订单分布(日均):")
    print(weekday_analysis(orders).to_string(index=False))

    print("\n品类结构:")
    print(category_breakdown(orders).to_string(index=False))

    print("\n价格带分布:")
    print(price_band_distribution(orders).to_string(index=False))

    print("\n" + "=" * 28, "市场与竞品概览", "=" * 28)
    print("\n各品类榜单价格:")
    print(market_price_stats(snaps).to_string(index=False))

    print("\n各品类评分:")
    print(market_rating_stats(snaps).to_string(index=False))

    print("\n热门商品 TOP10（按评论数=需求热度代理）:")
    print(hot_products(snaps).to_string(index=False))

    print("\n价格带-需求关系:")
    print(price_review_relationship(snaps).to_string(index=False))

    print("\n类目竞争度:")
    print(category_competitiveness(snaps).to_string(index=False))

    rc = rank_changes(snap=snaps)
    if rc:
        risers, fallers = rc
        print("\n榜单动态(最近两批采集对比): 排名上升 TOP5")
        print(risers.to_string(index=False))
        print("排名下降 TOP5")
        print(fallers.to_string(index=False))
    else:
        print("\n榜单动态: 目前只有一批采集数据，明天再跑一次采集即可对比排名变化")


if __name__ == "__main__":
    generate_report()
