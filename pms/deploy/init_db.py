#!/usr/bin/env python3
"""PMS 生产数据库初始化脚本：直接 create_all + 标记 alembic 版本"""
import os

from dotenv import load_dotenv

load_dotenv("deploy/.env.prod")

from sqlmodel import SQLModel, create_engine
from pms.database.models import *  # noqa: F401,F403
from sqlalchemy import text

mysql_dsn = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}"
    f"/{os.getenv('MYSQL_DATABASE')}?charset=utf8mb4"
)

engine = create_engine(mysql_dsn)
print("Creating all tables...")
SQLModel.metadata.create_all(engine)
print("Tables created.")

with engine.connect() as conn:
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY)"
    ))
    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(text(
        "INSERT INTO alembic_version (version_num) VALUES ('00a82ba91945')"
    ))
    conn.commit()

print("Alembic version set to 00a82ba91945.")
print("Done.")
