# PMS 绩效管理系统 — 开发执行方案（给 Kimi）

> 本文档面向开发侧，用于将 `/Users/trentshen/Documents/Kimi code - 工作区/hr/design-prototype/` 中的设计原型与令牌落地到现有 React 项目。  
> 现有前端路径：`/Users/trentshen/Documents/Kimi code - 工作区/hr/pms/web/src/`  
> 原则：**不修改现有项目业务逻辑**，优先复用 Ant Design 5 组件，仅通过自定义样式覆盖与设计令牌对齐。  
> 版本：v2.2（Phase 5 最终交付，响应式改造已纳入）

---

## 1. 范围与目标

### 1.1 目标
- 将设计原型中的视觉风格、信息层级、交互模式落地到现有 PMS 前端项目。
- 统一全站色彩、字体、间距、圆角、阴影，建立可维护的设计令牌 CSS 变量体系。
- 保证 6 个核心页面（首页、HR 绩效看板、HR 管理台、员工自评、上级评估、绩效校准）风格一致。
- 解决质量评审中剩余的 P2 问题：焦点状态、图标尺寸、可访问性、死代码、校准矩阵颜色语义、长表单操作入口。

### 1.2 原则
- 尽量保留现有 Ant Design 组件，避免重复造轮子。
- 使用 CSS 变量覆盖 Ant Design 的 `token` 与全局样式，减少硬编码。
- 新增组件以“可复用、可配置”方式实现，放在项目组件目录。
- 不破坏现有路由、状态管理、接口调用逻辑。

---

## 2. 全局改造

### 2.1 设计令牌落地

| 项 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 目标 | 现有项目颜色/字号/间距分散，不统一 | `src/styles/global.css` 或 `src/styles/variables.css` | 将下文章节 8 中的 CSS 变量复制到全局样式；在 `:root` 中定义完整令牌 | 全站使用 CSS 变量，搜索不到硬编码的 `#3370FF`、`#F5F6F7` 等主色/背景色（SVG 除外） |
| 问题 | 无集中式变量 | 全局入口 `src/App.tsx` 或 `src/global.less` | 引入 variables 文件；配置 Ant Design 5 `theme.token` 与 CSS 变量对齐 | 设计令牌一处修改，全站同步更新 |

### 2.2 页面外壳与导航（Linear 结构）

| 项 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 目标 | 导航与原型不一致 | `src/layouts/AppShell.tsx` / `MainLayout.tsx` | 使用 Ant Design `Layout`：左侧 `Sider`（240px）+ 顶部 `Header`（56px）+ `Content`；Logo 区 + 导航分组 + 全局栏 | 所有页面共用统一外壳，侧边栏宽度/高度使用 CSS 变量 |
| 问题 | 导航项状态不统一 | `Sidebar` 组件 | 当前页 `nav-item` 高亮背景 `--color-primary-subtle`，文字 `--color-primary`，左侧加 3px 蓝色指示条 | 切换路由时高亮态正确，hover 态为 `--color-surface-raised` |
| 问题 | 顶部栏缺少全局搜索/角色切换/头像 | `Topbar` 组件 | 左侧页面标题 + 搜索框 + 通知图标按钮 + 角色切换下拉 + 头像 | 所有页面顶部栏一致，角色切换显示当前角色 |

### 2.3 响应式与移动端（核心改造）

| 目标 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 统一断点 | 现有项目只有基础响应式，断点不清晰 | 全局 CSS / AppShell | 在全局样式中落地 `--breakpoint-sm: 640px`、`--breakpoint-md: 768px`、`--breakpoint-lg: 1024px`、`--breakpoint-xl: 1280px`；媒体查询使用 `max-width: 1023px`、`max-width: 767px`、`max-width: 639px` 与 `min-width: 1280px` | 所有页面使用同一组断点，无杂散 `px` 硬编码 |
| 侧栏抽屉化 | 移动端侧栏无法打开 | `AppShell` / `Sidebar` | 在 `<=1024px` 下侧边栏 `transform: translateX(-100%)`，汉堡菜单按钮显示，点击切换 `.open`；`768px` 以下使用 280px 抽屉，`768px` 以上可使用 72px 图标窄栏 | 平板/手机可正常打开/关闭侧边栏抽屉 |
| 表格卡片化 | 复杂表格移动端展示差 | 各页面表格 | 为每个表格同时提供 `.data-table`（桌面）和 `.table-card-list`（<768px 显示）；卡片使用 `data-label` 生成字段标签 | 移动端表格无横向滚动，关键字段可见，操作按钮可点 |
| KPI 横向滑动 | Dashboard 多列布局在移动端挤压 | `dashboard` 页面 | 使用 `.kpi-grid-scroll`：`display: flex; overflow-x: auto; scroll-snap-type: x mandatory;`；卡片 `flex: 0 0 auto; min-width: 160px` | 小屏下 KPI 可横向滑动，无重叠 |
| 底部固定操作栏 | 长表单提交按钮在移动端难触达 | `SelfEval`、`LeaderEval`、`Calibration` | 使用 `.form-bottom-actions`：`position: fixed; bottom: 0; left: 0; right: 0; height: 56px; z-index: 110; padding-bottom: env(safe-area-inset-bottom, 0)` | 长表单页面底部始终可见保存/提交/退回按钮，不遮挡内容 |
| 表单单列化 | 移动端表单两列显示拥挤 | 所有表单 | 在 `max-width: 767px` 下，`.form-row` 改为 `flex-direction: column; gap: 16px`；输入框高度提升至 44px | 手机下表单所有字段单列显示，输入框高度 ≥ 44px |
| 图表简化 | 复杂图表在移动端不可读 | `Dashboard`、`Calibration` | 桌面使用完整 SVG/ECharts；手机改用 `.trend-summary`（关键数字 + 趋势箭头）+ `.mobile-distribution`（横向条形图）+ `.sparkline`（60-80px 迷你图） | 移动端图表可在一屏内理解，无密集数据点 |
| 长表单分步 | 自评页在移动端过长 | `SelfEval` | 桌面使用左侧步骤条 + 右侧表单；移动端使用 `.steps-compact` 只显示当前步骤名，每步一个 `.form-section` | 手机下自评每屏只显示一个步骤内容 |
| 列表-详情分屏 | 上级评估桌面左右分屏在手机上不可用 | `LeaderEval` | 桌面：左侧下属列表 + 右侧详情；手机：拆分为 `SubordinateList` 和 `SubordinateDetail` 两个视图，通过路由或状态切换 | 手机下先选下属再进入详情，详情页底部固定操作栏 |
| Modal 抽屉化 | 居中 Modal 在手机上遮挡内容 | 全局 Modal | 桌面 Modal 居中；手机使用 `Drawer` 从底部滑出，高度 `90vh`，圆角顶部 12px | 手机下弹窗不遮挡顶部标题，底部按钮可触 |
| 触控目标放大 | 按钮/图标在手机上太小 | 全局 | 所有可点击元素在移动端最小 44px×44px，推荐 48px；`.icon-btn` 在移动端 padding 增加至 12px | 按钮、图标、菜单项在 375px 下可轻松点击 |
| 安全区适配 | 底部操作栏被 iPhone 底部横条遮挡 | 全局 | `.form-bottom-actions` 和 `.page-content` 使用 `padding-bottom: env(safe-area-inset-bottom, 0)` 或 `padding-bottom: constant(safe-area-inset-bottom)` | iPhone 底部横条不遮挡操作按钮 |

### 2.4 焦点状态与可访问性

| 项 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 目标 | 按钮/链接焦点态缺失 | 全局样式 | 为 `button`、`a`、`.form-control`、`.icon-btn` 添加 `:focus-visible`：`box-shadow: 0 0 0 2px rgba(51,112,255,0.15); outline: none;` | 使用 Tab 键切换时，焦点可见 |
| 问题 | 图标按钮缺少说明 | 所有纯图标按钮 | 添加 `aria-label`（如“打开菜单”“通知”“编辑”） | 无文本图标按钮均有 aria-label |
| 问题 | 步骤条、评分选项键盘不可达 | `Steps`、`RatingOptions` | 步骤条使用 `role="list"` / `aria-current="step"`；评分选项使用 `role="radio"`、`aria-checked`、`tabIndex` | 可通过键盘操作并屏幕阅读器朗读 |

### 2.5 图标规范

| 项 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 目标 | 图标尺寸不统一 | 全局 | 导航图标 20px；操作图标 16px；按钮内图标 14px；趋势图标 14px | 全站图标尺寸符合规范，不出现 18px/22px 混用 |
| 问题 | 图标来源不一致 | 图标组件 | 统一使用 `lucide-react` 或 `@ant-design/icons`，按设计语义选择 | 同义图标使用同一组件，可一键换色 |

---

## 3. 页面改造

### 3.1 首页 / 个人工作台（home.html → `src/pages/Home/index.tsx`）

| 目标 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 统一入口 | “继续填写自评”按钮未链接 | 首页 Hero 区 | 将按钮改为 `<Link to="/self-eval">` 或 `onClick` 跳转 | 点击后进入自评页 |
| 待办图标 | 任务图标尺寸不一致 | 待办列表 | 所有 `.task-icon` 内图标统一 20px，容器 40px×40px | 视觉对齐 |
| 焦点态 | 任务项、按钮无焦点 | 首页组件 | 添加 `:focus-visible` 与 `aria-label` | Tab 可聚焦 |
| 卡片 hover | KPI 迷你卡片缺少 hover | KPI 卡片 | 增加悬停阴影 `0 4px 12px rgba(31,35,41,0.08)` |  hover 时有明显反馈 |
| 数据一致 | 表格状态 Tag 语义 | 周期表格 | 使用 `Tag` 组件：`进行中` primary、`已归档` success、`自评中` warning | 与设计稿一致 |
| 移动端快捷入口 | 桌面快捷操作按钮在手机上横向拥挤 | 首页 Hero 区 | 在移动端使用 8 宫格图标网格 `.quick-actions-grid`，图标 24px，文字 12px | 手机下快捷入口 2 行 4 列，可点击 |
| 移动端待办 | 桌面待办列表在手机上信息密集 | 待办任务 | 在移动端使用 `.task-item` 单列卡片，标题+状态+操作垂直排列 | 手机下待办任务可滑动浏览，操作按钮 44px |
| 移动端周期卡片 | 桌面周期表格在手机上不可读 | 周期列表 | 在移动端使用 `.table-card-list`，每张卡片显示：周期名、状态、我的状态、最终结果、操作按钮 | 手机下周期列表无横向滚动，关键信息可见 |

### 3.2 HR 绩效看板（dashboard.html → `src/pages/Dashboard/index.tsx`）

| 目标 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 图表标签 | 折线图 X 轴标签可能溢出 | 趋势图 SVG | 使用 `preserveAspectRatio="none"` 与 `viewBox` 控制；标签字号 11px，确保在容器内 | 任意宽度下标签不截断、不重叠 |
| 数据一致 | KPI 与表格数据需对应 | 页面数据 | 参与人数 128、自评完成率 72%、部门进度与表格一致 | 数字与表格/图表数据不矛盾 |
| 移动端图表 | 图表在移动端过密 | 响应式 | 小屏下隐藏图例，减少 X 轴标签，或使用垂直堆叠 | 小屏可读 |
| 图表配色 | 所有图表使用设计色板 | 图表组件 | 只使用 `--color-chart-1` 到 `--color-chart-6`，避免自定义高饱和色 | 图表色彩与色板一致 |
| 部门进度 | 双进度条对比 | 部门进度组件 | 自评 `--color-primary`、互评 `--color-chart-2` | 两进度条颜色区分明确 |
| 移动端 KPI | 4 列 KPI 在手机上挤压 | KPI 网格 | 在移动端使用 `.kpi-grid-scroll` 横向滑动，卡片宽度 160px，scroll-snap 对齐 | 手机下 KPI 可横向滑动，一屏可见 1.5 张卡片 |
| 移动端趋势图 | 折线图在手机上无法阅读 | 趋势图 | 在移动端替换为 `.trend-summary`：关键数字 + 趋势箭头 + 迷你 sparkline（80px 高） | 手机下趋势一目了然，无需放大 |
| 移动端分布图 | 环形图在手机上标签拥挤 | 分布图 | 在移动端改为横向条形图 + 图例列表，条形图使用图表色板 | 手机下各等级人数对比清晰 |
| 移动端部门表格 | 部门概览表格在手机上列多 | 部门表格 | 在移动端使用 `.table-card-list`，卡片显示部门名、自评完成率、互评完成率、状态 | 手机下部门进度卡片化，无横向滚动 |
| 移动端筛选 | 顶部筛选器在手机上占满一行 | 筛选器 | 在移动端使用 `.mobile-filter-drawer`，顶部只显示“筛选”按钮，点击展开抽屉 | 手机下筛选入口不占用宝贵空间 |

### 3.3 HR 管理台 / 周期管理（hr-console.html → `src/pages/HRConsole/index.tsx`）

| 目标 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 清理死代码 | `.status-tag` 未使用 | 样式文件 | 删除 `.status-tag` 相关 CSS；如业务需要则补全组件 | 无未引用样式 |
| 图标尺寸 | 操作列图标混用 | 周期表格、参与人表格 | 操作图标统一 16px，按钮尺寸 28px×28px，圆角 6px | 操作列整齐 |
| 表格分页 | 两个表格共用分页组件但数据不同 | 周期表与参与人表 | 拆分分页状态，避免互相影响 | 切换页码互不影响 |
| 导入区 | 批量导入区域静态 | 导入导出区 | 使用 `Upload` 组件，支持拖拽；提供下载模板链接 | 可触发上传与下载 |
| 选中态 | 选中行背景过浅 | 表格 | 选中行背景 `--color-primary-subtle`，文字保持可读 | 选中态明显 |
| 移动端周期卡片 | 周期表格在手机上列多 | 周期表格 | 在移动端使用 `.table-card-list`，每张卡片显示：周期名、状态、时间、参与人数、操作按钮（发布/编辑/归档） | 手机下周期列表卡片化，关键操作可触 |
| 移动端参与人 | 参与人表格在手机上不可读 | 参与人表格 | 在移动端参与人列表折叠在周期卡片内，或点击后进入详情页 | 手机下可查看/管理参与人 |
| 移动端导入导出 | 桌面导入导出按钮在手机上换行 | 导入导出区 | 在移动端按钮宽度 100%，上下堆叠 | 手机下导入导出按钮不重叠，点击区域 ≥ 44px |

### 3.4 员工自评页（self-eval.html → `src/pages/SelfEval/index.tsx`）

| 目标 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 长表单操作 | 页面长，提交入口仅在页头 | 自评表单 | 增加底部固定操作栏或步骤条可点击跳转；保留顶部“暂存/提交” | 用户随时可提交/暂存 |
| 评分选项 | 无焦点、无键盘支持 | 评分组件 | 将 `div` 改为 `button` 或加 `role="radio"`、`tabIndex`、`aria-checked`；选中态 `.selected` | 可用键盘选择分数 |
| 互评人 | Tag 删除无确认 | 互评人选择 | 点击删除时二次确认或撤销提示 | 避免误删 |
| 步骤条 | 仅展示，不可交互 | 步骤条 | 当前步骤 `aria-current="step"`，可点击回退到已完步骤 | 屏幕阅读器可识别 |
| 文本域 | 默认高度与提示 | 表单 | `textarea` 最小高度 96px，字数提示 | 符合设计规范 |
| 桌面分栏 | 长表单在桌面端纵向过长 | 自评页 | 桌面使用左侧步骤条 `.eval-steps-sidebar` + 右侧表单内容，左右分栏 | 桌面端步骤清晰，内容区可滚动 |
| 移动端分步 | 自评页在手机上过长 | 自评表单 | 移动端使用 `.steps-compact` 只显示当前步骤名，每步一个 `.form-section`，底部固定操作栏（上一步/下一步/保存） | 手机下每屏只显示一个步骤内容，底部按钮可触 |
| 移动端目标卡片 | 绩效目标表格在手机上列多 | 绩效目标表格 | 在移动端使用 `.goal-card-list`，每张卡片显示目标、描述、权重、状态 | 手机下目标列表卡片化 |
| 移动端输入框 | 输入框在手机上太小 | 表单 | 在移动端输入框高度 44px，字号 16px（防止 iOS 缩放） | 手机下输入框可轻松点击和输入 |

### 3.5 上级评估页（leader-eval.html → `src/pages/LeaderEval/index.tsx`）

| 目标 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 下属列表 | 空态缺失 | 左侧列表 | 无下属时显示 Empty 状态：图标 + 标题 + 说明 | 空态友好 |
| 详情面板 | 评分使用下拉与评分按钮混用 | 评估表单 | 业绩评分/价值观评分使用 `Select`；绩效等级建议使用评分按钮 | 统一组件，减少用户认知成本 |
| 操作确认 | 提交/退回无二次确认 | 底部操作栏 | 提交评估前弹窗确认；退回需填写原因 | 防止误操作 |
| 互评汇总 | 评论卡片过长 | 互评列表 | 超过 4 行折叠，提供“展开”按钮 | 长评论可折叠 |
| 图标尺寸 | 详情面板内图标不统一 | 详情页 | 统一为 16px，头像使用 `Avatar` 组件 | 视觉一致 |
| 桌面分屏 | 无 | 左侧列表 + 右侧详情 | 桌面使用左右分栏，左侧下属列表，右侧详情面板 | 桌面端无需跳转即可评估 |
| 移动端列表-详情 | 左右分屏在手机上不可用 | `LeaderEval` 页面 | 在移动端拆分为 `SubordinateList` 和 `SubordinateDetail` 两个视图，通过路由或状态切换；列表使用 `.table-card-list` | 手机下先选下属再进入详情，底部固定操作栏（提交/退回） |
| 移动端详情折叠 | 详情页内容在手机上过长 | 详情页 | 在移动端使用折叠面板（Collapse）分区块：员工信息、目标、自评、互评、上级评估 | 手机下每屏只展开一个区块，便于浏览 |

### 3.6 绩效校准页（calibration.html → `src/pages/Calibration/index.tsx`）

| 目标 | 现状问题 | 修改范围 | 具体改法 | 验收标准 |
|---|---|---|---|---|
| 颜色语义 | `.score-change.up` 为危险红，`.down` 为成功绿，语义混乱 | 校准矩阵样式 | 将 `.score-change.up` 改为 `--color-success`（分数增加），`.score-change.down` 改为 `--color-danger`（分数减少）；或两者均使用 `--color-text-secondary` 避免语义歧义 | 颜色语义直观，不误导 |
| 异常行 | 异常行高亮但 hover 色硬编码 | 矩阵表格 | 使用 `--color-warning-bg` 与 `--color-warning-bg` hover 加深，避免 `#FFF0E0` 硬编码 | 使用 CSS 变量 |
| 输入校验 | 校准后评分无校验 | 分数输入 | 限制输入范围（如 1-5），超出时显示错误提示 | 输入非法时阻止提交并提示 |
| 审批操作 | 底部审批按钮缺少说明 | 审批卡片 | “驳回并说明”弹窗输入原因；“通过并提交”二次确认 | 审批流程可闭环 |
| 分布图 | 实际/目标对比条形图 | 分布组件 | 实际使用 `--color-primary`，目标使用 `--color-chart-grid` | 与设计稿一致 |
| 桌面分布对比 | 无 | 校准页 | 桌面使用双向条形图对比实际/目标分布，矩阵表格展示完整字段 | 桌面端可完整对比校准前后差异 |
| 移动端分布简化 | 双向条形图在手机上不可读 | 分布图 | 在移动端使用 `.mobile-distribution` 数字卡片 + 横向进度条，展示各等级实际人数与目标人数对比 | 手机下各等级对比清晰 |
| 移动端矩阵卡片 | 人员矩阵表格在手机上列多 | 校准矩阵 | 在移动端使用 `.table-card-list`，每张卡片显示：姓名、部门、初始评分、校准后评分、价值观、状态、调整按钮 | 手机下矩阵卡片化，关键操作可触 |
| 移动端审批按钮 | 桌面审批按钮在手机上分散 | 审批操作 | 在移动端使用 `.form-bottom-actions` 固定底部审批按钮（提交 HR 审批/通过/驳回） | 手机下审批按钮始终可见，方便单手操作 |

---

## 4. 组件改造

### 4.1 Button（按钮）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 统一按钮样式 | 封装 `Button` 组件，支持 `variant="primary|secondary|ghost|danger"`、`size="sm|default|lg"` | 所有按钮使用同一组件，不再使用原生 Ant Design 按钮样式直接覆盖 |
| 状态 | 默认 32px 高；hover/active/disabled 按令牌；危险按钮使用红色系 | 与设计稿按钮表一致 |

### 4.2 Card（卡片）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 统一卡片 | 封装 `Card` 组件，`header`/`body` 结构可选；默认白底、1px border、8px 圆角、Raised 阴影 | 所有卡片使用同一组件，不再散落样式 |
| 内边距分级 | 支持 `padding="sm|md|lg"`（16/20/24px） | 与设计规范一致 |

### 4.3 Tag / Badge（标签）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 语义化 | 封装 `StatusTag` 组件，支持 `type="success|warning|danger|info|primary|default"`、`pill` 变体 | 所有状态展示使用 Tag，不单独用色字 |
| 尺寸 | 支持 `size="sm|default"`（12px/13px） | 设计规范一致 |

### 4.4 Table（表格）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 统一数据表 | 封装 `DataTable` 组件，表头背景 `--color-surface-raised`，行高 48px，单元格 padding 12px 16px | 所有表格样式一致 |
| 操作列 | 操作列使用图标按钮分组，间距 8px | 操作列整齐不拥挤 |
| 空态 | 无数据时显示 `Empty` 组件（图标 + 标题 + 说明 + 可选操作） | 空态统一 |
| 响应式 | 外层包裹 `TableWrapper`，默认 `overflow-x: auto` | 移动端可横向滚动 |

### 4.5 Form（表单）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 统一输入框 | 覆盖 Ant Design `Input` 样式：高度 32px，边框 `--color-border`，圆角 6px，focus 主色 + 外描边 | 所有输入框样式一致 |
| 标签 | 标签 14px，medium 字重，底部间距 8px；必填项加红色 `*` | 表单标签统一 |
| 错误态 | 错误边框 `--color-danger`，错误提示 13px 红色 | 校验失败时显示正确 |
| 文本域 | `TextArea` 最小高度 96px，支持 resize: vertical | 长文本输入符合规范 |

### 4.6 Steps（步骤条）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 统一步骤条 | 节点直径 24px；当前态主色，已完成态成功色，待处理态灰色 | 步骤状态清晰 |
| 可访问性 | 增加 `aria-label`、`aria-current` | 屏幕阅读器可识别 |

### 4.7 Progress（进度条）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 统一进度条 | 默认 8px 高，轨道 `--color-border`，填充支持主色/成功/警告 | 所有进度条样式一致 |
| 带标签 | 提供 `withLabel` 属性，右侧显示百分比 | 进度与数值对齐 |

### 4.8 Avatar（头像）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 统一头像 | 默认 32px，支持 `size="sm|default|lg"`，背景按角色自动取色 | 头像尺寸与设计规范一致 |
| 用户名 | 默认显示姓名首字，支持图片头像 | fallback 正确 |

### 4.9 Charts（图表）

| 目标 | 改法 | 验收标准 |
|---|---|---|
| 优先轻量 | 简单图表使用 CSS/SVG 内联实现（如环形图、柱状图、折线图） | 不引入额外图表库时即可满足设计 |
| 如需图表库 | 使用 ECharts/Ant Design Charts，但需将色系映射到 `--color-chart-1` ~ `--color-chart-6` | 图表色彩与令牌一致 |

### 4.10 响应式组件

| 组件 | 改法 | 验收标准 |
|---|---|---|
| **MobileTableCardList** | 封装 `TableCardList` 组件，接收 `columns` 和 `dataSource`，在移动端渲染为卡片列表，每张卡片显示 3-4 个关键字段，支持点击展开/操作 | 所有表格在移动端自动切换为卡片列表，无需每个页面单独写 |
| **KPIScrollGrid** | 封装 `KPIScrollGrid` 组件，使用 `flex + overflow-x: auto + scroll-snap` 实现横向滑动 KPI 卡片 | 小屏下 KPI 可横向滑动，无挤压 |
| **BottomActions** | 封装 `BottomActions` 组件，固定底部，高度 56px，安全区适配，支持主/次/危险按钮布局 | 长表单页面底部操作栏一致，iPhone 底部横条不遮挡 |
| **StepsCompact** | 封装 `StepsCompact` 组件，只显示当前步骤名和进度，适合移动端 | 手机下步骤条不占用过多横向空间 |
| **MobileDrawer** | 封装 `MobileDrawer` 组件，用于筛选器、操作面板等，从底部滑出 | 手机下筛选/操作面板不遮挡核心内容 |
| **Sparkline** | 封装 `Sparkline` 组件，80px 高迷你折线图，无坐标轴，仅展示趋势 | 手机下趋势图可在一行内展示 |
| **ResponsiveShow** | 封装 `ResponsiveShow` 组件，支持 `breakpoint="sm|md|lg|xl"` 和 `hide/show` 属性，基于窗口宽度显隐 | 响应式显隐逻辑集中管理，避免散落媒体查询 |

---

## 5. 需要新增 / 修改的 React 组件

### 5.1 新增组件

| 组件路径 | 说明 |
|---|---|
| `src/components/AppShell/index.tsx` | 页面外壳：左侧边栏 + 顶部全局栏 + 内容区 |
| `src/components/Sidebar/index.tsx` | 侧边栏导航，含 Logo、分组、菜单项 |
| `src/components/Topbar/index.tsx` | 顶部全局栏，含页面标题、搜索、通知、角色切换、头像 |
| `src/components/Button/index.tsx` | 统一按钮组件 |
| `src/components/Card/index.tsx` | 统一卡片组件 |
| `src/components/Tag/index.tsx` | 统一标签/徽章组件 |
| `src/components/DataTable/index.tsx` | 统一表格组件 |
| `src/components/Steps/index.tsx` | 步骤条组件 |
| `src/components/Progress/index.tsx` | 进度条组件 |
| `src/components/Avatar/index.tsx` | 头像组件 |
| `src/components/EmptyState/index.tsx` | 空态组件 |
| `src/components/RatingOptions/index.tsx` | 5 分制评分选项（支持键盘/可访问性） |
| `src/components/Chart/BarChart.tsx` | 简易柱状图（可选） |
| `src/components/Chart/LineChart.tsx` | 简易折线图（可选） |
| `src/components/Chart/DonutChart.tsx` | 简易环形图（可选） |
| `src/components/TableCardList/index.tsx` | 移动端表格卡片列表 |
| `src/components/KPIScrollGrid/index.tsx` | 移动端 KPI 横向滑动网格 |
| `src/components/BottomActions/index.tsx` | 底部固定操作栏 |
| `src/components/StepsCompact/index.tsx` | 移动端紧凑步骤条 |
| `src/components/MobileDrawer/index.tsx` | 移动端底部抽屉 |
| `src/components/Sparkline/index.tsx` | 迷你 sparkline 趋势图 |
| `src/components/ResponsiveShow/index.tsx` | 响应式显隐组件 |

### 5.2 修改组件

| 组件路径 | 修改内容 |
|---|---|
| `src/App.tsx` | 引入全局样式/令牌，配置 Ant Design 主题 |
| `src/router/index.tsx` | 确保 6 个页面路由存在，layout 使用 AppShell |
| `src/pages/Home/index.tsx` | 按原型重排布局，替换为统一组件 |
| `src/pages/Dashboard/index.tsx` | 重构图表与 KPI 布局 |
| `src/pages/HRConsole/index.tsx` | 周期表格与参与人管理改造 |
| `src/pages/SelfEval/index.tsx` | 长表单、步骤条、评分选项改造 |
| `src/pages/LeaderEval/index.tsx` | 左右分栏评估改造 |
| `src/pages/Calibration/index.tsx` | 校准矩阵、分布图、审批流程改造 |

---

## 6. 需要调整的全局样式（global.css / styles）

```css
/* 引入设计令牌 */
@import "./variables.css";

/* 基础覆盖 */
html, body {
  margin: 0;
  padding: 0;
  font-family: var(--font-family);
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-primary);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
}

a {
  color: var(--color-primary);
  text-decoration: none;
}
a:hover { color: var(--color-primary-hover); }

/* 响应式基础 */
.page-content {
  padding: var(--space-6);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

@media (max-width: 1023px) {
  .page-content {
    padding: var(--content-padding-tablet, 24px);
  }
  .sidebar {
    transform: translateX(-100%);
  }
  .sidebar.open {
    transform: translateX(0);
  }
  .menu-toggle {
    display: flex;
  }
}

@media (max-width: 767px) {
  .page-content {
    padding: var(--content-padding-mobile, 16px);
    padding-bottom: calc(var(--content-padding-mobile) + var(--bottom-action-height));
  }
  .data-table {
    display: none;
  }
  .table-card-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-mobile-card-gap, 12px);
  }
  .form-row {
    flex-direction: column;
    gap: var(--space-4);
  }
  .form-control, select, input, textarea {
    min-height: var(--form-input-height-mobile, 44px);
  }
}

@media (max-width: 639px) {
  .kpi-grid {
    display: none;
  }
  .kpi-grid-scroll {
    display: flex;
    overflow-x: auto;
    gap: var(--space-mobile-card-gap, 12px);
    scroll-snap-type: x mandatory;
  }
  .kpi-card {
    flex: 0 0 auto;
    min-width: 160px;
    scroll-snap-align: start;
  }
}

@media (min-width: 1280px) {
  .page-content {
    margin: 0 auto;
  }
  .sidebar {
    transform: translateX(0) !important;
  }
  .main-content {
    margin-left: var(--sidebar-width);
  }
  .menu-toggle {
    display: none !important;
  }
}

/* 焦点态（全局） */
button:focus-visible,
a:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible,
[role="button"]:focus-visible,
[role="radio"]:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(51, 112, 255, 0.15);
}

/* 表单基础 */
input, select, textarea, button {
  font-family: inherit;
}

/* 滚动条 */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}
```

### 6.1 覆盖 Ant Design 5 Token 示例

```tsx
// src/App.tsx
import { ConfigProvider } from "antd";

<ConfigProvider
  theme={{
    token: {
      colorPrimary: "#3370FF",
      colorPrimaryHover: "#2B62E0",
      colorPrimaryActive: "#2456C4",
      colorSuccess: "#00B42A",
      colorWarning: "#FF7D00",
      colorError: "#F53F3F",
      colorText: "#1F2329",
      colorTextSecondary: "#646A73",
      colorTextTertiary: "#6B7280",
      colorBorder: "#DEE0E3",
      colorBgLayout: "#F5F6F7",
      colorBgContainer: "#FFFFFF",
      borderRadius: 8,
      fontSize: 14,
      controlHeight: 32,
    },
  }}
>
  <App />
</ConfigProvider>
```

---

## 7. 需要保留的 Ant Design 组件和需要自定义的样式

### 7.1 保留使用（无需替换）

| Ant Design 组件 | 用途 | 自定义说明 |
|---|---|---|
| `Layout` | 页面整体布局 | 自定义 Sider/Header 背景、宽度、高度 |
| `Menu` | 侧边栏菜单 | 使用自定义样式覆盖默认主题，移除默认选中样式 |
| `Table` | 数据表格 | 使用 `components` / `className` 覆盖表头、行高、hover |
| `Form` | 表单结构 | 覆盖输入框、标签、错误提示样式 |
| `Input` / `TextArea` / `Select` / `DatePicker` | 表单控件 | 覆盖高度、边框、圆角、focus 态 |
| `Button` | 基础按钮 | 如自封装 Button 内部可基于 Ant Design Button 扩展 |
| `Tag` | 状态标签 | 覆盖颜色、圆角、字号 |
| `Steps` | 流程步骤 | 覆盖节点大小、颜色、连线 |
| `Progress` | 进度条 | 覆盖轨道与填充色 |
| `Avatar` | 头像 | 覆盖尺寸、背景色、字号 |
| `Modal` / `Drawer` | 弹窗/抽屉 | 覆盖圆角、阴影、标题字号 |
| `Pagination` | 分页 | 覆盖页码按钮尺寸、选中态 |
| `Upload` | 批量导入 | 覆盖拖拽区域样式 |
| `Empty` | 空态 | 使用自定义图标与文案 |
| `Breadcrumb` | 面包屑 | 覆盖字号、颜色、分隔符 |
| `Alert` / `Message` / `Notification` | 消息提示 | 使用语义色变量 |
| `Tabs` / `Segmented` | 标签/分段控件 | 覆盖激活态下划线/背景 |

### 7.2 需要自定义的样式

- **按钮**：所有 variant 的 background、border、color、hover/active/disabled。
- **卡片**：background、border、border-radius、shadow、padding 分级。
- **表格**：表头背景、行高、hover 背景、选中背景、操作列内边距。
- **表单**：输入框高度、边框、圆角、focus 阴影、错误态、placeholder 色。
- **步骤条**：节点大小、颜色、已完成/当前/待处理态。
- **进度条**：轨道色、填充色、高度、标签。
- **侧边栏**：宽度、背景、分组标题、菜单项高度、active 指示条。
- **顶部栏**：高度、背景、边框、搜索框、图标按钮。

---

## 8. 设计令牌 CSS 变量片段（可直接复制）

```css
:root {
  /* Primary */
  --color-primary: #3370FF;
  --color-primary-hover: #2B62E0;
  --color-primary-active: #2456C4;
  --color-primary-subtle: #E8F0FF;
  --color-primary-text-on: #FFFFFF;

  /* Neutral */
  --color-bg: #F5F6F7;
  --color-surface: #FFFFFF;
  --color-surface-raised: #FAFAFB;
  --color-border: #DEE0E3;
  --color-border-strong: #BBBFC4;
  --color-text-primary: #1F2329;
  --color-text-secondary: #646A73;
  --color-text-tertiary: #6B7280;
  --color-text-disabled: #BBBFC4;

  /* Semantic */
  --color-success: #00B42A;
  --color-success-bg: #E8FFEA;
  --color-warning: #FF7D00;
  --color-warning-bg: #FFF3E8;
  --color-danger: #F53F3F;
  --color-danger-bg: #FFECE8;
  --color-info: #3370FF;
  --color-info-bg: #E8F0FF;

  /* Chart */
  --color-chart-1: #3370FF;
  --color-chart-2: #14C9C9;
  --color-chart-3: #F7BA1E;
  --color-chart-4: #F53F3F;
  --color-chart-5: #86909C;
  --color-chart-6: #00B42A;
  --color-chart-grid: #E8E9EB;

  /* Typography */
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  --font-family-mono: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "PingFang SC", "Microsoft YaHei", monospace;
  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 48px;
  --space-10: 64px;

  /* Layout */
  --sidebar-width: 240px;
  --sidebar-collapsed-width: 72px;
  --header-height: 56px;
  --content-max-width: 1440px;

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;

  /* Shadows */
  --shadow-raised: 0 1px 2px rgba(31, 35, 41, 0.04);
  --shadow-floating: 0 4px 12px rgba(31, 35, 41, 0.08);
  --shadow-overlay: 0 8px 24px rgba(31, 35, 41, 0.12);
  --shadow-backdrop: 0 0 0 9999px rgba(31, 35, 41, 0.45);

  /* Z-index */
  --z-base: 0;
  --z-sticky: 100;
  --z-dropdown: 200;
  --z-modal: 300;
  --z-modal-backdrop: 299;
  --z-toast: 400;
  --z-popover: 500;

  /* Responsive */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
  --font-size-display-mobile: 28px;
  --font-size-h1-mobile: 22px;
  --font-size-h2-mobile: 18px;
  --font-size-h3-mobile: 16px;
  --font-size-h4-mobile: 14px;
  --font-size-body-large-mobile: 15px;
  --font-size-small-mobile: 12px;
  --font-size-micro-mobile: 11px;
  --font-size-statistic-mobile: 24px;
  --touch-target-min: 44px;
  --touch-target-comfortable: 48px;
  --bottom-action-height: 56px;
  --bottom-action-padding: 12px;
  --sidebar-drawer-width: 280px;
  --sidebar-drawer-width-mobile: 100vw;
  --space-mobile-page: 16px;
  --space-mobile-section: 24px;
  --space-mobile-card-gap: 12px;
  --space-mobile-inline: 12px;
  --content-padding-tablet: 24px;
  --content-padding-mobile: 16px;
  --page-header-gap-mobile: 16px;
  --form-input-height-mobile: 44px;
  --bottom-action-z: 110;
}
```

---

## 9. 验收清单

- [ ] 全局 CSS 变量文件已引入，`App.tsx` 中 Ant Design `theme.token` 与设计令牌对齐。
- [ ] 响应式变量已落地：断点、移动端字体、触控目标、底部操作栏、抽屉侧栏等。
- [ ] 媒体查询已统一：1024px / 768px / 640px，无杂散断点。
- [ ] 移动端侧栏抽屉可正常打开/关闭，汉堡菜单在 1024px 以下显示。
- [ ] 所有表格在 768px 以下自动切换为 `.table-card-list` 卡片列表，无横向滚动。
- [ ] Dashboard 在移动端 KPI 可横向滑动，图表已简化为迷你图/横向条形图/关键数字。
- [ ] 长表单页面（自评、上级评估、校准）使用底部固定操作栏，高度 56px，安全区适配。
- [ ] 自评页在移动端分步显示，每屏只显示一个步骤内容。
- [ ] 上级评估在移动端拆分为列表页和详情页，详情页使用折叠面板分区块。
- [ ] 校准页在移动端分布图已简化，人员矩阵已卡片化。
- [ ] Modal 在移动端使用底部 Drawer，高度 90vh，底部按钮可触。
- [ ] 表单输入框在移动端高度 ≥ 44px，字号 16px，防止 iOS 缩放。
- [ ] 所有可点击元素在移动端 ≥ 44px×44px。
- [ ] `AppShell`、`Sidebar`、`Topbar` 组件已落地，所有页面使用统一布局。
- [ ] 6 个核心页面按原型完成布局、信息层级、数据展示改造。
- [ ] 按钮、卡片、标签、表格、表单、步骤条、进度条、头像等组件已统一封装。
- [ ] 所有图标尺寸符合规范：导航 20px，操作 16px，按钮内 14px，趋势 14px。
- [ ] 所有纯图标按钮均已添加 `aria-label`；步骤条、评分选项支持键盘与屏幕阅读器。
- [ ] 所有表单控件均有 `:focus-visible` 样式。
- [ ] `calibration.html` 中 `.score-change.up/down` 颜色语义已修正。
- [ ] `self-eval.html` 长表单增加顶部或底部固定提交/暂存入口。
- [ ] `hr-console.html` 未使用样式已清理，表格分页已拆分。
- [ ] `dashboard.html` 图表数据与表格数据一致，折线图标签无溢出。
- [ ] 无 `/hr/pms/` 下现有文件被误修改。
- [ ] 代码通过项目 lint / TypeScript 检查，无新增报错。

---

## 10. 参考资料

- 设计令牌文档：`/Users/trentshen/Documents/Kimi code - 工作区/hr/design-prototype/DESIGN.md`
- 交付说明文档：`/Users/trentshen/Documents/Kimi code - 工作区/hr/design-prototype/DESIGN-DELIVERY.md`
- 共享样式：`/Users/trentshen/Documents/Kimi code - 工作区/hr/design-prototype/styles.css`
- 原型 HTML：同目录下 `home.html`、`dashboard.html`、`hr-console.html`、`self-eval.html`、`leader-eval.html`、`calibration.html`
