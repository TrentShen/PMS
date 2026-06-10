from __future__ import annotations

# 企业微信 API 封装
# access_token 用 Redis 缓存，提前 5 分钟刷新，所有 API 调用统一走此模块
import time
from typing import Any

import httpx
from loguru import logger

from pms.configs import settings
from pms.database.session import redis_client

WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
TOKEN_KEY = "pms:wecom:access_token"
TOKEN_TTL = 7200  # 企微 token 2 小时有效
REFRESH_AHEAD = 300  # 提前 5 分钟刷新


def _ensure_access_token() -> str:
    """获取有效 access_token：命中缓存直接返回，否则调企微接口获取"""
    cached = redis_client.get(TOKEN_KEY)
    if cached:
        return cached

    url = f"{WECOM_API_BASE}/gettoken"
    resp = httpx.get(url, params={"corpid": settings.wecom_corpid, "corpsecret": settings.wecom_secret}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"企微 access_token 获取失败: {data}")

    token = data["access_token"]
    expires_in = data.get("expires_in", TOKEN_TTL)
    redis_ttl = max(expires_in - REFRESH_AHEAD, 60)
    redis_client.setex(TOKEN_KEY, redis_ttl, token)
    logger.info("企微 access_token 已刷新, ttl={}s", redis_ttl)
    return token


def _get(url: str, params: dict | None = None) -> dict:
    token = _ensure_access_token()
    p = params or {}
    p["access_token"] = token
    r = httpx.get(url, params=p, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("errcode") not in (0, None):
        logger.error("企微 API 错误: {} {}", url, data)
    return data


def _post(url: str, json_body: dict, params: dict | None = None) -> dict:
    token = _ensure_access_token()
    p = params or {}
    p["access_token"] = token
    r = httpx.post(url, params=p, json=json_body, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("errcode") not in (0, None):
        logger.error("企微 API 错误: {} {} {}", url, json_body, data)
    return data


# ---------- OAuth ----------

def get_userinfo(code: str) -> str:
    """用 OAuth code 换取企微 userid（静默授权 snsapi_base）"""
    data = _get(f"{WECOM_API_BASE}/auth/getuserinfo", params={"code": code})
    userid = data.get("userid") or data.get("UserId")
    if not userid:
        raise RuntimeError(f"code 换 userid 失败: {data}")
    return userid


# ---------- 通讯录同步 ----------

def list_departments(parent_id: int | None = None) -> list[dict]:
    """拉取部门列表，不传 parent_id 则拉根部门"""
    params = {}
    if parent_id is not None:
        params["id"] = parent_id
    data = _get(f"{WECOM_API_BASE}/department/list", params=params)
    return data.get("department", [])


def list_users_by_dept(dept_id: int, fetch_child: bool = True) -> list[dict]:
    """拉取部门下的用户（含子部门），返回简化字段"""
    data = _get(
        f"{WECOM_API_BASE}/user/list",
        params={"department_id": dept_id, "fetch_child": 1 if fetch_child else 0},
    )
    return data.get("userlist", [])


def list_users_detail_by_dept(dept_id: int, fetch_child: bool = True) -> list[dict]:
    """拉取部门下的用户详情（含 direct_leader/position 等完整字段）"""
    data = _get(
        f"{WECOM_API_BASE}/user/list",
        params={
            "department_id": dept_id,
            "fetch_child": 1 if fetch_child else 0,
        },
    )
    return data.get("userlist", [])


# ---------- 应用消息 ----------

def send_text(user_ids: list[str], content: str, agentid: int | None = None) -> dict:
    """发送文本消息"""
    return _post(
        f"{WECOM_API_BASE}/message/send",
        json_body={
            "touser": "|".join(user_ids),
            "msgtype": "text",
            "agentid": agentid or int(settings.wecom_agentid),
            "text": {"content": content},
        },
    )


def send_textcard(
    user_ids: list[str],
    title: str,
    description: str,
    url: str,
    btntxt: str = "查看详情",
    agentid: int | None = None,
) -> dict:
    """发送文本卡片消息（企微工作台推荐格式）
    注意：title < 128 字节，description < 512 字节
    """
    # 截断处理，避免企微拒绝
    title = title.encode("utf-8")[:124].decode("utf-8", errors="ignore")
    description = description.encode("utf-8")[:508].decode("utf-8", errors="ignore")
    return _post(
        f"{WECOM_API_BASE}/message/send",
        json_body={
            "touser": "|".join(user_ids),
            "msgtype": "textcard",
            "agentid": agentid or int(settings.wecom_agentid),
            "textcard": {
                "title": title,
                "description": description,
                "url": url,
                "btntxt": btntxt,
            },
        },
    )


def send_markdown(user_ids: list[str], content: str, agentid: int | None = None) -> dict:
    """发送 Markdown 消息"""
    return _post(
        f"{WECOM_API_BASE}/message/send",
        json_body={
            "touser": "|".join(user_ids),
            "msgtype": "markdown",
            "agentid": agentid or int(settings.wecom_agentid),
            "markdown": {"content": content},
        },
    )
