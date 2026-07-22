# PMS 响应式改造速查表

> 各页面在桌面端与移动端的核心差异一览。

---

## 断点速记

| 断点 | 范围 | 策略 |
|------|------|------|
| `xl` | ≥ 1280px | 完整左侧边栏（240px）+ 内容区居中最大 1440px |
| `lg` | 1024 - 1279px | 侧栏可收起/展开，多列网格保持 |
| `md` | 768 - 1023px | 侧栏抽屉化，网格压缩为 2 列，底部操作栏出现 |
| `sm` | 640 - 767px | 严格单列，表格卡片化，KPI 横向滑动 |
| `xs` | < 640px | 紧凑单列，触控目标 44-48px，字号微调 |

---

## 首页（home.html）

| 桌面端 | 移动端 |
|--------|--------|
| 左侧边栏常驻 + 顶部全局栏 | 抽屉侧栏 + 汉堡菜单 |
| 3 列 KPI 迷你卡 | 2 列 KPI 卡或单列 |
| 快捷操作按钮横向排列 | 8 宫格图标网格 `.quick-actions-grid` |
| 待办任务列表横向展示 | 待办任务卡片单列，操作按钮置底 |
| 试用期进度卡片 + 周期表格 | 试用期卡片单列，周期表格转为 `.table-card-list` |

---

## 绩效看板（dashboard.html）

| 桌面端 | 移动端 |
|--------|--------|
| 6 列 KPI 指标卡 | `.kpi-grid-scroll` 横向滑动 |
| 趋势折线图 + 环形分布图并排 | 趋势图简化为 `.trend-summary`（关键数字 + sparkline） |
| 完整部门概览表格 | 分布图改为横向条形图 + 图例列表 |
| 顶部筛选器水平展开 | 部门表格转为 `.table-card-list` |
|  | 顶部筛选器改为 `.mobile-filter-drawer` |

---

## HR 管理台（hr-console.html）

| 桌面端 | 移动端 |
|--------|--------|
| 周期表格完整展示 | 周期表格转为 `.table-card-list` |
| 参与人 Tab 表格 | 参与人列表折叠在周期卡片内或进入详情页 |
| 导入/导出按钮横向排列 | 按钮宽度 100%，上下堆叠 |
| 操作列图标 grouping | 操作按钮置底，宽度 ≥ 44px |

---

## 员工自评（self-eval.html）

| 桌面端 | 移动端 |
|--------|--------|
| 左侧垂直步骤条 + 右侧表单 | 顶部紧凑步骤条 `.steps-compact`，只显示当前步骤名 |
| 绩效目标表格完整展示 | 绩效目标转为 `.goal-card-list` 卡片 |
| 表单两列/平铺 | 表单严格单列，输入框高度 44px |
| 操作按钮在页头 | 底部固定操作栏 `.form-bottom-actions`（上一步/下一步/保存） |
| 互评人多选 Tag | 互评人选择改为底部抽屉或全屏选择页 |

---

## 上级评估（leader-eval.html）

| 桌面端 | 移动端 |
|--------|--------|
| 左侧下属列表 + 右侧详情面板 | 拆分为列表页 → 详情页两级结构 |
| 下属列表完整展示 | 下属列表转为 `.table-card-list` |
| 详情面板可滚动 | 详情页使用折叠面板分区块 |
| 底部固定操作栏 | 详情页底部固定操作栏（提交/退回） |

---

## 绩效校准（calibration.html）

| 桌面端 | 移动端 |
|--------|--------|
| 双向条形图对比实际/目标分布 | 简化为 `.mobile-distribution` 数字卡片 + 横向进度条 |
| 人员矩阵表格完整展示 | 人员矩阵转为 `.table-card-list` |
| 校准状态水平展示 | 校准状态垂直堆叠或简化标签 |
| 审批按钮在页面底部 | 底部固定操作栏（提交审批/通过/驳回） |

---

## 通用响应式类速查

| 类名 | 作用 |
|------|------|
| `.table-card-list` | 移动端表格卡片化容器 |
| `.table-card` | 单个卡片 |
| `.kpi-grid-scroll` | 移动端 KPI 横向滑动 |
| `.form-bottom-actions` | 底部固定操作栏 |
| `.mobile-only` / `.desktop-only` | 控制元素显隐 |
| `.hide-on-mobile` / `.hide-on-tablet` / `.hide-on-desktop` | 按断点显隐 |
| `.steps-compact` | 移动端紧凑步骤条 |
| `.mobile-filter-drawer` | 移动端筛选抽屉 |
| `.trend-summary` | 趋势图简化版（关键数字 + 趋势箭头） |
| `.mobile-distribution` | 分布图简化版（横向条形图） |
| `.goal-card-list` | 绩效目标卡片列表 |

---

## 关键响应式变量

```css
--breakpoint-sm: 640px;
--breakpoint-md: 768px;
--breakpoint-lg: 1024px;
--breakpoint-xl: 1280px;
--touch-target-min: 44px;
--bottom-action-height: 56px;
--sidebar-drawer-width: 280px;
--form-input-height-mobile: 44px;
```

---

详细改造策略见 `RESPONSIVE-PLAN.md`，执行方案见 `KIMI-EXEC-PLAN.md`。
