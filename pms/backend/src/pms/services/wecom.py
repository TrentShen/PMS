from __future__ import annotations

# 企业微信 API 封装
# access_token 用 Redis 缓存，提前 5 分钟刷新，所有 API 调用统一走此模块
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import httpx
from loguru import logger

from pms.configs import settings
from pms.database.session import redis_client

WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
TOKEN_KEY = "pms:wecom:access_token"
CONTACT_TOKEN_KEY = "pms:wecom:contact_access_token"
TOKEN_TTL = 7200  # 企微 token 2 小时有效
REFRESH_AHEAD = 300  # 提前 5 分钟刷新

# 人事助手（花名册）字段 ID，与 HR-bot 项目保持一致
HR_FIELD_IDS = {
    "birthday": 11005,
    "join_date": 12018,
    "confirm_date": 12023,
    "probation": 12021,
    "employee_type": 12003,
    "employee_status": 12004,
    "employee_no": 12024,
}

# 企微员工状态 → PMS 内部状态
HR_EMPLOYEE_STATUS_MAP = {
    1: "regular",     # 正式
    2: "probation",   # 试用
    3: "resigning",   # 待离职
    4: "resigned",    # 已离职
    5: "pending",     # 待入职
    6: "abandoned",   # 放弃入职
}

# 企微员工类型选项 ID → PMS 内部类型
HR_EMPLOYEE_TYPE_MAP = {
    1: "full_time",   # 全职
    2: "intern",      # 实习
    4: "other",       # 其他
}

# 企微试用期选项 ID → 月数（根据 get_fields 接口的 option_list）
HR_PROBATION_MAP = {
    1: 0,   # 无
    2: 1,   # 1个月
    3: 2,   # 2个月
    4: 3,   # 3个月
    5: 4,   # 4个月
    6: 5,   # 5个月
    7: 6,   # 6个月
}


def _ensure_access_token(secret: str | None = None, key: str = TOKEN_KEY) -> str:
    """获取有效 access_token：命中缓存直接返回，否则调企微接口获取

    Args:
        secret: 用于获取 token 的 secret；默认使用应用 secret。
        key: Redis 缓存 key；不同 secret 应使用不同 key 避免冲突。
    """
    cached = redis_client.get(key)
    if cached:
        return cached

    used_secret = secret or settings.wecom_secret
    url = f"{WECOM_API_BASE}/gettoken"
    resp = httpx.get(url, params={"corpid": settings.wecom_corpid, "corpsecret": used_secret}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"企微 access_token 获取失败: {data}")

    token = data["access_token"]
    expires_in = data.get("expires_in", TOKEN_TTL)
    redis_ttl = max(expires_in - REFRESH_AHEAD, 60)
    redis_client.setex(key, redis_ttl, token)
    logger.info("企微 access_token 已刷新, key={}, ttl={}s", key, redis_ttl)
    return token


def _ensure_contact_token() -> str:
    """获取通讯录同步专用 access_token"""
    if not settings.wecom_contact_secret:
        # 未配置通讯录 secret 时回退到应用 token（权限可能受限）
        return _ensure_access_token()
    return _ensure_access_token(
        secret=settings.wecom_contact_secret,
        key=CONTACT_TOKEN_KEY,
    )


def _get(url: str, params: dict | None = None, *, use_contact_token: bool = False) -> dict:
    token = _ensure_contact_token() if use_contact_token else _ensure_access_token()
    p = params or {}
    p["access_token"] = token
    r = httpx.get(url, params=p, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("errcode") not in (0, None):
        logger.error("企微 API 错误: {} {}", url, data)
    return data


def _post(url: str, json_body: dict, params: dict | None = None, *, use_contact_token: bool = False) -> dict:
    token = _ensure_contact_token() if use_contact_token else _ensure_access_token()
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
    """拉取部门列表，不传 parent_id 则拉根部门（使用应用 token）"""
    params = {}
    if parent_id is not None:
        params["id"] = parent_id
    data = _get(f"{WECOM_API_BASE}/department/list", params=params)
    return data.get("department", [])


def list_users_by_dept(dept_id: int, fetch_child: bool = True) -> list[dict]:
    """拉取部门下的用户（含子部门），返回简化字段（使用应用 token）"""
    data = _get(
        f"{WECOM_API_BASE}/user/list",
        params={"department_id": dept_id, "fetch_child": 1 if fetch_child else 0},
    )
    return data.get("userlist", [])


def list_users_detail_by_dept(dept_id: int, fetch_child: bool = True) -> list[dict]:
    """拉取部门下的用户详情（含 direct_leader/position 等完整字段，使用应用 token）"""
    data = _get(
        f"{WECOM_API_BASE}/user/list",
        params={
            "department_id": dept_id,
            "fetch_child": 1 if fetch_child else 0,
        },
    )
    return data.get("userlist", [])


def get_user_detail(userid: str) -> dict:
    """获取单个用户详情（含部门、职位、直属上级等）"""
    return _get(f"{WECOM_API_BASE}/user/get", params={"userid": userid})


# ---------- 人事助手（花名册） ----------

def get_hr_staff_info(userid: str) -> dict:
    """通过人事助手获取员工花名册信息

    调用 /cgi-bin/hr/get_staff_info，使用自建应用 secret 的 access_token。
    需要应用拥有「人事助手」接口权限，且该员工在应用可见范围内。
    """
    payload = {
        "userid": userid,
        "fieldids": [{"fieldid": fid} for fid in HR_FIELD_IDS.values()],
    }
    return _post(f"{WECOM_API_BASE}/hr/get_staff_info", json_body=payload)


def _ts_to_date(ts: int | None) -> date | None:
    """把 Unix 时间戳（秒）转成 date，无效时返回 None"""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
    except (ValueError, OSError, TypeError, OverflowError):
        return None


def parse_hr_staff_info(data: dict) -> dict:
    """解析人事助手返回的花名册字段为结构化数据

    企微接口实际返回格式为 {"field_info": [{fieldid, result, value_type, value_xxx}, ...]}，
    其中 value_type：1=string, 2=uint64(时间戳), 3=uint32(选项ID), 4=int64(时间戳)。
    """
    field_info = data.get("field_info", [])
    if not field_info and "fieldInfo" in data:
        field_info = data["fieldInfo"]

    result: dict[str, date | int | str | None] = {
        "hired_at": None,
        "confirm_date": None,
        "probation": None,
        "employee_status": None,
        "employee_type": None,
        "employee_no": None,
    }

    for field in field_info:
        if field.get("result") != 1:
            continue

        fid = field.get("fieldid")
        vtype = field.get("value_type", 0)
        raw: int | str | None = None

        if vtype == 1:
            raw = field.get("value_string")
        elif vtype == 2:
            raw = field.get("value_uint64")
        elif vtype == 3:
            raw = field.get("value_uint32")
        elif vtype == 4:
            raw = field.get("value_int64")

        if raw is None:
            continue

        if fid == HR_FIELD_IDS["join_date"]:
            result["hired_at"] = _ts_to_date(raw)
        elif fid == HR_FIELD_IDS["confirm_date"]:
            result["confirm_date"] = _ts_to_date(raw)
        elif fid == HR_FIELD_IDS["birthday"]:
            result["hired_at"] = result["hired_at"] or _ts_to_date(raw)
        elif fid == HR_FIELD_IDS["probation"]:
            result["probation"] = HR_PROBATION_MAP.get(int(raw))
        elif fid == HR_FIELD_IDS["employee_status"]:
            result["employee_status"] = HR_EMPLOYEE_STATUS_MAP.get(int(raw))
        elif fid == HR_FIELD_IDS["employee_type"]:
            result["employee_type"] = HR_EMPLOYEE_TYPE_MAP.get(int(raw))
        elif fid == HR_FIELD_IDS["employee_no"]:
            result["employee_no"] = str(raw) if raw else None

    return result


def batch_get_hr_staff_info(userids: list[str], max_workers: int = 5) -> dict[str, dict]:
    """并发批量获取员工花名册信息

    注意：此函数用于后台同步任务，不要在请求链路中同步调用，避免阻塞。
    """
    results: dict[str, dict] = {}
    failed: list[str] = []

    def _fetch(uid: str) -> tuple[str, dict | None]:
        try:
            data = get_hr_staff_info(uid)
            if data.get("errcode") not in (0, None):
                logger.warning("人事助手查询失败 [{}]: {}", uid, data)
                return uid, None
            return uid, parse_hr_staff_info(data)
        except Exception as e:
            logger.warning("人事助手查询异常 [{}]: {}", uid, e)
            return uid, None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch, uid): uid for uid in userids}
        for future in as_completed(futures):
            uid, info = future.result()
            if info:
                results[uid] = info
            else:
                failed.append(uid)

    if failed:
        logger.warning("人事助手批量查询完成: 成功 {}, 失败 {}", len(results), len(failed))

    return results


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
