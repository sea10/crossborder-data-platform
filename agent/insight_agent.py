"""经营解读 Agent（④ AI 层）

输入: 数据库最新指标（Agent 自主调用工具查询）
输出: 经营分析解读 —— 核心指标摘要 + 异动归因 + 行动建议

用法: python -m agent.insight_agent
"""
import sys
from datetime import datetime

from agent.llm_client import run_agent
from agent.tools import TOOL_DEFS

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SYSTEM_PROMPT = """你是跨境电商公司的数据分析师，负责解读店铺经营数据。

工作方式:
1. 先用工具查询核心指标（gmv、order_count、aov、cancellation_rate、repeat_purchase_sku_ratio、top_sku_concentration、monthly_trend）
2. 识别值得关注的异动（环比下滑/取消率偏高/头部过度集中等），结合 category_breakdown 尝试归因
3. 给出 3 条以内、可执行的行动建议

要求:
- 所有数字必须来自工具查询结果，禁止编造
- 中文输出 markdown 格式: ## 核心指标 → ## 异动与归因 → ## 行动建议
- 简洁专业，总长度 400 字以内"""


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    user_msg = (f"请基于最新数据解读店铺经营情况（今天是 {today}）。"
                f"重点关注: 月度趋势与环比、取消率、品类结构、头部集中度。")
    print("🤖 经营解读 Agent 启动（DeepSeek）...")
    report = run_agent(SYSTEM_PROMPT, TOOL_DEFS, user_msg)
    print("\n" + report)


if __name__ == "__main__":
    main()
