# 规则 002: 权限校验

**问题描述**: 新增 API 接口忘记添加权限校验，导致敏感数据泄露或未授权访问。

**错误示例**:
```python
@router.get("/users/{user_id}/evaluations")
async def get_user_evaluations(user_id: int, db: Session = Depends(get_db)):
    # ❌ 没有校验当前用户是否有权限查看该用户的评估
    ...
```

**正确示例**:
```python
@router.get("/users/{user_id}/evaluations")
async def get_user_evaluations(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ✅ 先校验权限
    from pms.services.scope import ensure_can_view_user
    ensure_can_view_user(db, current_user, user_id)
    ...
```

**触发场景**: 
- 新增任何查询/操作接口
- 修改现有接口的返回数据范围
- 新增导出功能

**校验方式**: 
1. 检查所有 `@router.*` 装饰器的方法是否有权限校验
2. 检查敏感操作是否记录 audit_log
3. 检查数据范围是否按用户角色过滤
