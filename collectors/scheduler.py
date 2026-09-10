"""定时调度器（① RPA 调度层）

按 settings.yaml 里的时间每天自动执行一轮采集；
任务异常只记日志不退出，调度器保持存活（无人值守的核心要求）。

用法:
    python -m collectors.scheduler --once   # 立即执行一轮采集后退出（测试用）
    python -m collectors.scheduler          # 常驻运行，每日定时执行
"""
import argparse

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from analytics.report_pusher import build_report_text, send_feishu
from collectors.amazon_bestseller import run_all
from database.db import load_config
from utils.logger import get_logger

logger = get_logger("scheduler")


def job():
    """一次完整任务: 采集 -> 日报推送（两步各自隔离异常，互不影响）"""
    try:
        logger.info("====== 定时采集开始 ======")
        run_all()
        logger.info("====== 定时采集完成 ======")
    except Exception:
        logger.exception("采集任务执行失败（调度器继续存活）")
    try:
        send_feishu(build_report_text())
        logger.info("日报已推送到飞书")
    except Exception:
        logger.exception("日报推送失败（不影响调度器存活）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="采集任务定时调度器")
    parser.add_argument("--once", action="store_true", help="立即执行一次后退出")
    args = parser.parse_args()

    if args.once:
        job()
    else:
        sc = load_config()["scheduler"]
        sched = BlockingScheduler()
        sched.add_job(job, CronTrigger(hour=sc["hour"], minute=sc["minute"]))
        logger.info("调度器启动: 每天 %02d:%02d 执行采集（Ctrl+C 退出）", sc["hour"], sc["minute"])
        sched.start()
