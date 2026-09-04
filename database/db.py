"""数据库连接与会话管理

- 配置从 config/settings.yaml 读取
- 首次连接自动建库（CREATE DATABASE IF NOT EXISTS）
- 密码含特殊字符已做 URL 编码，直接填明文即可
"""
from pathlib import Path
from urllib.parse import quote_plus

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.models import Base

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "settings.yaml"

_engine = None
_Session = None


def load_config() -> dict:
    """读取全局配置（settings.yaml）"""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_engine():
    global _Session
    cfg = load_config()["database"]
    base = (
        f"mysql+pymysql://{cfg['user']}:{quote_plus(cfg['password'])}"
        f"@{cfg['host']}:{cfg['port']}"
    )
    # 先连服务器，确保目标库存在
    server = create_engine(base, pool_pre_ping=True)
    with server.connect() as conn:
        conn.execute(
            text(f"CREATE DATABASE IF NOT EXISTS `{cfg['db']}` DEFAULT CHARACTER SET utf8mb4")
        )
    server.dispose()

    engine = create_engine(f"{base}/{cfg['db']}?charset=utf8mb4", pool_pre_ping=True)
    _Session = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session():
    """获取一个数据库会话（用后记得 close）"""
    get_engine()
    return _Session()
