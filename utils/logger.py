"""统一日志配置（utils/logger.py）

设计说明（参考工程实践）:
- 双通道输出: 控制台（开发实时看）+ 文件（data/logs/<模块>.log，事后排错）
- 轮转策略: 单文件 2MB × 5 份，防止长期运行占满磁盘
- 按模块命名: 每个模块 get_logger("collector") 等，日志里直接定位错误来源
- 幂等: 重复调用不会重复添加 handler

用法:
    from utils.logger import get_logger
    logger = get_logger("collector")
    logger.info("正常流程") / logger.warning("异常迹象") / logger.exception("错误+堆栈")
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "data" / "logs"

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_configured: set = set()


def _ensure_stdout_utf8():
    """Windows 控制台默认 GBK，打印中文前切 UTF-8"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """获取 控制台+文件 双通道 logger（幂等，重复调用不叠加 handler）"""
    _ensure_stdout_utf8()
    logger = logging.getLogger(name)
    if name in _configured:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(_FORMAT)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=2 * 1024 * 1024,  # 2MB
        backupCount=5,             # 保留 5 份历史
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.propagate = False  # 不向上传递，避免重复输出
    _configured.add(name)
    return logger
