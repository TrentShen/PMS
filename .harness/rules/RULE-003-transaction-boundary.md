# 规则 003: 事务边界

**问题描述**: 数据库操作的事务边界不清晰，导致部分操作提交、部分操作回滚，数据不一致。

**错误示例**:
```python
async def write_audit_log(session: Session, ...):
    session.add(log_entry)
    # ❌ 在函数内部直接 commit，如果调用方后续报错回滚，日志却被提交了
    session.commit()
```

**正确示例**:
```python
async def write_audit_log(session: Session, ...):
    session.add(log_entry)
    # ✅ 只添加记录，不 commit，由调用方控制事务边界

# 在路由层统一管理事务
async def some_api_endpoint(session: Session = Depends(get_session)):
    try:
        do_something(session)
        write_audit_log(session, ...)
        session.commit()  # ✅ 统一提交
    except Exception:
        session.rollback()  # ✅ 统一回滚
        raise
```

**触发场景**: 
- 新增涉及多表的操作
- 在 service/utils 中写数据库操作
- 在工具函数中调用 `session.commit()`

**校验方式**: 
1. 检查 service/utils 中是否有直接的 `session.commit()`
2. 检查涉及多表的操作是否在一个事务中
3. 检查 APScheduler job 中的事务处理
