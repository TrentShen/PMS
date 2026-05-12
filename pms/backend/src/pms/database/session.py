# 数据库会话管理
# engine 为进程级单例；每个请求通过 FastAPI Depends(get_session) 拿一个短生命周期 Session
from collections.abc import Generator

from sqlmodel import Session, create_engine

from pms.configs import settings

# pool_pre_ping 避免连接被 MySQL 回收后拿到坏连接
engine = create_engine(
    settings.mysql_dsn,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)


def get_session() -> Generator[Session, None, None]:
    # FastAPI 依赖注入：请求结束自动关闭 session
    with Session(engine) as session:
        yield session
