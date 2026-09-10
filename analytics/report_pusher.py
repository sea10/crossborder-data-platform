"""每日经营日报生成与飞书推送（③ 分析层）

日报 = 核心经营指标 + TOP品类 + 异常提醒（阈值规则检测）
用法:
    python -m analytics.report_pusher          # 生成日报并推送到飞书
    python -m analytics.report_pusher --dry    # 只打印日报内容，不推送（调试用）
"""
import argparse
from datetime import datetime

import requests

from database import metrics as m
from database.db import load_config
from utils.logger import get_logger

logger = get_logger("report")

# 异常阈值（指标异动检测的规则版基线；深度归因由 AI Agent 完成）
CANCEL_RATE_THRESHOLD = 8.0    # 取消率超过 8% 告警
GMV_DROP_THRESHOLD = -10.0     # 完整月 GMV 环比下降超 10% 告警


def build_report_text() -> str:
    """组装日报文本（纯文本格式，飞书 text 消息）"""
    orders = m.load_orders()
    trend = m.monthly_trend(orders)
    cat = m.category_breakdown(orders)

    alerts = []
    cancel = m.cancellation_rate(orders)
    if cancel > CANCEL_RATE_THRESHOLD:
        alerts.append(f"⚠️ 取消率 {cancel}% 超过 {CANCEL_RATE_THRESHOLD}% 阈值，建议排查库存/物流")

    # 最后一个自然月数据不完整（当月），环比取完整月
    full_months = trend.iloc[:-1]
    if len(full_months) >= 2:
        mom = full_months.iloc[-1]["GMV环比%"]
        if mom < GMV_DROP_THRESHOLD:
            alerts.append(f"⚠️ 上月 GMV 环比 {mom}%，下滑超阈值，建议关注流量与转化")

    lines = [
        f"📊 跨境电商经营日报 · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 GMV: ${m.gmv(orders):,.0f} ｜ 订单数: {m.order_count(orders)} ｜ 客单价: ${m.aov(orders)}",
        f"📈 日均GMV: ${m.avg_daily_gmv(orders):,.0f} ｜ 复购SKU占比: {m.repeat_purchase_sku_ratio(orders)}%",
        f"🏆 TOP品类: {cat.iloc[0]['category']}（GMV占比 {cat.iloc[0]['GMV占比%']}%）｜ "
        f"头部集中度: {m.top_sku_concentration(orders)}%",
    ]
    if alerts:
        lines += ["", "━━━ 异常提醒 ━━━"] + alerts
    lines += ["", "（完整分析见经营大屏；指标口径见 docs/指标字典.md）"]
    return "\n".join(lines)


def send_feishu(text: str, webhook: str | None = None) -> dict:
    """推送飞书群机器人消息"""
    webhook = webhook or load_config()["notify"]["feishu_webhook"]
    if not webhook:
        raise ValueError("settings.yaml 未配置 notify.feishu_webhook")
    r = requests.post(
        webhook,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=10,
    )
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书推送失败: {data}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成并推送每日经营日报")
    parser.add_argument("--dry", action="store_true", help="只打印日报内容，不推送")
    args = parser.parse_args()
    text = build_report_text()
    if args.dry:
        print(text)
    else:
        send_feishu(text)
        logger.info("日报已推送到飞书")
