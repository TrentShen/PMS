# 本地开发常用命令
.PHONY: install dev lint test migrate makemigration

install:
	pip install -e ".[dev]"

dev:
	# 本地启动开发服务器，改代码自动重载
	# --app-dir 指向 src 目录，以便 import pms.xxx 生效
	PYTHONPATH=src uvicorn pms.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src

lint:
	ruff check src

test:
	pytest -v

migrate:
	# 应用所有迁移到数据库
	alembic upgrade head

makemigration:
	# 使用方式：make makemigration MSG="add user table"
	alembic revision --autogenerate -m "$(MSG)"
