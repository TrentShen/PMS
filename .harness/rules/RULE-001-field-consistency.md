# 规则 001: 前后端字段一致性

**问题描述**: 前端使用的字段名与后端 Pydantic Schema 不一致，导致数据无法正常传递或显示异常。

**错误示例**:
```python
# 后端 schema
class CalibrateItem(BaseModel):
    user_id: int
    perf_score: float
    value_belief_grade: str
    value_team_grade: str
    value_growth_grade: str
```

```typescript
// 前端传参 ❌ 字段名不匹配
const payload = {
  user_id: 1,
  perf_score: 3.5,
  value_grade: "jia"  // ❌ 后端没有 value_grade，需要分开传三个维度
};
```

**正确示例**:
```typescript
// 前端传参 ✅ 字段名完全一致
const payload = {
  user_id: 1,
  perf_score: 3.5,
  value_belief_grade: "jia",
  value_team_grade: "yi",
  value_growth_grade: "jia"
};
```

**触发场景**: 
- 新增/修改 API 接口
- 修改数据库模型字段
- 修改前端表单提交数据

**校验方式**: 
1. Plan 阶段输出字段对照表
2. 搜索前端代码中是否存在后端没有的字段名
3. 搜索后端代码中是否存在前端没传的字段名
