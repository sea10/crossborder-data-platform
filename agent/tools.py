"""Agent 工具集（④ AI 层）

把 metrics 的 18 项指标包装成 LLM 可调用的工具。
设计要点:
- 工具返回精简文本（限行数 + 长文本截断），控制 token 消耗
- 工具内部全兜底：任何异常都返回错误文本而非抛出，模型读得到、可自行调整
"""
import pandas as pd
from pandas.api.types import is_string_dtype

from database import metrics as m


def _df_to_text(df: pd.DataFrame, max_rows: int = 12, max_col_width: int = 50) -> str:
    """DataFrame 转精简文本：限行 + 长文本截断（控制 token）"""
    if df.empty:
        return "（无数据）"
    out = df.head(max_rows).copy()
    for col in out.columns:
        if is_string_dtype(out[col]):  # 兼容 object 与 StringDtype（pandas 3.0）
            out[col] = out[col].astype(str).str.slice(0, max_col_width)
    return out.to_string(index=False)


METRIC_FUNCS = {
    "gmv": lambda: f"${m.gmv():,.0f}",
    "order_count": lambda: f"{m.order_count():,} 单",
    "aov": lambda: f"${m.aov():,.2f}",
    "cancellation_rate": lambda: f"{m.cancellation_rate()}%",
    "repeat_purchase_sku_ratio": lambda: f"{m.repeat_purchase_sku_ratio()}%",
    "top_sku_concentration": lambda: f"{m.top_sku_concentration()}%",
    "avg_daily_gmv": lambda: f"${m.avg_daily_gmv():,.0f}",
    "monthly_trend": lambda: _df_to_text(m.monthly_trend().tail(6)),
    "category_breakdown": lambda: _df_to_text(m.category_breakdown()),
    "weekday_analysis": lambda: _df_to_text(m.weekday_analysis()),
    "price_band_distribution": lambda: _df_to_text(m.price_band_distribution()),
    "market_price_stats": lambda: _df_to_text(m.market_price_stats()),
    "market_rating_stats": lambda: _df_to_text(m.market_rating_stats()),
    "category_competitiveness": lambda: _df_to_text(m.category_competitiveness()),
    "price_review_relationship": lambda: _df_to_text(m.price_review_relationship()),
}

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "query_metric",
            "description": "查询店铺经营或市场竞品的单个指标/报表。metric 可选值: "
                           + ", ".join(METRIC_FUNCS),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": list(METRIC_FUNCS)},
                },
                "required": ["metric"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_hot_products",
            "description": "按评论数（需求热度代理）查询热门商品榜",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "minimum": 3, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_rank_changes",
            "description": "查询榜单排名变化（上升/下降各 TOP5，需至少两批采集数据）",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "品类名，可省略"},
                },
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """执行工具并返回文本结果。任何异常都转成错误文本（不抛出，模型可自行调整）"""
    try:
        if name == "query_metric":
            metric = args.get("metric", "")
            if metric not in METRIC_FUNCS:
                return f"未知指标 '{metric}'，可选值: {', '.join(METRIC_FUNCS)}"
            return METRIC_FUNCS[metric]()
        if name == "query_hot_products":
            return _df_to_text(m.hot_products(top=int(args.get("top_n", 10))))
        if name == "query_rank_changes":
            rc = m.rank_changes(category=args.get("category"))
            if rc is None:
                return "目前只有一批采集数据，无法对比排名变化。明天再跑一次采集即可。"
            risers, fallers = rc
            return ("排名上升 TOP5:\n" + _df_to_text(risers)
                    + "\n\n排名下降 TOP5:\n" + _df_to_text(fallers))
        return f"未知工具: {name}"
    except Exception as e:
        return f"工具执行失败: {e}"
