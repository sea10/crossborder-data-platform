"""初始化数据库：建库 + 建表
用法: python -m database.init_db
"""
import sys

from database.db import get_engine
from database.models import Base

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

if __name__ == "__main__":
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("数据库初始化完成，已建表：", ", ".join(Base.metadata.tables))
