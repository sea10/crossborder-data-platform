"""一键启动：定时调度 + 经营大屏 + 自动打开浏览器

用法:
    python start_all.py           # 前台运行，Ctrl+C 停止所有服务
    或双击 启动.bat               # 日常最方便的方式

启动前自动检查: 虚拟环境、settings.yaml 配置、8501 端口占用
说明: 一键启动适合日常开发演示；生产环境定时建议用 Windows 任务计划（见 README）
"""
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
DASH_PORT = 8501
DASH_URL = f"http://localhost:{DASH_PORT}"


def check_env() -> None:
    """启动前环境检查：缺什么提示什么，不让用户面对奇怪的报错"""
    if not PY.exists():
        sys.exit(
            "❌ 未找到虚拟环境 .venv。请先执行:\n"
            "   python -m venv .venv\n"
            "   .venv\\Scripts\\python -m pip install -r requirements.txt\n"
            "   .venv\\Scripts\\python -m playwright install chromium"
        )
    if not (ROOT / "config" / "settings.yaml").exists():
        sys.exit(
            "❌ 未找到 config/settings.yaml。\n"
            "   请复制 config/settings.example.yaml 改名为 settings.yaml，\n"
            "   填入你的 MySQL 密码后重试。"
        )


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_streamlit_config() -> None:
    """Streamlit 首次运行会交互式询问邮箱、卡住启动流程，提前写入默认配置跳过"""
    cred = Path.home() / ".streamlit" / "credentials.toml"
    if not cred.exists():
        cred.parent.mkdir(parents=True, exist_ok=True)
        cred.write_text('[general]\nemail = ""\n', encoding="utf-8")
        print("ℹ️ 已初始化 Streamlit 配置（跳过首次运行的邮箱询问）", flush=True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    check_env()
    ensure_streamlit_config()

    if port_in_use(DASH_PORT):
        print("ℹ️ 大屏已在运行（8501 端口被占用），直接打开浏览器。如需重启请先关闭旧进程。", flush=True)
        webbrowser.open(DASH_URL)
        return

    print("🚀 一键启动: 定时调度（每日 8:30 采集 + 日报推送）+ 经营大屏", flush=True)
    sched = subprocess.Popen([str(PY), "-m", "collectors.scheduler"], cwd=str(ROOT))
    dash = subprocess.Popen(
        [str(PY), "-m", "streamlit", "run", "analytics/dashboard.py",
         "--server.port", str(DASH_PORT)],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,    # 防止子进程等待交互输入
        stdout=subprocess.DEVNULL,   # 大屏日志较噪，不输出
        stderr=subprocess.DEVNULL,
    )

    print("⏳ 大屏启动中，6 秒后自动打开浏览器...", flush=True)
    time.sleep(6)
    webbrowser.open(DASH_URL)
    print("✅ 全部启动完成。按 Ctrl+C 停止所有服务。", flush=True)

    try:
        sched.wait()  # 调度器常驻；用户 Ctrl+C 时退出
    except KeyboardInterrupt:
        print("\n🛑 正在停止所有服务...", flush=True)
        for p in (dash, sched):
            p.terminate()
        print("已停止。下次需要时再双击 启动.bat 即可。", flush=True)


if __name__ == "__main__":
    main()
