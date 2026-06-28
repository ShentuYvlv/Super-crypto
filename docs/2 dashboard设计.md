# Super Crypto Dashboard 设计方案

版本：v0.1  
日期：2026-06-28  
定位：本地只读量化研究终端，用于查看实验复现、回测、实时信号、数据质量和订单簿成本。

Figma 文件：<https://www.figma.com/design/96EXuMec2XURTt7ap1kysr>  
Overview frame：<https://www.figma.com/design/96EXuMec2XURTt7ap1kysr?node-id=2-2>  
本地截图：[dashboard-overview-figma-v0.png](</Users/zed/all code/A我的/Super-crypto/docs/assets/dashboard-overview-figma-v0.png>)

## 1. 结论

Dashboard 不应该先从“好看的页面”开始，而应该按这个顺序做：

```text
PRD
  -> 信息架构
  -> 数据契约
  -> Figma 设计系统和页面稿
  -> 用 Figma get_design_context / screenshot 生成前端
  -> 接入 SQLite / Parquet / report API
  -> 浏览器验收
```

这次不采用“Codex 纯文字空想页面”的路线。正确流程是：先在 Figma 里生成可审核的 Dashboard 视觉稿，再让 Codex 读取 Figma frame 实现 Next.js 前端。Figma 是 UI 蓝图来源，Codex 负责工程实现、组件化、mock 数据和后端 API 接入。

Figma 不能决定后端字段。数据契约必须先定，再让 Figma 设计这些字段如何展示。尤其是 `experiment_id`、`config_hash`、`split_hash`、`data_snapshot_hash`、`git_commit_hash`、`freshness_sec`、`missing_fields`、`stale_fields`、`fee_cost`、`slippage_cost`、`funding_cost` 这类字段，属于研究终端可信度基础，不能由视觉稿临时补。

Figma 是增强项，不是前端启动的硬依赖。Figma 可用时，按 Figma 生成更统一的产品级 UI；Figma 卡住时，不等它，直接用本文的 token、信息架构和 shadcn/ui 先做 Next.js mock 骨架。

## 2. Dashboard 边界

### 2.1 必须做

- 查看 pipeline 运行状态。
- 查看实验列表、config hash、split hash、data snapshot hash、git commit hash。
- 查看 train / validation / holdout 对比。
- 查看 event-driven 回测结果，vectorbt 只作为对照。
- 查看权益曲线、回撤曲线、交易明细、分币种表现、分月份表现。
- 查看去掉收益最高 5 笔后的表现。
- 查看 vectorbt vs event-driven diff report。
- 查看实时 V4A/V4B 信号。
- 查看 paper trade PnL。
- 查看操纵评分排行。
- 查看数据覆盖率、freshness、missing fields、stale fields。
- 查看 CoinGlass 缓存健康。
- 查看订单簿深度和滑点曲线。

### 2.2 明确不做

- 不直接修改策略配置。
- 不触发 pipeline。
- 不触发 holdout。
- 不作为策略验收依据。
- 不隐藏样本数量、滑点、手续费、Funding 成本。
- 不把漂亮图表替代 no-lookahead、event-driven backtest、holdout guard。

## 3. 推荐技术路线

### 3.1 第一阶段：完整 Next.js 网站

明确不用 Streamlit。Dashboard 做成完整网站，技术栈固定为：

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Table
- ECharts
- TradingView Lightweight Charts
- FastAPI report API

不用 Streamlit 的原因：这个系统需要高密度表格、复杂筛选、图表联动、详情页、状态标签、只读配置查看器和长期组件复用。Streamlit 适合临时研究面板，不适合作为最终产品前端。

图表库职责固定：

- 普通指标图、收益曲线、回撤曲线、双轴图、热力图：ECharts。
- K 线、entry / exit 标注、支撑线、trailing stop：TradingView Lightweight Charts。
- 表格、排序、筛选、列固定、密度切换：TanStack Table。
- UI 基础组件、表单、Tabs、Drawer、Badge、Card：shadcn/ui。

不要同时大量混用 ECharts 和 Recharts。这个 Dashboard 是高密度研究终端，ECharts 更适合复杂 tooltip、缩放、联动和多轴分析。

### 3.2 前后端分工

```text
SQLite
  -> pipeline_runs / pipeline_stages / experiment_runs / signals / trades

Parquet
  -> OHLCV / cycles / scores / features / orderbook / enrichment

FastAPI report API
  -> 只读查询接口

Next.js Dashboard
  -> 页面、筛选、图表、表格、详情
```

Dashboard 只读，不向后端发送“执行实验”“修改配置”“跑 holdout”这类请求。

## 4. 视觉方向

### 4.1 风格选择

采用“专业暗色加密量化终端”风格，参考 Binance / Coinbase Pro / Bloomberg Terminal 的高密度信息结构，但不要做交易所营销页。

关键词：

- dark trading terminal
- dense but readable
- professional quant research
- high contrast
- compact tables
- flat surfaces
- strong data hierarchy
- no flashy gradients
- no decorative hero

### 4.2 设计基调

- 背景：近黑，不用纯黑。
- 卡片：深灰面板，边框清晰，少阴影。
- 主色：黄色只用于主状态、选中态、关键 action、重要 hash/ID 高亮。
- 涨跌：绿色表示正收益 / 上涨，红色表示亏损 / 下跌 / short 风险。
- 警告：橙色表示 stale / partial / warning。
- 错误：红色表示 failed / missing / holdout violation。
- 数字：使用等宽或 tabular font，保证表格列对齐。

### 4.3 基础 Token

```text
canvas:        #0B0E11
surface:       #161A20
surface-2:     #1E2329
border:        #2B3139
text-main:     #EAECEF
text-muted:    #8A929E
accent:        #FCD535
accent-hover:  #F0B90B
positive:      #0ECB81
negative:      #F6465D
warning:       #F59E0B
info:          #3B82F6
```

圆角以 4px / 6px / 8px 为主。不要大圆角卡片，不要渐变球，不要大面积紫蓝渐变。

## 5. 信息架构

### 5.1 主导航

左侧导航：

1. Overview
2. Experiments
3. Backtest
4. Signals
5. Trades
6. Symbols
7. Data Quality
8. Orderbook
9. Reports

顶部状态栏：

- 当前环境：local / research / final_holdout
- 最新 pipeline run 状态
- scanner 状态
- 数据更新时间
- CoinGlass cache 状态
- Git commit hash

状态栏不是装饰，它必须帮助用户判断“当前看到的数据可信不可信”。

### 5.2 页面关系

```text
Overview
  -> Experiment Detail
  -> Signal Detail
  -> Symbol Detail
  -> Data Quality Detail

Experiments
  -> Experiment Detail / Backtest Detail

Signals
  -> Signal Detail
  -> Symbol Detail

Trades
  -> Trade Detail
  -> Signal Detail
  -> Symbol Detail

Symbols
  -> Symbol Detail

Data Quality
  -> Source Detail
```

## 6. 页面设计

执行上分两阶段。页面规划可以完整，但第一版 MVP 只做 4 个页面：

1. Overview
2. Experiments
3. Backtest Detail
4. Signals

这 4 页先验证核心闭环：实验是否可信、信号是否清晰、数据是否可追溯、回测是否防过拟合。

第二阶段再补：

5. Trades
6. Symbol Detail
7. Data Quality
8. Orderbook
9. Reports

不要先做登录、营销首页、账户中心、实盘交易面板、参数敏感性热力图、AutoResearch 解释页。

### 6.1 Overview

目标：30 秒内看清系统是否健康、策略是否有效、今天有没有信号。

首屏模块：

- KPI Strip
  - 今日信号数
  - 活跃监控币数量
  - 最近 7 天 paper PnL
  - 当前 validation best net return
  - 最大回撤
  - 数据健康分
- System Status
  - pipeline latest run
  - scanner heartbeat
  - CoinGlass cache
  - Binance API freshness
  - orderbook snapshot freshness
- Performance Snapshot
  - equity curve
  - drawdown curve
  - train / validation / holdout 对比
- Live Signals
  - 最新 V4A / V4B 信号列表
- Data Warnings
  - missing / stale / failed source 列表

设计要求：

- Overview 不展示过多解释文字。
- 所有指标必须带时间范围。
- holdout 结果必须清楚标记是否 final。
- validation 和 holdout 不能混在一张无标签图里。

### 6.2 Experiments

目标：快速筛选、比较和追踪实验。

核心控件：

- strategy filter：V3 / V4A / V4B
- split filter：train / validation / holdout
- engine filter：vectorbt / event_driven
- status filter：accepted / rejected / failed / running
- date range
- metric sort

表格字段：

- experiment_id
- strategy
- engine
- split
- status
- net return
- Sharpe
- max drawdown
- win rate
- trade count
- fee / pnl ratio
- slippage / pnl ratio
- config hash
- split hash
- data snapshot hash
- git commit hash
- report path

交互：

- 点击行进入 Experiment Detail。
- hash 默认截断显示，hover 展示完整值。
- failed / rejected 必须能直接看到原因。
- trade count 过低的实验必须有明显风险标识。

### 6.3 Backtest Detail

目标：判断一个实验是否真的可信。

顶部摘要：

- experiment_id
- strategy
- engine
- split
- config hash
- split hash
- data snapshot hash
- git commit hash
- final holdout 标记

Tab：

1. Summary
2. Equity & Drawdown
3. Trades
4. By Symbol
5. By Month
6. Robustness
7. Vectorbt Diff
8. Config

必须展示：

- net return
- Sharpe
- Sortino
- max drawdown
- profit factor
- win rate
- avg win / avg loss
- trade count
- median holding time
- MAE / MFE
- fee cost
- slippage cost
- funding cost
- 去掉收益最高 5 笔后的表现
- vectorbt vs event-driven 差异原因

关键原则：

- event-driven 指标是主指标。
- vectorbt 指标只能放在 diff / research 区域。
- 如果 event-driven 明显差于 vectorbt，页面必须突出显示差异。

### 6.4 Signals

目标：查看实时信号、信号原因和后续 paper trade 表现。

列表字段：

- signal_time
- symbol
- strategy
- side
- entry reference
- stop loss
- trailing stop
- confidence
- manipulation score bucket
- reason tags
- data quality
- orderbook slippage
- paper trade PnL
- status

Signal Detail：

- 最近 K 线结构
- pump context
- first sell pressure
- support break
- entry / stop / trailing stop
- confidence breakdown
- data freshness
- missing fields
- orderbook depth
- webhook payload

设计要求：

- SHORT 信号用红色语义，不要用绿色。
- confidence 不等于“能赚钱”，页面文案必须避免误导。
- reason tags 要固定枚举，不要自由文本乱飞。

### 6.5 Trades

目标：查看回测交易和实时 paper trade 的真实表现，避免只看信号数量。

核心筛选：

- trade source：backtest / paper
- strategy：V3 / V4A / V4B
- symbol
- exit reason
- date range
- PnL range
- data quality

表格字段：

- trade_id
- signal_id
- symbol
- side
- entry_time
- entry_price
- exit_time
- exit_price
- gross_return
- fee_cost
- slippage_cost
- funding_cost
- net_return
- exit_reason
- holding_minutes
- MAE
- MFE
- orderbook_snapshot_status

Trade Detail：

- 对应信号原因。
- 入场 K 线和出场 K 线。
- stop loss / trailing stop 变化。
- 成本拆分。
- 订单簿滑点证据。
- 当前交易是否属于 top 5 trades。

设计要求：

- paper trade 和 backtest trade 必须有明显区分。
- 净收益必须扣除 fee、slippage、funding。
- top 5 trades 需要标记，方便判断结果是否过度依赖少数极端交易。

### 6.6 Symbols

目标：查看币种操纵评分和交易可行性。

表格字段：

- symbol
- manipulation_score
- score_bucket
- cycle_count
- avg pump return
- avg dump return
- median duration
- latest funding
- OI change 1h / 6h / 24h
- 24h quote volume
- data completeness
- orderbook depth status
- latest signal

交互：

- 点击进入 Symbol Detail。
- 支持按 score_bucket、数据质量、是否有信号筛选。
- score 必须标记 point-in-time cutoff。

### 6.7 Symbol Detail

目标：把一个币的“为什么触发、是否可交易、历史表现如何”讲清楚。

模块：

- Kline Panel
  - K 线
  - Pump / Dump 周期标注
  - V4A entry / exit 标注
  - support line
  - trailing stop line
- Manipulation Score
  - score trend
  - cycle count
  - score bucket history
- Derivatives
  - OI
  - Funding
  - taker buy/sell
- Orderbook
  - 20-level depth
  - spread bps
  - bid / ask depth
  - slippage curve for 100 / 500 / 1000 USDT
- Trades
  - 该 symbol 历史交易
  - paper trade 当前状态

设计要求：

- 图表和表格联动。
- 所有标注必须来自 signal_time 之前已经可得的数据。
- 如果订单簿快照缺失，必须标记该信号“低可信”。

### 6.8 Data Quality

目标：快速发现数据源问题，避免脏数据污染实验。

模块：

- Source Health Matrix
  - Binance klines
  - Binance ticker
  - Binance funding
  - Binance open interest
  - Binance orderbook
  - CoinGlass tickers
  - CoinGlass futures flow
  - CoinGlass spot flow
  - CoinGlass coin info
- Freshness Timeline
- Missing Fields Table
- Stale Fields Table
- Cache Status
- Failed Requests
- Coverage by Symbol

状态定义：

- healthy：数据新鲜且字段完整。
- partial：字段缺失但不影响核心 K 线逻辑。
- stale：超过 freshness 阈值。
- failed：请求失败或数据不可用。
- blocked：影响信号可信度或实验复现。

### 6.9 Orderbook

目标：验证策略是否真的能成交，而不是纸面盈利。

模块：

- candidate symbol list
- spread bps
- bid / ask depth
- depth imbalance
- estimated slippage
- max trade size under 50 bps
- depth snapshots timeline
- slippage stress table

必须突出：

- 妖币盘口薄，滑点可能吞掉收益。
- 没有订单簿快照的交易不能和有快照的交易同等可信。

### 6.10 Reports

目标：统一访问 Markdown / HTML / CSV / diff report。

列表字段：

- report type
- experiment_id
- generated_at
- split
- strategy
- path
- hash

支持打开：

- Markdown report
- HTML report
- trade log CSV
- vectorbt diff report
- robustness report
- data coverage report

## 7. 组件库

第一批必须做这些组件：

- AppShell
- TopStatusBar
- SideNav
- MetricCard
- StatusBadge
- HashBadge
- RiskBadge
- DataQualityBadge
- SplitBadge
- StrategyBadge
- SignalReasonTags
- MetricDelta
- EquityChart
- DrawdownChart
- KlinePanel
- PnLChart
- SlippageCurve
- OrderbookDepthPanel
- ExperimentTable
- TradeTable
- SignalTable
- SymbolScoreTable
- DataQualityTable
- ConfigViewer
- EmptyState
- ErrorState
- LoadingSkeleton

组件原则：

- 表格优先支持排序、筛选、列固定、密度切换。
- 数字列右对齐。
- hash 使用等宽字体。
- 状态标签颜色必须稳定，不随页面变化。
- 图表必须有明确时间范围和数据来源。

## 8. 数据契约

前端不能直接猜字段，必须先定义只读 API。

### 8.1 API 分组

```text
GET /api/overview
GET /api/pipeline/runs
GET /api/pipeline/runs/{run_id}
GET /api/experiments
GET /api/experiments/{experiment_id}
GET /api/experiments/{experiment_id}/trades
GET /api/experiments/{experiment_id}/metrics
GET /api/experiments/{experiment_id}/diff
GET /api/signals
GET /api/signals/{signal_id}
GET /api/trades
GET /api/trades/{trade_id}
GET /api/paper-trades
GET /api/symbols
GET /api/symbols/{symbol}
GET /api/symbols/{symbol}/klines
GET /api/symbols/{symbol}/orderbook
GET /api/data-quality
GET /api/reports
```

### 8.2 前端必需字段

所有接口返回都必须包含：

- generated_at
- source
- freshness_sec
- data_quality
- missing_fields
- stale_fields

实验相关接口必须包含：

- config_hash
- split_hash
- data_snapshot_hash
- git_commit_hash
- report_path

信号相关接口必须包含：

- signal_time
- decision_time
- data_cutoff_time
- entry_reference
- reason

这些字段是防止页面误读结果的基础。

## 9. Figma 工作流

### 9.1 当前 Figma 状态

- Figma MCP 已连接。
- 已创建设计文件：<https://www.figma.com/design/96EXuMec2XURTt7ap1kysr>
- 已生成第一版 Overview 页面 frame：`2:2`
- Overview frame 链接：<https://www.figma.com/design/96EXuMec2XURTt7ap1kysr?node-id=2-2>
- 已通过 `get_metadata` 验证图层结构。
- 已通过 `get_screenshot` 导出视觉截图。
- 已通过 `get_design_context` 验证后续可用于 Next.js 实现。
- 后续代码实现必须基于具体 Figma frame，不允许跳过 Figma 直接写页面。

注意：当前完成的是 Overview 第一版 Figma 页面稿，不是完整多页面设计系统。下一步先补 MVP 的 Experiments、Backtest Detail、Signals 三个 frame；Trades、Symbol Detail、Data Quality、Orderbook、Reports 放第二阶段。

### 9.2 Figma 能力命名

不要把 `Figma Create Design System`、`Figma Generate Design`、`Figma Implement Design` 当成固定插件名。更准确的说法是：

```text
安装 Figma MCP / Codex Figma Plugin
  -> 使用 Figma skills 或自定义 skill 执行工作流
  -> Generate Design System
  -> Generate Dashboard Pages
  -> Implement Design in Code
  -> Compare Screenshot and Iterate
```

Figma MCP / Codex Figma Plugin 是基础设施。skills 是可复用指令集，不是 MCP 的替代品。

第一批能力：

1. Figma MCP / Codex Figma Plugin
2. `crypto-dashboard-design-system` skill
3. `crypto-dashboard-page-generation` skill
4. `crypto-dashboard-implementation` skill

第二批能力：

1. Figma Code Connect
2. `crypto-dashboard-component-mapping` skill

第一次做不需要马上沉淀完整自定义 skill。先用本文 prompt 跑通 Figma -> Next.js；做完 2-3 个页面后，再把稳定规则沉淀成上述 skill。

自定义 skill 的职责：

- `crypto-dashboard-design-system`：固定暗色金融终端 token、字体、间距、圆角、状态色、基础组件。
- `crypto-dashboard-page-generation`：按本文信息架构生成 Figma 页面，禁止营销页、写操作按钮、holdout 执行入口。
- `crypto-dashboard-implementation`：按 Figma frame 实现 Next.js App Router + TypeScript + Tailwind + shadcn/ui + TanStack Table + ECharts。
- `crypto-dashboard-component-mapping`：后续把 Figma 组件和代码组件映射起来。

### 9.3 执行顺序

```text
Step 1: 先锁定数据契约和字段
Step 2: 用 Figma MCP 生成设计系统基础
Step 3: 生成 4 个 MVP 页面：Overview / Experiments / Backtest Detail / Signals
Step 4: 使用 get_screenshot 检查视觉
Step 5: 使用 get_design_context 读取 frame 结构
Step 6: 人工检查视觉、布局和信息层级
Step 7: 生成 Next.js App Router + TypeScript + Tailwind + shadcn/ui 代码
Step 8: mock 数据组件化
Step 9: 接 FastAPI / SQLite / Parquet 只读 API
Step 10: 用浏览器截图和 Figma 对比，修复差异
Step 11: 第二阶段补 Trades / Symbol Detail / Data Quality / Orderbook / Reports
```

### 9.4 Figma 设计系统 Prompt

```text
Create a professional dark-mode design system for a crypto quant research dashboard.

The product is a local read-only dashboard for a manipulation-cycle backtesting and realtime signal system.

Style:
- dark trading terminal
- Binance-like high contrast
- dense but readable
- professional quant research tool
- compact tables
- flat panels
- no decorative gradients
- no marketing hero

Define:
- color tokens
- typography
- spacing
- dark surfaces
- table styles
- status badges
- risk colors
- chart colors
- form controls
- navigation
- metric cards
- data quality badges
- hash badges
- signal reason tags
```

### 9.5 Figma 页面 Prompt

```text
Design a professional dark-mode crypto quant research dashboard for Super Crypto.

The dashboard monitors Binance futures symbols, V4A/V4B short signals, pump-dump cycles, backtest results, data quality, CoinGlass cache health, orderbook slippage, and experiment logs.

Important constraints:
- Dashboard is read-only.
- It must not trigger experiments.
- It must not trigger holdout.
- Event-driven backtest metrics are primary.
- vectorbt is only a research comparison.
- Every experiment must show config hash, split hash, data snapshot hash, and git commit hash.

Pages:
1. Overview
2. Experiments
3. Backtest Detail
4. Realtime Signals
5. Trades
6. Symbol Detail
7. Data Quality
8. Orderbook
9. Reports

Reusable components:
MetricCard, TopStatusBar, ExperimentTable, TradeTable, SignalTable, KlinePanel, PnLChart, DrawdownChart, OrderbookDepthPanel, SlippageCurve, DataQualityBadge, HashBadge, SignalReasonTags.
```

### 9.6 Figma 到 Next.js 实现 Prompt

```text
读取当前 Figma frame，并使用 Figma skill 实现为前端页面。

技术栈：
Next.js App Router + TypeScript + Tailwind CSS + shadcn/ui + TanStack Table + ECharts + TradingView Lightweight Charts。

要求：
1. 先使用 get_design_context 获取精确 frame 结构。
2. 再使用 get_screenshot 获取视觉参考。
3. 生成代码前先分析页面结构。
4. 尽量复用 shadcn/ui 组件。
5. 表格、图表、状态卡片都要组件化。
6. 所有 mock 数据放到 lib/mock-*.ts。
7. 所有接口类型放到 types/api.ts。
8. 不写死 hash、metric、signal。
9. 不接真实后端，先完成 mock 版。
10. 不增加写操作按钮。
11. Dashboard 只能只读。
12. 保持 Figma 的布局、层级、间距和视觉风格。
13. 完成后用浏览器截图和 Figma 参考图对比，继续修复差异。
```

## 10. 实现计划

### Phase A：MVP 设计和数据契约

交付：

- `dashboard设计.md`
- Dashboard API schema
- Figma Overview frame
- Figma design system foundations
- 4 个 MVP 页面设计稿：Overview、Experiments、Backtest Detail、Signals
- 组件命名规范

验收：

- MVP 页面覆盖实验可信度、信号解释、回测详情和运行状态。
- 所有页面都能对应到 SQLite / Parquet / report 数据源。
- 没有任何“执行实验”“跑 holdout”的入口。
- 每个要实现的页面都有明确 Figma frame URL 和 node id。

### Phase B：Next.js 前端骨架

交付：

- Next.js app
- AppShell
- TopStatusBar
- SideNav
- 基础路由
- 全局暗色主题
- mock data
- 核心组件库

验收：

- 本地能打开 Dashboard。
- mock 数据能展示 Overview、Experiments、Backtest Detail、Signals。
- 表格、图表、状态标签样式统一。

### Phase C：真实数据接入

交付：

- FastAPI report API
- SQLite 查询层
- Parquet 查询层
- 实验详情页真实数据
- 信号列表真实数据
- Backtest Detail 真实数据

验收：

- 能查看实验列表、回测曲线、交易摘要、分组表现。
- 能查看实时信号、信号原因和数据 freshness。
- 能区分 validation / holdout / event-driven / vectorbt。

### Phase C2：研究终端扩展页面

交付：

- Trades
- Symbol Detail
- Data Quality
- Orderbook
- Reports

验收：

- 能查看完整交易明细和 paper trade。
- 能查看 Symbol K 线、信号标注、操纵评分、Funding / OI。
- 能查看 CoinGlass cache、数据覆盖率、missing / stale fields。
- 能查看订单簿深度和滑点曲线。
- 能统一打开 Markdown / HTML / CSV / diff report。

### Phase D：浏览器验收

验收项：

- 1440px 桌面可读。
- 1280px 笔记本可读。
- 表格列不乱挤。
- 长 hash 不撑爆布局。
- 图表为空时有 EmptyState。
- 数据源失败时有 ErrorState。
- 数字颜色和交易语义一致。
- validation / holdout 不会被误读。
- 所有关键指标都有时间范围。

按你的要求，浏览器验收不用 Playwright，直接用浏览器检查。

## 11. 关键验收清单

MVP 设计完成前必须逐项检查：

- 是否覆盖 Overview、Experiments、Backtest Detail、Signals。
- 是否明确 Dashboard 只读。
- 是否没有 holdout 执行入口。
- 是否区分 vectorbt 和 event-driven。
- 是否展示 config hash、split hash、data snapshot hash、git commit hash。
- 是否展示 trade count，避免小样本误导。
- 是否展示手续费、滑点、Funding 成本。
- 是否展示去掉 top 5 trades 后表现。
- 是否展示数据 freshness、missing fields、stale fields。
- 是否所有图表都有时间范围和数据来源。

第二阶段设计完成前再检查：

- 是否覆盖 Trades / paper trade 结果。
- 是否覆盖 Symbol Detail。
- 是否覆盖 Data Quality。
- 是否补上 Orderbook 和 Reports。
- 是否展示 CoinGlass cache 健康。
- 是否展示订单簿深度和滑点曲线。

## 12. 页面优先级

第一阶段 MVP：

1. Overview
2. Experiments
3. Backtest Detail
4. Signals

第二阶段研究终端能力：

5. Trades
6. Symbol Detail
7. Data Quality
8. Orderbook
9. Reports

第三优先级：

1. 多实验对比
2. 参数敏感性热力图
3. AutoResearch 实验解释页

不要先做登录、营销首页、账户中心、实盘交易面板。这些都不是当前产品目标。

## 13. 最终判断标准

这个 Dashboard 做得好不好，不看它像不像交易所官网，而看四件事：

1. 能不能快速判断实验结果是否可信。
2. 能不能暴露策略过拟合、滑点低估、样本过少、数据缺失。
3. 能不能让 V4A 信号的触发原因、成本和风险一眼看清。
4. 能不能长期支撑 AutoResearch 前的实验日志和报告复盘。

一句话：它是研究终端，不是炫酷大屏，也不是交易下单系统。
