"""启动采集（独立入口脚本）

一键运行亚马逊 Best Sellers 榜单采集，无需启动完整的一键启动流程。

是否无头由 config/settings.yaml 的 collect.headless 决定（默认 true=无头）。
命令行 --headful 可临时覆盖为有头（显示浏览器窗口）。

用法:
    python start_collect.py             # 按 settings.yaml 的 collect.headless 执行
    python start_collect.py --headful   # 强制显示浏览器窗口，便于调试选择器
"""
import argparse
import sys

from collectors.amazon_bestseller import run_all

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    parser = argparse.ArgumentParser(description="启动亚马逊 Best Sellers 榜单采集")
    parser.add_argument("--headful", action="store_true",
                        help="显示浏览器窗口，覆盖 settings.yaml 的 collect.headless（调试用）")
    args = parser.parse_args()
    run_all(headless=False if args.headful else None)


if __name__ == "__main__":
    main()
