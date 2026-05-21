from collections.abc import Generator

import redis
from sqlmodel import Session, create_engine

from pms.configs import settings

engine = create_engine(
    settings.mysql_dsn,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=20,
    max_overflow=30,
)

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
