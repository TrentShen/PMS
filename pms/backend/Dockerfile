# 后端生产镜像（部署到公司服务器用）
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先拷依赖文件，利用 Docker 层缓存
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# 再拷源码
COPY src /app/src
COPY alembic /app/alembic
COPY alembic.ini pyproject.toml /app/

ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "pms.main:app", "--host", "0.0.0.0", "--port", "8000"]
