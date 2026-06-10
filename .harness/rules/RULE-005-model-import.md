# 规则 005: 数据库模型导入

**问题描述**: 新增 SQLModel 模型后忘记在 `database/models/__init__.py` 中导入，导致 Alembic 迁移无法识别新表，或运行时 ImportError。

**错误示例**:
```python
# database/models/new_model.py
class NewModel(SQLModel, table=True):
    ...

# ❌ 忘记在 __init__.py 中导入
# database/models/__init__.py
from .user import User
# from .new_model import NewModel  # 遗漏！
```

**正确示例**:
```python
# database/models/__init__.py
from .user import User
from .cycle import Cycle
from .evaluation import Evaluation
from .new_model import NewModel  # ✅ 新增模型必须在这里导入
```

**触发场景**: 
- 新增数据库模型文件
- 重命名模型文件
- 从其他文件移动模型类

**校验方式**: 
1. 新增模型后检查 `models/__init__.py` 是否有导入
2. 运行 `make migrate` 检查 Alembic 是否能识别新表
