# 规则 004: 时间处理（禁用 utcnow）

**问题描述**: Python 3.12 已废弃 `datetime.utcnow()`，继续使用会产生 DeprecationWarning，且返回的 datetime 对象没有时区信息，容易导致时区混乱。

**错误示例**:
```python
from datetime import datetime

# ❌ Python 3.12 已废弃，且返回 naive datetime
created_at = datetime.utcnow()
```

**正确示例**:
```python
from datetime import datetime, timezone

# ✅ 带时区信息，符合现代 Python 最佳实践
created_at = datetime.now(timezone.utc)

# 数据库模型中的字段
from sqlalchemy import Column, DateTime
created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
```

**触发场景**: 
- 任何需要获取当前时间的代码
- 数据库模型定义中的时间字段
- 定时任务（APScheduler）中的时间计算

**校验方式**: 
1. 全局搜索 `utcnow()`，全部替换
2. 检查数据库模型中 `DateTime` 字段是否带 `timezone=True`
