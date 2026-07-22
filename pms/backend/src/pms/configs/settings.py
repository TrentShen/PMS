from __future__ import annotations

# 应用配置：通过环境变量加载（来自 .env 或系统环境）
# 所有配置统一从 settings 单例读取，禁止在业务代码里直接 os.getenv
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 应用基础
    app_name: str = "pms"
    app_env: str = Field(default="local", description="local / dev / prod")
    app_port: int = 8000
    app_secret: str = Field(default="change-me", description="JWT 签名密钥，生产必须改")

    # 数据库（MySQL）
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "pms"
    mysql_password: str = "pms_password"
    mysql_database: str = "pms"

    # Redis
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    # 企业微信
    wecom_corpid: str = Field(default="", description="企业 ID")
    wecom_agentid: str = Field(default="", description="自建应用 agentid")
    wecom_secret: str = Field(default="", description="自建应用 secret")
    wecom_contact_secret: str = Field(default="", description="通讯录同步 secret")
    wecom_redirect_uri: str = Field(default="http://localhost:5173/auth/callback")

    # SMTP 邮件（企微消息降级通道）
    smtp_host: str = Field(default="", description="SMTP 服务器地址")
    smtp_port: int = Field(default=465, description="SMTP 端口")
    smtp_user: str = Field(default="", description="SMTP 用户名")
    smtp_password: str = Field(default="", description="SMTP 密码")
    smtp_from_email: str = Field(default="", description="发件人邮箱")
    smtp_use_tls: bool = Field(default=True, description="是否使用 TLS")

    # 前端地址（CORS）
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def mysql_dsn(self) -> str:
        # SQLAlchemy 连接串：pymysql 驱动
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache(maxsize=1)
def _load() -> Settings:
    return Settings()


# 对外暴露的配置单例
settings = _load()
