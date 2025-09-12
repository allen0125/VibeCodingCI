from sqlmodel import SQLModel, create_engine, Session
from typing import Generator
import os

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./linear_webhook.db")

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,  # 设置为 True 可以看到 SQL 查询日志
)

def create_db_and_tables():
    """创建数据库和表"""
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """获取数据库会话的依赖注入函数"""
    with Session(engine) as session:
        yield session

def get_db():
    """向后兼容的数据库会话获取函数"""
    return get_session()
