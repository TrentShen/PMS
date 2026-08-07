# 后端生产镜像（部署到公司服务器用）
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app

# 先拷依赖文件，利用 Docker 层缓存
# 注:服务器在国内机房,PyPI 直连不稳定,走阿里云镜像(2026-08-05 部署曾因此卡 17 分钟)
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# 再拷源码
COPY src /app/src
COPY alembic /app/alembic
COPY alembic.ini pyproject.toml /app/

ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "pms.main:app", "--host", "0.0.0.0", "--port", "8000"]
