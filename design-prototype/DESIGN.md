# PMS 绩效管理系统设计令牌文档

> 基于飞书绩效 / 飞书 People 视觉语言，以 Linear 作为结构参考底，融合 Modern Minimal + Tech Utility 视觉方向。
> 版本：v2.2 | 适配：Ant Design 5 组件库  
> 更新：响应式改造完成后，`--color-text-tertiary` 已统一为 `#6B7280`。``

---

## 1. Visual Theme

**Philosophy**: 干净、通透、任务导向——让绩效信息像飞书一样清晰易读，让管理工作像仪表盘一样高效可见。

**Direction**: Modern Minimal + Tech Utility，轻商务、温暖、克制。

**Personality**: 专业、可信、亲和、效率。

**Reference**: 飞书绩效 / 飞书 People、Linear（结构与信息密度）、Notion（留白与温暖感）。

---

## 2. Color Palette

### Primary

| Token | HEX | OKLCh | Usage |
|-------|-----|-------|-------|
| `--color-primary` | `#3370FF` | `oklch(58% 0.22 255)` | 主按钮、链接、激活状态、关键操作 |
| `--color-primary-hover` | `#2B62E0` | `oklch(53% 0.20 255)` | 主按钮悬停、链接悬停 |
| `--color-primary-active` | `#2456C4` | `oklch(49% 0.18 255)` | 主按钮按下 |
| `--color-primary-subtle` | `#E8F0FF` | `oklch(94% 0.04 255)` | 轻量背景、选中态、Tag 背景 |
| `--color-primary-text-on` | `#FFFFFF` | `oklch(100% 0 0)` | 主色背景上的文字 |

### Neutral

| Token | HEX | OKLCh | Usage |
|-------|-----|-------|-------|
| `--color-bg` | `#F5F6F7` | `oklch(97% 0.002 245)` | 页面背景、侧边栏背景 |
| `--color-surface` | `#FFFFFF` | `oklch(100% 0 0)` | 卡片、弹窗、浮层、内容区背景 |
| `--color-surface-raised` | `#FAFAFB` | `oklch(98.5% 0.001 245)` | 表头、次级卡片、hover 背景 |
| `--color-border` | `#DEE0E3` | `oklch(88% 0.01 245)` | 分割线、边框、输入框边框 |
| `--color-border-strong` | `#BBBFC4` | `oklch(77% 0.015 245)` | 聚焦边框、强调分隔 |
| `--color-text-primary` | `#1F2329` | `oklch(24% 0.01 245)` | 标题、正文、主文本 |
| `--color-text-secondary` | `#646A73` | `oklch(48% 0.015 245)` | 辅助说明、次要信息 |
| `--color-text-tertiary` | `#6B7280` | `oklch(55% 0.012 245)` | 占位符、禁用态、最弱信息 |
| `--color-text-disabled` | `#BBBFC4` | `oklch(77% 0.015 245)` | 禁用文字 |

### Semantic

| Token | HEX | OKLCh | Usage |
|-------|-----|-------|-------|
| `--color-success` | `#00B42A` | `oklch(68% 0.22 145)` | 成功、已完成、正向状态 |
| `--color-success-bg` | `#E8FFEA` | `oklch(96% 0.06 145)` | 成功状态背景 |
| `--color-warning` | `#FF7D00` | `oklch(70% 0.20 55)` | 警告、待处理、需谨慎 |
| `--color-warning-bg` | `#FFF3E8` | `oklch(97% 0.05 55)` | 警告状态背景 |
| `--color-danger` | `#F53F3F` | `oklch(62% 0.22 25)` | 错误、删除、危险操作 |
| `--color-danger-bg` | `#FFECE8` | `oklch(95% 0.05 25)` | 错误状态背景 |
| `--color-info` | `#3370FF` | `oklch(58% 0.22 255)` | 信息提示、进行中 |
| `--color-info-bg` | `#E8F0FF` | `oklch(94% 0.04 255)` | 信息状态背景 |

### Chart / Data Visualization

| Token | HEX | OKLCh | Usage |
|-------|-----|-------|-------|
| `--color-chart-1` | `#3370FF` | `oklch(58% 0.22 255)` | 主系列、柱状图、折线图 |
| `--color-chart-2` | `#14C9C9` | `oklch(75% 0.15 190)` | 次系列、对比色 |
| `--color-chart-3` | `#F7BA1E` | `oklch(78% 0.16 80)` | 第三系列、分布图 |
| `--color-chart-4` | `#F53F3F` | `oklch(62% 0.22 25)` | 风险/负向系列 |
| `--color-chart-5` | `#86909C` | `oklch(60% 0.02 245)` | 中性/基准线 |
| `--color-chart-6` | `#00B42A` | `oklch(68% 0.22 145)` | 正向/达成系列 |
| `--color-chart-grid` | `#E8E9EB` | `oklch(91% 0.005 245)` | 图表网格线 |

---

## 3. Typography

### Font Stacks

- **Heading / Body**: `-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif`
- **Mono**: `"SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "PingFang SC", "Microsoft YaHei", monospace`

### Type Scale

| Level | Size | Weight | Line-height | Letter-spacing | Usage |
|-------|------|--------|-------------|----------------|-------|
| Display | `32px / 2rem` | 600 | 1.25 | `-0.02em` | 数据大屏关键数字、页面首屏标题 |
| H1 | `24px / 1.5rem` | 600 | 1.35 | `-0.01em` | 页面标题 |
| H2 | `20px / 1.25rem` | 600 | 1.4 | `0` | 区块标题、卡片标题 |
| H3 | `16px / 1rem` | 600 | 1.5 | `0` | 小节标题、表单分组标题 |
| H4 | `14px / 0.875rem` | 600 | 1.5 | `0` | 列表项标题、小标题 |
| Body | `14px / 0.875rem` | 400 | 1.6 | `0` | 正文、表单标签、表格内容 |
| Body Large | `16px / 1rem` | 400 | 1.6 | `0` | 重要说明、引导文字 |
| Small | `13px / 0.8125rem` | 400 | 1.5 | `0` | 辅助信息、元数据 |
| Micro | `12px / 0.75rem` | 500 | 1.4 | `0.01em` | 标签、徽章、时间戳 |
| Statistic | `28px / 1.75rem` | 600 | 1.2 | `-0.01em` | 数据指标、KPI 数字 |

### Font Weight

| Token | Value | Usage |
|-------|-------|-------|
| `--font-weight-regular` | 400 | 正文、说明 |
| `--font-weight-medium` | 500 | 按钮、标签、导航 |
| `--font-weight-semibold` | 600 | 标题、强调、关键数据 |
| `--font-weight-bold` | 700 | 极少使用，仅大屏数字 |

---

## 4. Component Styles

### Button

| Variant | Background | Text | Border | Border-radius | Padding | Hover | Active |
|---------|------------|------|--------|---------------|---------|-------|--------|
| Primary | `--color-primary` | `#FFFFFF` | none | `6px` | `8px 16px` | `--color-primary-hover` | `--color-primary-active` |
| Secondary | `#FFFFFF` | `--color-text-primary` | `1px solid var(--color-border)` | `6px` | `8px 16px` | `--color-surface-raised` | `--color-bg` |
| Text / Ghost | transparent | `--color-primary` | none | `6px` | `8px 12px` | `--color-primary-subtle` | `--color-primary-subtle` |
| Danger | `--color-danger` | `#FFFFFF` | none | `6px` | `8px 16px` | `#D9363E` | `#B82E34` |
| Disabled | `--color-bg` | `--color-text-disabled` | none | `6px` | `8px 16px` | — | — |

- 按钮高度：默认 `32px`，大尺寸 `40px`，小尺寸 `24px`。
- 图标按钮：`28px × 28px`，圆角 `6px`。
- 危险操作按钮默认使用 Secondary 样式，仅在确认删除等强破坏场景使用 Danger 主按钮。

### Card

- Background: `#FFFFFF`
- Border: `1px solid var(--color-border)`（可选，部分卡片使用无边框+阴影）
- Border-radius: `8px`
- Padding: `16px` / `20px` / `24px`（按信息密度分三级）
- Shadow: `0 1px 2px rgba(31, 35, 41, 0.04)` 或 none
- Hover: 可交互卡片悬停时 shadow 升至 `0 4px 12px rgba(31, 35, 41, 0.08)`

### Tag / Badge

| Type | Background | Text | Border |
|------|------------|------|--------|
| Default | `--color-surface-raised` | `--color-text-secondary` | `1px solid var(--color-border)` |
| Primary | `--color-primary-subtle` | `--color-primary` | none |
| Success | `--color-success-bg` | `--color-success` | none |
| Warning | `--color-warning-bg` | `--color-warning` | none |
| Danger | `--color-danger-bg` | `--color-danger` | none |
| Info | `--color-info-bg` | `--color-info` | none |

- 圆角：`4px`（小标签）/ `12px`（胶囊标签）
- 字号：Micro `12px`，Small `13px`
- 内边距：`4px 8px`（小）/ `6px 12px`（大）

### Table

- 表头背景：`--color-surface-raised`
- 表头文字：`--color-text-primary`，字号 `13px`，字重 `500`
- 行高：`48px`（默认）/ `56px`（宽松）
- 行底边框：`1px solid var(--color-border)`
- 行悬停：`--color-bg`（斑马行可省略）
- 单元格内边距：`12px 16px`
- 操作列：图标按钮 grouped，间距 `8px`
- 空态：居中图标 + 标题 + 说明 + 操作按钮
- 表头筛选：hover 显示筛选图标，选中态显示蓝色下划线或背景高亮

### Form

- 标签：Body `14px`，`--color-text-primary`，字重 `500`，底部间距 `8px`
- 输入框高度：`32px`（默认）/ `40px`（大号）
- 输入框边框：`1px solid var(--color-border)`，圆角 `6px`
- 输入框背景：`#FFFFFF`
- 聚焦边框：`1px solid var(--color-primary)`，外阴影 `0 0 0 2px rgba(51, 112, 255, 0.15)`
- 错误边框：`1px solid var(--color-danger)`，错误提示 `Small 13px` `--color-danger`
- 占位符：`--color-text-tertiary`
- 禁用背景：`--color-bg`，禁用文字：`--color-text-disabled`
- 表单项间距：`24px`（纵向分组）/ `16px`（紧凑布局）
- 分节标题：H3 `16px`，下方加 `12px` 间距与内容分隔
- 步骤条：图标节点直径 `24px`，当前步骤使用 `--color-primary`，已完成使用 `--color-success`

### Input / Select / DatePicker

- 统一使用 `32px` 高度，大号表单使用 `40px`
- Select 下拉面板：圆角 `8px`，阴影 `0 4px 12px rgba(31, 35, 41, 0.12)`
- 选中项背景：`--color-primary-subtle`
- 多选 Tag：使用 `--color-primary-subtle` 背景 + `--color-primary` 文字

### Modal / Drawer

- Modal 背景：`#FFFFFF`，圆角 `12px`
- Modal 阴影：`0 8px 24px rgba(31, 35, 41, 0.16)`
- 标题：H2 `20px`，关闭按钮右上角
- 内容区 padding：`24px`
- 底部操作栏：顶部边框 `1px solid var(--color-border)`，右对齐按钮组，间距 `12px`
- Drawer：宽度 `400px`（默认）/ `560px`（宽详情），背景 `#FFFFFF`
- 遮罩层：`rgba(31, 35, 41, 0.45)`

### Alert / Message / Notification

| Type | Background | Border | Icon | Text |
|------|------------|--------|------|------|
| Success | `--color-success-bg` | `1px solid rgba(0,180,42,0.2)` | success icon | `--color-text-primary` |
| Warning | `--color-warning-bg` | `1px solid rgba(255,125,0,0.2)` | warning icon | `--color-text-primary` |
| Error | `--color-danger-bg` | `1px solid rgba(245,63,63,0.2)` | error icon | `--color-text-primary` |
| Info | `--color-info-bg` | `1px solid rgba(51,112,255,0.2)` | info icon | `--color-text-primary` |

- Alert 圆角：`8px`，padding：`12px 16px`
- Message 圆角：`8px`，阴影 `0 4px 12px rgba(31, 35, 41, 0.12)`

### Menu / Sidebar

- 侧边栏宽度：`240px`（桌面展开）/ `72px`（收起）
- 背景：`--color-bg`（#F5F6F7）
- 分组标题：`Micro 12px`，`--color-text-tertiary`，大写或中文小号，padding `16px 16px 8px`
- 菜单项高度：`40px`
- 菜单项圆角：`6px`
- 默认态：`--color-text-secondary`
- 悬停态：背景 `--color-surface-raised`
- 激活态：背景 `--color-primary-subtle`，文字 `--color-primary`，左侧可加 `3px` 蓝色指示条
- 图标：`20px × 20px`，间距 `12px`
- 顶部 Logo 区高度：`56px`，padding `0 16px`

### Breadcrumb / Page Header

- 面包屑：Small `13px`，`--color-text-secondary`，分隔符 `/`
- 页面标题：H1 `24px`，副标题 Small `13px` `--color-text-secondary`
- 页头操作区：右对齐，主按钮 + 次按钮，间距 `12px`

### Progress / Statistic

- Progress 轨道：`--color-border`，高度 `8px`（默认）/ `4px`（迷你）
- Progress 填充：`--color-primary`（进行中）/ `--color-success`（完成）/ `--color-warning`（有风险）
- 环形进度：圆环宽度 `8px`，中心显示百分比或数值
- Statistic 数值：`28px` 600，标签 `Small 13px` `--color-text-secondary`
- 趋势指示：上升绿色 `+12%`，下降红色 `-5%`

### Tabs / Segmented

- 标签高度：`36px`
- 默认态：`--color-text-secondary`
- 激活态：`--color-text-primary`，底部 `2px` `--color-primary` 下划线
- 卡片式 Tabs：背景 `--color-surface-raised`，圆角 `6px`，激活项背景 `#FFFFFF` + 阴影
- Segmented 控件：背景 `--color-surface-raised`，选中项 `#FFFFFF` + 阴影，圆角 `6px`

### Timeline / Steps

- 节点直径：`24px`（默认）/ `16px`（紧凑）
- 已完成：背景 `--color-success`，图标白色
- 进行中：背景 `--color-primary`，图标白色
- 待处理：背景 `--color-border`，图标 `--color-text-tertiary`
- 连线：`1px solid var(--color-border)`，已完成 `--color-primary`
- 时间标签：Small `13px` `--color-text-secondary`
- 标题：Body `14px` `--color-text-primary`
- 描述：Small `13px` `--color-text-secondary`

### Responsive Components

#### Table

- **桌面端（≥1024px）**：完整列展示，行高 `48px`，操作列图标 grouping，支持横向滚动兜底。
- **平板端（768px–1023px）**：表格保持横向滚动，操作列优先显示主要操作，次要操作收入下拉菜单。
- **移动端（<768px）**：表格转为 `.table-card-list` 卡片列表，每张卡片展示 4-5 个关键字段，操作按钮置于卡片底部，禁止横向滚动。
- **卡片结构**：`.table-card` → `.table-card-header` / `.table-card-body` / `.table-card-footer`。

#### KPI Card

- **桌面端**：4 列或 3 列网格，完整标签和趋势文字。
- **平板端**：2 列网格，关键指标优先展示。
- **移动端**：使用 `.kpi-grid-scroll` 横向滑动，每张卡片固定宽度 `160px`（小屏 `148px`），保留数值和短标签。

#### Form

- **桌面端**：表单按 `.form-row` 两列布局，标签顶部对齐，长表单使用左侧步骤条或分节标题。
- **平板端**：步骤条改为顶部水平，表单单列或两列混合。
- **移动端**：严格单列，输入框高度 `44px`，长表单按步骤分节（每步只显示一个区块），使用 `.form-bottom-actions` 固定底部操作栏（上一步/下一步/保存）。

#### Chart

- **桌面端**：完整趋势图、分布图、图例在侧或顶部，保留坐标轴和全部数据点。
- **平板端**：图表上下堆叠，图例移至下方，减少非关键数据点。
- **移动端**：趋势图转为迷你 sparkline（高度 `80px`）或只显示关键数字 + 趋势箭头；分布图改为横向条形图 + 图例列表；隐藏复杂坐标轴。

#### Modal / Drawer

- **桌面端**：Modal 居中显示，宽度 `480px/640px/800px`；Drawer 右侧滑出，宽度 `400px/560px`。
- **移动端**：Modal 转为 `.modal-bottom-sheet` 底部抽屉；确认弹窗使用 `.action-sheet` 底部操作面板；抽屉占满底部宽度，顶部显示拖拽手柄。

#### Sidebar

- **桌面端（≥1280px）**：左侧边栏 `240px` 常驻，带当前项蓝色指示条。
- **小桌面/平板（768px–1279px）**：侧栏可收缩为抽屉，宽度 `280px`，从左侧滑出，带遮罩层，点击外部关闭。
- **移动端（<768px）**：抽屉占满 `100vw`，汉堡菜单打开，分组菜单可折叠。

#### Filter

- **桌面端**：顶部水平筛选器，常驻显示。
- **平板端**：筛选器可折叠，点击展开。
- **移动端**：顶部仅保留一个“筛选”按钮，点击展开 `.mobile-filter-drawer` 右侧抽屉。

---

## 5. Layout

### Grid

- 内容区最大宽度：`1440px`（大屏自适应）/ `1200px`（标准桌面）
- 栅格列数：`24`（推荐）或 `12`
- 列间距（gutter）：`16px`（桌面）/ `12px`（平板）/ `8px`（移动）
- 页面水平边距：`24px`（桌面）/ `16px`（平板）/ `12px`（移动）

### Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | `0px` | 无间距 |
| `--space-1` | `4px` | 图标与文字间距、紧凑内边距 |
| `--space-2` | `8px` | 按钮内边距、组件内部小间距 |
| `--space-3` | `12px` | 表单控件间距、卡片内紧凑间距 |
| `--space-4` | `16px` | 标准卡片内边距、组件间距 |
| `--space-5` | `20px` | 中等区块间距 |
| `--space-6` | `24px` | 页面边距、大卡片内边距 |
| `--space-7` | `32px` | 区块间间距 |
| `--space-8` | `40px` | 大区块分隔 |
| `--space-9` | `48px` | 页面级间距 |
| `--space-10` | `64px` | 英雄区 / 大屏首屏间距 |

### Layout Structure

| Element | Value | Notes |
|---------|-------|-------|
| Sidebar width | `240px`（展开）/ `72px`（收起） | 左侧固定 |
| Header height | `56px` | 顶部全局栏固定 |
| Content top padding | `24px` | 页面内容区顶部留白 |
| Content bottom padding | `32px` | 页面内容区底部留白 |
| Card gap | `16px` | 卡片/区块之间默认间距 |
| Section gap | `24px` | 大区块之间间距 |

### Page Shell

```
┌────────────────────────────────────────────────────────────┐
│  Header (56px)  │ Logo  │ 全局搜索 │ 通知 │ 角色切换 │ 头像 │
├────────┬───────────────────────────────────────────────────┤
│        │                                                   │
│  Sidebar│  Content Area (padding: 24px)                    │
│ (240px) │                                                   │
│        │  Breadcrumb → Page Title → Actions                 │
│        │                                                   │
│        │  ┌──────────┐  ┌────────────────────────────┐     │
│        │  │ Card 1   │  │ Card 2                     │     │
│        │  │          │  │                            │     │
│        │  └──────────┘  └────────────────────────────┘     │
│        │                                                   │
└────────┴───────────────────────────────────────────────────┘
```

---

## 6. Depth & Elevation

| Level | Shadow | Usage |
|-------|--------|-------|
| Flat | `none` | 默认卡片、列表、表单 |
| Raised | `0 1px 2px rgba(31, 35, 41, 0.04)` | 卡片、下拉面板 |
| Floating | `0 4px 12px rgba(31, 35, 41, 0.08)` | 悬浮菜单、日期面板、提示浮层 |
| Overlay | `0 8px 24px rgba(31, 35, 41, 0.12)` | Modal、Drawer、Notification |
| Backdrop | `0 0 0 9999px rgba(31, 35, 41, 0.45)` | 遮罩层 |

### Z-index Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--z-base` | 0 | 普通内容 |
| `--z-sticky` | 100 | 粘性表头、侧边栏 |
| `--z-dropdown` | 200 | 下拉菜单、日期选择器、Tooltip |
| `--z-modal` | 300 | Modal、Drawer 内容 |
| `--z-modal-backdrop` | 299 | Modal 遮罩层 |
| `--z-toast` | 400 | 全局消息、Notification |
| `--z-popover` | 500 | Popover、Tour 引导 |

---

## 7. Cautions

### Never Do

- 不要使用深色主题作为默认模式，PMS 以浅色通透为主。
- 避免 Card 套 Card 的嵌套堆叠，改用区块标题、留白和语义色块区分层级。
- 避免超过 3 种主色或高饱和装饰色，保持飞书的低饱和、高语义色彩。
- 不要在表格中使用超过 2 种字体大小，保持表格阅读的整齐性。
- 避免将所有角色入口平铺在顶部导航，应下沉到左侧边栏或角色工作台。
- 不要使用纯黑 `#000000` 或纯灰 `#808080` 作为正文色，统一使用语义化文本色。
- 不要为每个状态都使用不同图标，优先使用 Tag + 语义色组合。

### Prefer

- 用 8px 圆角作为默认，需要特殊强调时使用 12px，极少使用 0px（直角）。
- 用留白替代厚重的边框和阴影来分隔区块。
- 用 `--color-text-secondary` 和 `Small` 字号展示辅助信息，弱化视觉噪音。
- 用 Tag + 图标 + 文字组合展示状态，避免单独使用文字状态。
- 用图表（柱状图、折线图、环形图）替代纯数字 + 进度条展示绩效数据。
- 用步骤条 / Timeline 展示长表单工作流（自评、上级评估、校准）。
- 用表格筛选器 grouping 减少操作列拥挤，优先使用图标按钮 + 下拉菜单。

---

## 7.5 Responsive Design Tokens

### Breakpoints

| Token | Value | Usage |
|-------|-------|-------|
| `--breakpoint-sm` | `640px` | 小屏手机断点 |
| `--breakpoint-md` | `768px` | 平板竖屏 / 手机大屏断点 |
| `--breakpoint-lg` | `1024px` | 小桌面 / 平板横屏断点 |
| `--breakpoint-xl` | `1280px` | 大桌面断点 |

### Mobile Typography Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--font-size-display-mobile` | `28px` | 移动端大屏数字 |
| `--font-size-h1-mobile` | `22px` | 移动端页面标题 |
| `--font-size-h2-mobile` | `18px` | 移动端卡片/区块标题 |
| `--font-size-h3-mobile` | `16px` | 移动端小节标题 |
| `--font-size-h4-mobile` | `14px` | 移动端列表项标题 |
| `--font-size-body-large-mobile` | `15px` | 移动端重要正文 |
| `--font-size-small-mobile` | `12px` | 移动端辅助说明 |
| `--font-size-micro-mobile` | `11px` | 移动端标签、徽章 |
| `--font-size-statistic-mobile` | `24px` | 移动端 KPI 数字 |

### Touch & Layout

| Token | Value | Usage |
|-------|-------|-------|
| `--touch-target-min` | `44px` | 最小可点击区域 |
| `--touch-target-comfortable` | `48px` | 舒适点击区域 |
| `--bottom-action-height` | `56px` | 移动端底部固定操作栏高度 |
| `--bottom-action-padding` | `12px` | 底部操作栏内边距 |
| `--bottom-action-z` | `110` | 底部操作栏层级 |
| `--sidebar-drawer-width` | `280px` | 平板抽屉侧栏宽度 |
| `--sidebar-drawer-width-mobile` | `100vw` | 手机端抽屉侧栏宽度 |
| `--space-mobile-page` | `16px` | 移动端页面内边距 |
| `--space-mobile-section` | `24px` | 移动端区块间距 |
| `--space-mobile-card-gap` | `12px` | 移动端卡片间距 |
| `--space-mobile-inline` | `12px` | 移动端行内间距 |
| `--content-padding-tablet` | `24px` | 平板内容区内边距 |
| `--content-padding-mobile` | `16px` | 手机内容区内边距 |
| `--page-header-gap-mobile` | `16px` | 移动端页头间距 |
| `--form-input-height-mobile` | `44px` | 移动端输入框高度 |

---

## 8. Responsive Behavior

### Breakpoints

| Name | Width | Layout Strategy |
|------|-------|-----------------|
| Large Desktop | `≥ 1280px` | 左侧边栏完整展开，多列网格，完整表格与图表 |
| Small Desktop / Tablet Landscape | `1024px – 1279px` | 侧栏可收缩/抽屉，2 列布局，表格可横向滚动 |
| Tablet Portrait | `768px – 1023px` | 抽屉侧栏，单列为主，底部固定操作栏 |
| Mobile | `< 768px` | 严格单列、卡片化、底部固定操作栏、图表简化、长表单分步 |
| Small Mobile | `< 640px` | 进一步压缩间距、字号微调，卡片全宽 |

### Adaptation Rules

- **桌面端（≥1024px）**：侧边栏始终展开，表格完整展示，多列 Dashboard 布局，复杂操作 inline（批量、筛选、排序、导出）。
- **小桌面/平板横屏（1024px–1279px）**：侧边栏可收缩，点击汉堡菜单展开抽屉；内容区 2 列为主；表格可横向滚动。
- **平板竖屏（768px–1023px）**：侧边栏转为抽屉；内容单列为主；表单使用底部固定操作栏；表格可横向滚动或卡片化。
- **移动端（<768px）**：侧边栏全屏抽屉；所有卡片/表格/表单单列堆叠；表格优先转为卡片列表；图表简化为迷你图/关键数字；长表单按步骤分节；底部固定操作栏承载关键操作。
- **小屏手机（<640px）**：进一步压缩页面边距、字号、卡片间距，确保 375px 宽度下无横向滚动。
- **关键操作**：提交、审批、驳回等在移动端必须固定于底部操作栏或顶部明确入口，触控目标不小于 `44px`。

---

## 9. Agent Prompt Guide

### Key Instructions

- 当生成 PMS 页面时，默认使用浅色主题：`--color-bg` 作为页面背景，`--color-surface` 作为卡片背景。
- 所有卡片/容器默认使用 `8px` 圆角，边框使用 `var(--color-border)`（1px），阴影使用 Raised 级别（极轻）。
- 主按钮使用 `--color-primary`（#3370FF），文字白色；次要按钮使用白底灰边框。
- 表格行高使用 `48px`，表头背景 `--color-surface-raised`，操作列使用图标按钮 grouping。
- 状态展示使用 Tag 组件：成功/警告/危险/信息，避免单独用颜色文字表示状态。
- 表单按步骤条 / 分节标题组织，长表单使用进度指示（如自评流程）。
- 数据可视化使用图表色板（chart-1 到 chart-6），避免使用未定义的高饱和颜色。
- 导航结构：左侧边栏（240px）+ 顶部全局栏（56px），内容区自动填充剩余宽度。
- 字体使用系统字体栈，正文 14px，关键数字使用 Statistic 或 Display 尺寸。
- 移动端优先保证可查看 + 可操作，复杂表格可转为横向滚动或卡片列表。

### Quick CSS Snippet

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
}
```

---

## 设计系统推荐说明

### 候选方案对比

| 方案 | 设计系统 | 匹配度 | 特征 | 适合原因 |
|------|---------|--------|------|---------|
| A | Linear | ★★★★☆ | 现代 SaaS 仪表盘、左侧边栏、数据表格、状态徽章、清晰层级 | 结构上与 PMS 的“仪表盘 + 管理表格 + 状态工作流”高度契合，信息密度和导航模式最接近飞书 People |
| B | Notion | ★★★★☆ | 温暖极简、浅灰背景、白色卡片、圆润亲和、留白充分 | 视觉气质上与飞书“轻商务、温暖”最接近，适合降低管理系统的冰冷感 |
| C | Airtable | ★★★☆☆ | 数据库视图、表格密集、数据驱动、色彩系统清晰 | 在表格和信息密度上可参考，但整体视觉偏多彩，需要更克制地收敛到飞书风格 |

### 首选方案：Linear（结构参考）+ Feishu 风格化

最终选择以 **Linear** 作为结构参考底，因为它在以下方面与 PMS 场景最匹配：

1. **导航模式**：Linear 的左侧边栏 + 顶部全局栏与飞书 People 一致，适合多角色工作台。
2. **信息密度**：Linear 擅长在干净界面中展示大量任务状态、优先级、负责人，与绩效管理系统中的待办、评估、校准列表一致。
3. **组件结构**：状态徽章、表格、分面筛选、Timeline、Progress 等组件与 PMS 核心页面需求高度重叠。

但 Linear 本身品牌色偏冷紫/深蓝，与飞书清透蓝不同。因此最终设计令牌以 **飞书绩效/People 视觉语言** 为主线，仅借用 Linear 的信息架构与组件组织方式。色彩、字体、圆角、阴影均按飞书风格重新定义，并确保与 Ant Design 5 组件兼容。

### 备选方案说明

- **Notion**：若后续需要更温暖、更“协作感”的视觉方向，可切换到 Notion 的视觉基因，但 Notion 更偏向文档/wiki，仪表盘与表格能力不如 Linear 成熟。
- **Airtable**：若 PMS 大量页面以数据库视图和字段配置为主，可引入 Airtable 的数据视图模式，但需严格控制色彩饱和度，避免偏离飞书风格。
