"""选品报告 Agent（④ AI 层）

输入: 榜单快照数据（Agent 自主调用工具查询）
输出: 选品报告 markdown，保存到 data/reports/selection_report_{时间戳}.md

用法: python -m agent.selection_agent
"""
import sys
from datetime import datetime
from pathlib import Path

from agent.llm_client import run_agent
from agent.tools import TOOL_DEFS

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "reports"

SYSTEM_PROMPT = """你是跨境电商选品分析师，基于亚马逊榜单快照数据做选品建议。

工作方式:
1. 先用工具查看市场数据: market_price_stats、market_rating_stats、category_competitiveness、hot_products、query_rank_changes
2. 找出 2-3 个值得切入的产品机会: 需求热度高（评论数多）且竞争有缝隙（评分门槛可突破/价格带空缺）的方向
3. 每个机会说明: 参考商品、切入理由（引用工具数据）、风险提示

要求:
- 所有数字必须来自工具查询结果，禁止编造
- 中文输出 markdown: ## 市场概览 → ## 产品机会 → ## 风险与建议
- 总长度 600 字以内"""


def main():
    user_msg = ("请基于最新榜单快照数据输出一份选品报告。"
                "关注: 各品类价格带与评分门槛、热门商品特征、类目竞争度。")
    print("🔎 选品 Agent 启动（DeepSeek）...")
    report = run_agent(SYSTEM_PROMPT, TOOL_DEFS, user_msg)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"selection_report_{datetime.now():%Y%m%d_%H%M}.md"
    path.write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\n✅ 报告已保存: {path}")


if __name__ == "__main__":
    main()
