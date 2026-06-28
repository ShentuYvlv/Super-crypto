# 妖币操纵周期实验复现与量化信号系统 PRD

版本：v0.1  
日期：2026-06-28  
目标：先复刻《指导文章.md》里的核心实验，再扩展成可持续研究的量化信号系统。

## 1. 背景

文章的核心结论不是“提前预测拉盘”，而是：

- 预测妖币启动前兆不可行，训练集有效但 holdout 失效。
- 摸顶做空不可行，容易变成主观高位判断。
- 相对可行方向是：已经暴涨后的回撤做空，早入场，短持仓，严格按回弹止损/移动止盈退出。
- 最后有效信号主要来自裸 K，OI、Funding、订单簿、链上数据优先作为扩展验证、成本建模和过滤器。

从文章可见内容看，作者没有明确使用深度学习或神经网络作为交易模型。文章里的 AI 更像自动研究员：用 LLM agent 提假设、调参数、跑回测、看 F1/Sharpe/holdout、复盘失败实验。真正的策略更接近规则搜索和参数搜索，不是 LSTM、Transformer、CNN、RNN、深度强化学习或神经网络行情预测。

本项目第一阶段不追求实盘自动交易，而是复刻实验闭环：数据采集、操纵周期识别、庄币评分、V3/V4A/V4B 策略回测、样本外验证和实时信号扫描。

## 2. 产品目标

### 2.1 核心目标

1. 复刻文章实验链路：
   - 从 Binance USDT-M 合约历史 K 线中识别 Pump + Dump 操纵周期。
   - 对合约币种按操纵周期频率做操纵评分。
   - 复刻 V3、V4A、V4B 三类做空策略。
   - 做 train / validation / holdout 验证。
   - 加入手续费、滑点、Funding 成本和 next-bar 成交约束。

2. 建立可扩展研究框架：
   - 支持配置化参数搜索。
   - 支持实验结果落库。
   - 支持分币种、分时间、分市场阶段统计。
   - 支持后续加入 OI、Funding、清算、订单簿、链上数据。

3. 建立文章级数据复现实验底座：
   - 全市场低成本扫描覆盖 Binance 24h、K 线、Funding、OI。
   - 候选级增强覆盖 CoinGlass OI/flow/market cap 和 Binance 订单簿深度。
   - 离线研究路径预留 liquidation、liquidation heatmap、Etherscan 链上转账。
   - 明确 freshness、missing fields、stale fields、source level，避免脏数据污染信号。

4. 建立 AutoResearch 前置工程：
   - 先把数据、标签、策略、回测、验证、日志做成一条可复现实验链路。
   - 每次实验必须由配置驱动，并记录 config hash、指标、交易明细和报告。
   - 后续接入 agent loop 时，只允许 agent 在受保护边界内改配置、提假设、跑 validation。

5. 建立信号系统：
   - 实时扫描目标币。
   - 触发 V4A 类信号。
   - 输出 entry、stop、trailing stop、confidence、reason。
   - 写入数据库并展示到 Dashboard；Webhook 只作为可选通知扩展。

### 2.2 非目标

第一版 MVP 不做：

- 自动实盘下单。
- 高频撮合级回测。
- 本地训练 LLM。
- 深度学习模型。
- 完整 AutoResearch agent 自动改代码。该能力放到 Phase 9，必须等可复现实验闭环稳定后再接。
- 直接复刻文章隐藏的具体阈值。
- 宣称策略可稳定盈利。

文章隐藏了 V4A/V4B 的关键阈值，所以本项目只能通过参数搜索复原近似版本，不能把猜测写成确定事实。

## 3. 用户场景

### 3.1 研究者场景

用户希望选择一批 Binance 合约币，运行完整实验：

```bash
python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation
```

系统输出：

- 操纵周期列表。
- 庄币评分表。
- 策略交易明细。
- 回测指标。
- holdout 结果。
- 参数敏感性分析。

### 3.2 Pipeline 工作流

日常研究不应该手动敲多条子命令。系统必须提供 pipeline 总入口，自动编排数据、切分、标签、评分、增强、实验和报告。

常用命令：

```bash
# 跑完整 train + validation 研究流程
python -m super_crypto.cli pipeline \
  --config configs/pipeline_v4a.yaml \
  --split train_validation

# 只从策略回测阶段开始重跑
python -m super_crypto.cli pipeline \
  --config configs/pipeline_v4a.yaml \
  --split train_validation \
  --from run_experiment

# 只跑某一步 debug
python -m super_crypto.cli pipeline \
  --config configs/pipeline_v4a.yaml \
  --only score_symbols

# 失败后断点续跑
python -m super_crypto.cli pipeline \
  --config configs/pipeline_v4a.yaml \
  --resume

# 最终 holdout，必须显式 final
python -m super_crypto.cli pipeline \
  --config configs/pipeline_v4a.yaml \
  --split holdout \
  --final
```

pipeline 内部按顺序执行：

```text
ingest
  -> build-splits
  -> detect-cycles
  -> score-symbols
  -> enrich
  -> run-experiment
  -> generate-report
```

底层子命令仍保留，用于 debug 和单步重跑。

### 3.3 命令行子命令

第一阶段主入口是 CLI，不依赖前端页面。Dashboard 只用于查看结果，不作为实验执行入口。

推荐命令：

```bash
# 1. 下载基础市场数据
python -m super_crypto.cli ingest --config configs/data.yaml

# 2. 生成固定 split manifest 和 split hash
python -m super_crypto.cli build-splits --config configs/splits.yaml

# 3. 生成 Pump + Dump 周期标签
python -m super_crypto.cli detect-cycles --config configs/cycle.yaml

# 4. 生成 point-in-time 操纵评分
python -m super_crypto.cli score-symbols --config configs/scores.yaml

# 5. 候选级增强和订单簿快照
python -m super_crypto.cli enrich --config configs/enrichment.yaml

# 6. 跑 V4A train + validation，不允许读取 holdout
python -m super_crypto.cli run --config configs/experiment_v4a.yaml --split train_validation

# 7. 最终 holdout，只允许人工触发
python -m super_crypto.cli run --config configs/experiment_v4a.yaml --split holdout --final
```

所有命令必须输出：

- config hash
- split hash
- data snapshot hash
- git commit hash
- report path
- trade log path

### 3.4 本地 Web Dashboard 场景

实验由 CLI / pipeline 执行，结果用本地 Web Dashboard 查看：

```bash
super-crypto report serve --host 127.0.0.1 --port 8000
```

打开：

```text
http://localhost:8000
```

页面必须支持查看：

- 实验列表。
- 配置 hash。
- split hash。
- 数据快照 hash。
- 回测权益曲线。
- 每笔交易。
- 分品种表现。
- train / validation / holdout 对比。
- 不同实验对比。
- 失败原因。
- 参数敏感性分析。
- 数据覆盖率。
- CoinGlass 缓存健康。
- 订单簿深度和滑点曲线。

Dashboard 只读实验结果，不直接修改配置、不触发 holdout。

Dashboard 必须按 [dashboard设计.md](/Users/zed/all%20code/A我的/Super-crypto/dashboard设计.md) 实现，技术路线固定为：

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Table
- ECharts / Recharts
- TradingView Lightweight Charts
- FastAPI report API

明确不使用 Streamlit 作为 Dashboard 主形态。

### 3.5 实时扫描场景

系统每 60 秒扫描目标币：

```bash
python -m super_crypto.realtime.scanner --config configs/scanner.yaml
```

如果触发信号，推送：

- symbol
- strategy：V4A
- side：short
- entry reference
- stop loss
- trailing stop
- confidence
- 触发原因
- 最近 K 线结构

### 3.6 扩展研究场景

用户可以新增一个特征源，比如 Funding：

1. 写入数据采集模块。
2. 写入特征构建模块。
3. 在实验配置中打开该特征。
4. 重新运行 validation。
5. 只有 validation 稳定后，才允许最后跑一次 holdout。

## 4. 总体架构

系统分为八层：

1. 数据层：采集和存储 Binance 基础市场数据、候选级 CoinGlass 增强、订单簿深度，后续扩展 Etherscan 和清算热力图。
2. 标的层：生成币种池，筛选 Binance 合约币、新合约币、老币。
3. 标签层：识别 Pump + Dump 操纵周期。
4. 策略层：实现 V3、V4A、V4B 和后续策略。
5. 回测层：用 vectorbt 做参数扫描，用 event-driven backtester 做最终验收，自定义成本和风控。
6. 验证层：时间切分、币种切分、purged split、无未来函数检查。
7. AutoResearch 层：读取实验历史、提出假设、生成实验计划、运行 validation、解释结果、决定保留或拒绝。
8. 信号层：实时 scanner、本地 Dashboard、可选 Webhook 通知。

数据流：

```text
Binance API
  -> raw parquet
  -> normalized OHLCV
  -> cycle labels
  -> manipulation score
  -> strategy signals
  -> vectorbt parameter scan
  -> event-driven bar backtest
  -> experiment reports
  -> optional autoresearch loop
  -> dashboard
  -> optional webhook
```

## 5. 技术选型

### 5.1 语言和运行环境

- Python 3.11+
- uv 管理依赖和虚拟环境
- ruff 做 lint
- pytest 做测试
- pydantic 做配置校验

理由：量化数据处理、vectorbt、LightGBM、DuckDB、Polars 生态都以 Python 为主。

### 5.2 数据采集

数据采集不能只停留在 K 线。文章前期实验用了 12 大类、60+ 子维度；虽然最终 V4A 主要靠裸 K，但为了复现实验路径、验证“其他指标无效”、模拟真实成本，数据层第一版就要按三条路径设计。

#### 5.2.1 全市场低成本扫描路径

每轮扫描覆盖全部 USDT-M 合约，使用低成本、可高频获取的数据。Binance USDT-M 公共行情接口不需要 API key，`BINANCE_BASE_URL` 只用于切换 endpoint。

| 来源 | 频率 | 范围 | 字段 |
|---|---:|---|---|
| Binance exchange info | 每日 / 启动时 | 全合约 | symbol、base asset、contract status、上线状态、tick size、lot size |
| Binance 24h ticker | 60s | 全合约 | latest price、24h price change、quote volume、trade count |
| Binance K 线 | 1m/5m/15m/1h | 全合约 | OHLCV、quote volume、trades、taker buy base/quote volume |
| Binance funding | 60s / 8h 历史 | 全合约 | current funding、funding delta、funding history |
| Binance open interest | 60s 缓存 | 全合约 | current OI、OI USD value、OI freshness |
| 本地历史锚点 | 每轮计算 | 全合约 | OI 1h/6h/24h change、funding delta、OI acceleration |

用途：

- 实时 scanner 基础输入。
- 操纵评分基础数据。
- V4A 信号上下文。
- 候选池筛选。

#### 5.2.2 候选级深扫路径

只对候选币、watchlist、active pool、top movers 做深扫，避免全市场重数据拖垮扫描。CoinGlass 当前按逆向 `capi.coinglass.com` / `fapi.coinglass.com` 接口和本地缓存设计，不要求 `COINGLASS_API_KEY`；请求必须带 `encryption: true`、`cache-ts-v2`、`origin`、`referer`、`language`、浏览器 UA，并在响应加密时用 header `user` / `v` / `time` 自动 AES-ECB 解密和 gzip/zlib 解压。接口字段变化或请求失败时记录 `request_failed`，不阻断主 pipeline。

| 来源 | 频率 | 范围 | 字段 |
|---|---:|---|---|
| Binance taker long/short ratio | 候选触发时 | 候选级 | 5m taker buy/sell ratio、主动买卖压力 |
| Binance orderbook depth | 候选触发时 | 候选级 | 20-level bid/ask depth、depth imbalance、可成交规模估算 |
| CoinGlass tickers | 缓存 15m | 候选级 | cross-exchange OI、contract volume、exchange breadth、long-short ratio |
| CoinGlass futures flow | 缓存 15m | 候选级 | futures inflow/outflow/netflow 1h/4h/24h |
| CoinGlass spot flow | 缓存 30m | 候选级 | spot inflow/outflow/netflow 1h/4h/24h |
| CoinGlass coin info | 缓存 6h | 候选级 | market cap、circulating supply、total supply、max supply |

用途：

- 验证文章里的 OI/Funding/多空比/taker/订单簿是否有效。
- 给 V4A 信号增加置信度和风险过滤。
- 估算真实滑点、market impact 和最大可开仓规模。
- 做 CoinGlass OI backfill，补齐 Binance OI 缺失。

#### 5.2.3 离线历史研究路径

用于回测、统计和 AutoResearch，不要求每轮实时扫描都拉取。

| 来源 | 范围 | 字段 |
|---|---|---|
| Binance historical klines | 全样本 | 1m/5m/15m/1h OHLCV |
| Binance funding history | 全样本 | funding rate history、funding cost |
| Binance OI history / 本地 OI 快照 | 全样本 | OI level、OI change、OI acceleration |
| Binance taker / long-short history | 可用样本 | taker ratio、global long-short、top trader account/position ratio |
| CoinGlass liquidation | 可用样本 | long liquidation、short liquidation、liq imbalance |
| CoinGlass liquidation heatmap | 可用样本 | 上下方清算池、清算密度、价格距离 |
| CoinGlass orderbook / Binance orderbook snapshots | 候选样本 | depth、spread、imbalance、slippage curve |
| Etherscan V2 | ERC-20 项目 | whale transfer、CEX inflow/outflow、项目方地址转账 |

用途：

- 复现文章 60+ 维实验。
- 做策略有效性归因。
- 做清算热力图和支撑/压力关系研究。
- 做链上出货迹象研究。

#### 5.2.4 数据路径原则

- 不把 CoinGlass 当全市场每轮扫描源；它是候选级、缓存型增强源。
- 全市场扫描优先使用 Binance 低成本数据。
- 订单簿深度只对候选币或信号临近币做快照。
- 所有外部增强数据必须记录 freshness、missing fields、stale fields、source level。
- 回测可以使用历史增强数据，但实时信号只能使用信号时点之前已经可得的数据。

#### 5.2.5 第一版数据最低集

第一版不是只做 K 线，最低集调整为：

- Binance exchange info
- Binance 24h ticker
- Binance 1m/5m/15m/1h K 线
- Binance funding current + history
- Binance open interest current + 本地历史快照
- Binance taker buy/sell from K 线
- 候选级 Binance 20-level orderbook
- 候选级 CoinGlass cross-exchange OI / futures flow / spot flow / market cap

Etherscan 和 liquidation heatmap 可以稍后接，但接口和数据模型必须在 PRD 中预留。

### 5.3 数据存储

- Parquet：历史行情和特征主存储。
- DuckDB：本地分析查询。
- SQLite：实验日志、信号日志、运行状态。

理由：Parquet 适合列式历史数据，DuckDB 适合本地快速聚合，SQLite 适合轻量状态记录。

### 5.4 数据处理

- Polars：批量特征构建和大规模 groupby。
- pandas：和 vectorbt 交互。
- numpy：数值计算。

策略：内部尽量用 Polars，进入 vectorbt 前转换为 pandas DataFrame。

### 5.5 回测

- vectorbt：参数扫描和快速研究工具。
- 自研 event-driven bar-by-bar backtester：最终验收工具。
- 自定义 execution/cost 模块：补齐手续费、滑点、Funding、next-bar entry。

选择 vectorbt 的原因：

- 适合多币种、多参数、信号矩阵化回测。
- 官方定位就是高性能向量化策略研究。
- 适合快速做参数扫描和样本外对比。

vectorbt 的使用边界：

- 用于快速筛参数、筛大方向、做批量对比。
- 不能作为 V4A 最终裁判。
- 不负责最终状态机逻辑验收。

V4A 最终必须用逐 bar 事件驱动回测器复核，因为它是状态机策略，涉及：

- active pump 状态。
- 第一次卖压。
- 支撑跌破。
- next-bar entry。
- trailing stop。
- stop loss。
- max hold。
- 同币去重。
- 订单簿滑点和 Funding 成本。

限制：

- vectorbt 不是事件驱动实盘引擎。
- 不负责真实盘口撮合。
- 不适合直接证明妖币策略可实盘赚钱。
- 订单簿滑点和成交约束必须自己建模。

### 5.6 模型

第一阶段不使用机器学习做主信号。

后续扩展：

- scikit-learn：Logistic Regression、Isolation Forest。
- LightGBM：辅助过滤器，不作为第一版核心。

当前主线是裸 K 策略复现，不把 ML 放在核心链路。

不优先使用深度学习的原因：

- 文章没有明确使用神经网络交易模型。
- 当前目标是复现规则实验和参数搜索，不是训练行情预测器。
- 妖币样本少、非平稳、极端事件占比高，深度模型更容易过拟合。
- 第一阶段最重要的是验证无未来函数、真实成本和 holdout 稳定性。

LLM 的定位：

- 可以作为研究助理和实验调度器。
- 可以总结失败实验、提出新参数组合、生成报告。
- 不直接输出交易信号。
- 不替代回测、验证和成本模型。
- 环境变量统一使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，不绑定单一模型供应商。

### 5.7 Dashboard 和推送

- 第一阶段主入口是 CLI + Markdown/HTML report。
- Pipeline：自研 `pipeline_runner.py` 编排子命令。
- Dashboard 不使用 Streamlit。
- Dashboard 使用正式 Web 前端：Next.js + React + TypeScript + Tailwind CSS + shadcn/ui。
- 表格：TanStack Table。
- 图表：ECharts 或 Recharts；K 线优先 TradingView Lightweight Charts。
- Report API：FastAPI，只读查询 SQLite / DuckDB / Parquet / reports。
- MLflow：可选，用于实验追踪；第一版不强依赖。
- Webhook：可选通知通道，默认不配置 Discord / Telegram，不作为第一版必需能力。

Dashboard 不参与策略验收，不触发实验，不触发 holdout，不修改配置。V4A 验证完成前，不把前端页面作为实验执行入口；第一阶段必须保证命令行、pipeline、配置文件、Parquet/SQLite、CSV trade log、Markdown/HTML report 可用。Web Dashboard 是查看结果的最终常用形态。

## 6. 目录结构

```text
Super-crypto/
  README.md
  pyproject.toml
  justfile
  .env.example

  configs/
    data.yaml
    data_sources.yaml
    enrichment.yaml
    symbols.yaml
    scores.yaml
    cycle.yaml
    splits.yaml
    symbol_splits/
      train.txt
      validation.txt
      holdout.txt
    backtest.yaml
    strategy_v3.yaml
    strategy_v4a.yaml
    strategy_v4b.yaml
    experiment_v3.yaml
    experiment_v4a.yaml
    experiment_v4b.yaml
    pipeline_v4a.yaml
    autoresearch.yaml
    protected_files.yaml
    scanner.yaml

  data/
    raw/
      binance/
        exchange_info/
        klines/
          1m/
          5m/
          15m/
          1h/
        funding/
        open_interest/
        taker_ratio/
        orderbook/
      coinglass/
        tickers/
        futures_flow/
        spot_flow/
        coin_info/
        liquidation/
        liquidation_heatmap/
      etherscan/
        transfers/
        address_labels/
    processed/
      ohlcv/
      derivatives/
      orderbook_features/
      external_enrichment/
      onchain_features/
      cycles/
      scores/
      signals/
      trades/
      train/
      validation/
      holdout/
    cache/

  src/
    super_crypto/
      __init__.py
      cli.py

      common/
        config.py
        logging.py
        time.py
        paths.py
        types.py

      data/
        binance_client.py
        coinglass_client.py
        etherscan_client.py
        ingest_klines.py
        ingest_funding.py
        ingest_open_interest.py
        ingest_orderbook.py
        ingest_coinglass.py
        ingest_onchain.py
        normalize_ohlcv.py
        normalize_derivatives.py
        normalize_external.py
        data_quality.py
        freshness.py

      enrichment/
        request_selector.py
        cache_store.py
        coinglass_enrichment.py
        oi_backfill.py
        quality_flags.py

      features/
        price_features.py
        derivative_features.py
        taker_features.py
        orderbook_features.py
        liquidation_features.py
        onchain_features.py
        feature_matrix.py

      universe/
        binance_futures.py
        symbol_filters.py
        manipulation_score.py

      cycles/
        detect_pump_dump.py
        label_cycles.py
        cycle_stats.py

      signals/
        base.py
        naked_k.py
        v3_abandon_point.py
        v4a_early_short.py
        v4b_confirmed_short.py

      backtest/
        vectorbt_runner.py
        event_backtester.py
        bar_engine.py
        strategy_state.py
        fill_model.py
        execution_costs.py
        position_sizing.py
        exits.py
        metrics.py
        trade_report.py

      validation/
        splits.py
        leakage_checks.py
        robustness.py
        parameter_search.py

      experiments/
        run_experiment.py
        pipeline_runner.py
        pipeline_store.py
        experiment_store.py
        report_builder.py

      reports/
        markdown_report.py
        html_report.py
        report_store.py
        report_server.py

      report_api/
        main.py
        deps.py
        overview.py
        pipeline.py
        experiments.py
        signals.py
        trades.py
        symbols.py
        data_quality.py
        reports.py

      autoresearch/
        agent_loop.py
        hypothesis_generator.py
        experiment_planner.py
        config_mutator.py
        code_patch_guard.py
        result_interpreter.py
        accept_reject_policy.py
        protected_files.py

      realtime/
        scanner.py
        signal_store.py
        webhook.py
        scheduler.py

  apps/
    dashboard/
      package.json
      next.config.ts
      tsconfig.json
      tailwind.config.ts
      src/
        app/
          layout.tsx
          page.tsx
          experiments/
            page.tsx
            [experimentId]/
              page.tsx
          signals/
            page.tsx
            [signalId]/
              page.tsx
          trades/
            page.tsx
          symbols/
            page.tsx
            [symbol]/
              page.tsx
          data-quality/
            page.tsx
          orderbook/
            page.tsx
          reports/
            page.tsx
        components/
          app-shell.tsx
          top-status-bar.tsx
          side-nav.tsx
          metric-card.tsx
          status-badge.tsx
          hash-badge.tsx
          data-quality-badge.tsx
          equity-chart.tsx
          drawdown-chart.tsx
          kline-panel.tsx
          slippage-curve.tsx
          orderbook-depth-panel.tsx
          experiment-table.tsx
          trade-table.tsx
          signal-table.tsx
          symbol-score-table.tsx
          config-viewer.tsx
        lib/
          api.ts
          format.ts
          types.ts
        styles/
          globals.css

  tests/
    test_data_quality.py
    test_enrichment_request_selector.py
    test_coinglass_cache.py
    test_orderbook_slippage.py
    test_cycle_detection.py
    test_no_lookahead.py
    test_manipulation_score_point_in_time.py
    test_support_point_in_time.py
    test_split_manifest.py
    test_holdout_access_guard.py
    test_event_backtester_state_machine.py
    test_cost_model.py
    test_splits.py
    test_signal_v3.py
    test_signal_v4a.py
    test_signal_v4b.py

  reports/
    experiments/
    backtests/
    signals/
    html/
    markdown/

  notebooks/
    exploration_only/
```

规则：

- `notebooks/` 只做探索，不作为生产逻辑来源。
- 所有可复现实验必须能从 `configs/` 和 `src/` 一条命令跑出。
- `data/raw/` 不手工改。
- `data/processed/` 可删除重建。

## 7. 核心数据模型

### 7.1 OHLCV

字段：

- symbol
- interval
- open_time
- close_time
- open
- high
- low
- close
- volume
- quote_volume
- trades
- taker_buy_base_volume
- taker_buy_quote_volume

### 7.2 操纵周期 cycles

字段：

- cycle_id
- symbol
- pump_start_time
- peak_time
- dump_end_time
- pump_return
- dump_return
- total_duration_hours
- pump_duration_hours
- dump_duration_hours
- peak_price
- start_price
- end_price
- cycle_type
- source_config_hash

### 7.3 实时市场快照 market_snapshots

对应全市场低成本扫描路径，每轮扫描一行。

字段：

- symbol
- scan_time
- latest_price
- price_change_24h
- quote_volume_24h
- trades_24h
- funding_pct
- funding_delta_pct
- open_interest_current
- oi_change_1h
- oi_change_6h
- oi_change_24h
- oi_acceleration
- vol_oi_ratio
- taker_buy_sell_ratio
- basis
- annualized_basis_rate
- global_long_short_ratio
- top_long_short_account_ratio
- top_long_short_position_ratio
- alpha_hit
- insight_hit
- data_quality
- missing_fields
- stale_fields
- source_level

### 7.4 候选增强缓存 external_enrichment_cache

对应候选级 CoinGlass / 外部数据增强路径。

字段：

- request_key
- symbol
- source
- data_type：tickers / futures_flow / spot_flow / coin_info / liquidation / heatmap
- raw_payload
- normalized_payload
- status
- fetched_at
- expire_at
- next_retry_at
- lock_until
- http_status
- latency_ms
- error_message
- version

### 7.5 候选增强快照 external_enrichment_snapshots

字段：

- symbol
- snapshot_time
- cross_exchange_oi
- cross_exchange_oi_change_1h
- cross_exchange_oi_change_4h
- cross_exchange_oi_change_24h
- futures_inflow_1h
- futures_outflow_1h
- futures_netflow_1h
- futures_inflow_4h
- futures_outflow_4h
- futures_netflow_4h
- futures_netflow_24h
- spot_inflow_1h
- spot_outflow_1h
- spot_netflow_1h
- spot_netflow_4h
- spot_netflow_24h
- contract_volume_24h
- spot_volume_24h
- market_cap
- circulating_supply
- total_supply
- max_supply
- exchange_breadth
- binance_has_perp
- aggregated_long_short_ratio
- exchange_long_short_ratio
- contract_exchanges
- spot_exchanges
- field_quality
- missing_fields
- stale_fields

### 7.6 订单簿快照 orderbook_snapshots

字段：

- symbol
- snapshot_time
- depth_level
- best_bid
- best_ask
- spread_bps
- bid_depth_usd_20
- ask_depth_usd_20
- bid_depth_usd_1pct
- ask_depth_usd_1pct
- orderbook_imbalance
- estimated_slippage_100_usd
- estimated_slippage_500_usd
- estimated_slippage_1000_usd
- max_trade_size_under_50bps

用途：

- 真实滑点建模。
- 验证文章中“只能开很小仓位”的问题。
- 判断 V4A 信号是否具备可交易深度。

### 7.7 清算和热力图 liquidation_features

字段：

- symbol
- snapshot_time
- long_liquidation_1h
- short_liquidation_1h
- long_liquidation_4h
- short_liquidation_4h
- liquidation_imbalance
- upper_liq_pool_nearby
- lower_liq_pool_nearby
- nearest_upper_liq_price
- nearest_lower_liq_price
- distance_to_upper_liq_pct
- distance_to_lower_liq_pct
- heatmap_source
- heatmap_freshness_sec

用途：

- 研究支撑位、摸顶信号和清算池的关系。
- 验证“上方没有更多空单对手盘，庄就没动力继续拉”的假设。

### 7.8 链上事件 onchain_events

字段：

- chain
- token_address
- symbol
- event_time
- tx_hash
- from_address
- to_address
- from_label
- to_label
- amount_token
- amount_usd
- event_type：whale_transfer / cex_inflow / cex_outflow / team_wallet_move
- exchange
- confidence

用途：

- 识别项目方或鲸鱼向 CEX 转币。
- 验证现货出货迹象。
- 辅助判断操纵周期后期风险。

### 7.9 历史因子统计 factor_stats

字段：

- symbol
- factor_name
- interval
- start_time
- end_time
- sample_count
- coverage_ratio
- mean
- std
- p05
- p25
- p50
- p75
- p95
- data_quality

用途：

- 计算 z-score 和分位数。
- 判断异常 OI、Funding、taker、depth、volume。
- 给 AutoResearch 提供稳定的历史统计输入。

### 7.10 庄币评分 manipulation_scores

字段：

- symbol
- score_time
- lookback_days
- cycle_count
- weighted_cycle_count
- avg_pump_return
- avg_dump_return
- median_duration_hours
- manipulation_score
- score_bucket：ultra_high / high / medium / low
- point_in_time_cutoff
- source_window_start
- source_window_end

约束：

- 某一天的 `manipulation_score` 只能使用该时间点之前的数据。
- 不能用全历史操纵周期给过去时间打分。
- 回测中每一笔交易只能读取 `score_time <= signal_time` 的最新评分。
- 分组分析必须按 point-in-time score 分组，不能按事后全样本评分分组。

### 7.11 信号 signals

字段：

- signal_id
- symbol
- strategy
- signal_time
- side
- entry_time
- entry_reference_price
- stop_loss
- trailing_stop
- confidence
- reason
- params_hash
- is_realtime

### 7.12 交易 trades

字段：

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
- max_adverse_excursion
- max_favorable_excursion

### 7.13 Pipeline 运行 pipeline_runs

字段：

- run_id
- pipeline_name
- mode：research / scanner / final_holdout
- split
- final
- status
- started_at
- finished_at
- config_hash
- split_hash
- data_snapshot_hash
- git_commit_hash
- report_path
- error_message

### 7.14 Pipeline 阶段 pipeline_stages

字段：

- run_id
- stage_name
- status
- started_at
- finished_at
- skipped
- skip_reason
- config_hash
- input_hash
- output_hash
- output_path
- error_message

### 7.15 实验运行 experiment_runs

字段：

- experiment_id
- pipeline_run_id
- strategy
- engine：vectorbt / event_driven
- split
- config_hash
- split_hash
- data_snapshot_hash
- params_hash
- metrics_json
- trade_log_path
- report_path
- accepted
- reject_reason

## 8. 操纵周期识别

### 8.0 数据覆盖要求

本项目的数据目标分三档：

| 数据项 | 文章使用 | MVP 必须 | 候选增强 | 后续研究 |
|---|---|---:|---:|---:|
| Binance K 线 | 是 | 是 | 是 | 是 |
| Binance 24h ticker | 是 | 是 | 是 | 是 |
| Binance exchange info | 是 | 是 | 是 | 是 |
| Funding current/history | 是 | 是 | 是 | 是 |
| Open Interest current/history | 是 | 是 | 是 | 是 |
| OI 1h/6h/24h change | 是 | 是 | 是 | 是 |
| taker buy/sell ratio | 是 | K 线部分覆盖 | 是 | 是 |
| global long-short ratio | 是 | 否 | 是 | 是 |
| top trader long-short ratio | 是 | 否 | 是 | 是 |
| liquidation long/short | 是 | 否 | 可选 | 是 |
| orderbook depth | 是 | 候选级 | 是 | 是 |
| slippage curve | 文章 V4 关键 | 候选级 | 是 | 是 |
| liquidation heatmap | 后续重点 | 否 | 可选 | 是 |
| CoinGlass cross-exchange OI | 是 | 候选级 | 是 | 是 |
| CoinGlass futures/spot flow | 是 | 候选级 | 是 | 是 |
| market cap / supply | 是 | 候选级 | 是 | 是 |
| Etherscan 链上转账 | 是 | 否 | 否 | 是 |
| 项目方 / CEX 地址标签 | 是 | 否 | 否 | 是 |

MVP 的含义不是“只用 K 线”。MVP 主信号仍以裸 K 为核心，但数据层必须从第一版就支持 Funding、OI、候选级订单簿和候选级 CoinGlass 增强，否则无法验证文章中关于滑点、真实开仓成本和衍生品指标无效性的结论。

### 8.1 文章可见定义

文章明确提到：

- Pump + Dump 在 20%-50% 区间内。
- 96 小时以内完成。
- 太高样本太少，太低噪音太大。

具体阈值有隐藏部分，所以实现必须配置化。

### 8.2 第一版检测逻辑

输入：1h 或 15m K 线。  
输出：符合条件的 Pump + Dump 周期。

候选规则：

1. 在 lookback window 内找到局部低点 `pump_start`。
2. 在之后 `max_cycle_hours` 内找到局部高点 `peak`。
3. `peak / pump_start - 1` 落在 `[pump_min, pump_max]`。
4. 在 peak 之后找到回撤低点 `dump_end`。
5. `(peak - dump_end) / peak` 落在 `[dump_min, dump_max]`。
6. `dump_end - pump_start <= 96h`。
7. 周期之间做去重，重叠周期保留幅度更显著或更早触发的一个。

默认参数：

```yaml
pump_min: 0.20
pump_max: 0.50
dump_min: 0.20
dump_max: 0.50
max_cycle_hours: 96
min_gap_between_cycles_hours: 12
```

注意：

- 周期识别用于离线标签，可以用完整历史。
- 策略信号不能用未来 K 线。
- 标签模块和信号模块必须分离。

## 9. 策略复现

### 9.1 V3：弃盘点做空

文章描述：

- 逻辑落在 1H 线。
- 连续两根 1 小时 K 线实体跌破 5%。
- 配 3% 移动止损。
- 后来发现存在 look-ahead bias 和真实成本问题。

实现规则：

1. 使用 1h K 线。
2. 当前和上一根 1h K 线均为实体跌幅超过阈值的阴线。
3. 下一根 K 线开盘做空。
4. 使用 trailing stop。
5. 加入固定止损。
6. 最长持仓时间默认 6h。

默认参数：

```yaml
body_drop_threshold: 0.05
consecutive_bars: 2
trailing_stop: 0.03
stop_loss: 0.03
max_holding_hours: 6
```

V3 主要作为对照组，不作为最终主策略。

### 9.2 V4A：早进，抢第一脚

文章描述：

- 早期入场。
- 不看量，不看振幅。
- 摸顶确认只看卖压瞬时第一次大于买压的信号。
- 跌破支撑位以 1H 收盘价为依据。
- 确认跌破阈值比 V4B 更低。
- 摸顶确认后的搜索范围更短。
- 最终只有 V4A 站住。

可实现近似规则：

1. 第一轮必须全样本运行，不允许先用高操纵评分池硬过滤。
2. 当前处于近期明显 pump 后区域。
3. 用历史 K 线计算 peak candidate，不能用未来高点。
4. 出现第一次卖压强于买压：
   - 当前 1h K 线为阴线。
   - 实体占振幅比例超过阈值。
   - close 低于上一根或若干根关键价位。
5. 用信号时点之前已经存在的支撑位定义进行判断。
6. 1h 收盘价跌破支撑位一定比例后，下一根开盘做空。
7. 使用 trailing stop + stop loss。
8. 中位目标持仓约 1h，最长持仓不超过配置值。

操纵评分的使用方式：

- 第一版不作为 V4A 入场硬条件。
- `manipulation_score` 只作为分组分析字段。
- 必须先比较 high / medium / low score 分组表现。
- 只有证明高分组显著优于低分组后，才能在实时 scanner 中作为过滤器。
- 这样才能区分收益来自 V4A 逻辑，还是来自选币筛选，避免选币过拟合。

支撑位定义必须配置成枚举：

```yaml
support_type:
  - rolling_low
  - rolling_close_low
  - confirmed_pivot_low
  - pump_since_low
```

定义约束：

- `rolling_low`：只使用过去 N 根 K 线最低 low。
- `rolling_close_low`：只使用过去 N 根 K 线最低 close。
- `confirmed_pivot_low`：只使用已经确认的历史 pivot，确认时间必须早于 signal_time。
- `pump_since_low`：只使用 pump context 启动后、signal_time 之前的最低点。
- 所有支撑位必须满足 `support_time <= signal_time`。
- 不允许用未来 peak 反推 support。
- 不允许用 signal_time 之后的 K 线修正 support。

默认参数需要搜索：

```yaml
pump_context_lookback_hours: [12, 24, 48]
min_pump_context_return: [0.15, 0.20, 0.25]
sell_pressure_body_ratio: [0.45, 0.55, 0.65]
support_type: [rolling_low, rolling_close_low, confirmed_pivot_low, pump_since_low]
support_lookback_hours: [6, 12, 24]
support_break_threshold: [0.003, 0.005, 0.008, 0.01]
post_peak_search_hours: [1, 2, 3, 4]
trailing_stop: [0.015, 0.02, 0.03]
stop_loss: [0.01, 0.015, 0.02]
max_holding_hours: [2, 4, 6]
```

### 9.3 V4B：慢一点，等确认

文章描述：

- 等价格已经从 peak 跌下来一段。
- 市场仍剧烈波动，但下跌已经确认。
- 摸顶确认后的搜索范围更长。
- 更稳但更慢，最终不如 V4A。

实现规则：

1. 和 V4A 使用相同候选池。
2. 要求从 peak 已经回撤超过阈值。
3. 要求更多确认 K 线。
4. 支撑跌破阈值更高或确认时间更长。
5. 下一根开盘做空。
6. 同样使用 trailing stop + stop loss。

V4B 用于验证“更确认是否牺牲收益”，不作为第一优先级信号。

## 10. 回测要求

### 10.0 回测分层

回测分两层：

1. `vectorbt` 快速研究层：
   - 用于参数扫描。
   - 用于多币种、多参数组合快速比较。
   - 用于淘汰明显无效参数。
   - 不作为最终收益、回撤、胜率裁判。

2. event-driven bar-by-bar 验收层：
   - 用于最终复核 V4A/V4B。
   - 逐 bar 推进状态机。
   - 显式维护 active pump、first sell pressure、support break、open position、trailing stop、max hold。
   - 逐笔计算 next-bar entry、订单簿滑点、Funding、手续费、同币去重。
   - 最终报告以 event-driven 结果为准。

验收规则：

- vectorbt 发现的候选参数必须经过 event-driven 复核。
- event-driven 结果显著差于 vectorbt 时，以 event-driven 为准。
- 两者差异必须输出 diff report，说明差异来自入场时点、止损、滑点、状态去重还是持仓规则。

### 10.1 成交规则

所有策略必须满足：

- 信号在 K 线收盘后生成。
- 入场只能发生在下一根 K 线。
- 不允许用当前 K 线 close 当作已成交价格。
- 不允许使用未来 peak、未来 support、未来最低点。

### 10.2 成本模型

第一版必须同时支持固定滑点压力测试和候选级订单簿滑点回放：

```yaml
fee_rate: 0.0005
base_slippage: 0.001
small_cap_slippage: 0.003
extreme_slippage: 0.01
funding_cost_enabled: true
orderbook_slippage_enabled: true
orderbook_depth_level: 20
max_allowed_slippage: 0.02
```

固定滑点用于快速参数搜索；订单簿滑点用于验证策略是否具备真实可交易性。

- 按成交额和 24h quote volume 动态估算滑点。
- 加入 Binance funding rate 历史。
- 候选级匹配 Binance 20-level orderbook depth。
- 估算不同名义金额下的 market impact。
- 输出最大可开仓规模。

### 10.3 仓位管理

默认规则：

- 单笔固定风险。
- 同一 symbol 同时最多一笔仓位。
- 多币同时触发时按 score 排序。
- 每轮最多开仓 N 个 symbol。
- 不允许无限加仓。

### 10.4 指标

必须输出：

- net return
- Sharpe
- Sortino
- max drawdown
- profit factor
- win rate
- avg win
- avg loss
- trade count
- median holding time
- fee / pnl ratio
- slippage / pnl ratio
- MAE
- MFE
- 分币种表现
- 分月份表现
- 去掉收益最高 5 笔后的表现

## 11. 验证方案

这里的 train 不是深度学习训练集，而是参数搜索区：

- train：参数搜索区。
- validation：策略选择区。
- holdout：最终样本外验收区。

V4A 规则策略的流程是：train 上搜索参数，validation 上选参数，最后只在 holdout 上跑一次。

### 11.1 时间切分

示例：

```yaml
train:
  start: 2025-03-01
  end: 2025-09-30
validation:
  start: 2025-10-05
  end: 2026-02-28
holdout:
  start: 2026-03-05
  end: 2026-06-28
purge_gap_days: 5
```

实际日期按可下载数据调整。

要求：

- 时间切分必须写入 `configs/splits.yaml`。
- purge gap 至少覆盖最长 rolling lookback、最长持仓时间、操纵周期标签窗口。
- 每次实验必须记录 time split hash。

### 11.2 币种切分

至少保留一组 symbol holdout：

- train symbols：用于参数搜索。
- validation symbols：用于策略选择。
- holdout symbols：最终只跑一次。

推荐配置：

```yaml
symbol_split:
  mode: fixed_manifest
  seed: 42
  train_ratio: 0.70
  validation_ratio: 0.15
  holdout_ratio: 0.15
  train_symbols_path: configs/symbol_splits/train.txt
  validation_symbols_path: configs/symbol_splits/validation.txt
  holdout_symbols_path: configs/symbol_splits/holdout.txt
```

要求：

- symbol split 生成后必须固化为 manifest 文件。
- 每次实验必须记录 symbol split hash。
- 不允许根据策略结果手工替换 holdout symbols。
- 新增 symbol 时必须重新生成 split version，不能静默改旧 manifest。

### 11.3 三类 holdout

最终必须报告三类结果：

1. 时间 holdout：同一批币，未来时间。
2. 币种 holdout：同一时间区间，未见过的币。
3. 时间 + 币种双 holdout：未来时间 + 未见过的币。

第三类是最严格结果，优先级最高。

### 11.4 Holdout 物理隔离

holdout 不只是逻辑参数，必须物理隔离：

```text
data/processed/train/
data/processed/validation/
data/processed/holdout/
```

`configs/splits.yaml` 必须包含：

```yaml
holdout_policy:
  allow_parameter_search: false
  allow_agent_access: false
  max_manual_runs: 1
  require_final_flag: true
  require_clean_experiment_log: true
```

约束：

- 参数搜索脚本不能读取 `data/processed/holdout/`。
- AutoResearch agent 不能读取 holdout path。
- `--split holdout` 必须同时带 `--final`。
- holdout 运行必须写入审计日志。
- holdout 跑完后，不允许根据 holdout 结果继续改参数再复跑。

### 11.5 无未来函数检查

必须实现测试：

- signal timestamp 之后的数据不能参与 signal。
- support 只能由历史 K 线计算。
- peak candidate 只能是当前已知 rolling high。
- manipulation_score 只能使用 signal_time 之前的数据。
- point-in-time score 不能由全历史 cycles 反推。
- support_time 必须小于等于 signal_time。
- confirmed pivot 必须在 signal_time 之前完成确认。
- 所有 entry 都是 next-bar。
- 所有 feature timestamp <= decision timestamp。
- 禁止在 `signals/` 中使用负 shift。
- vectorbt 结果不能作为最终验收结果；V4A 必须通过 event-driven bar backtester 复核。

### 11.6 参数搜索约束

- 参数只能在 train + validation 上搜索。
- holdout 不能反复查看。
- 每次实验必须记录 config hash。
- 每次实验必须记录 split hash。
- 每次实验必须记录 data snapshot hash。
- 每次实验必须保存交易明细。
- validation 提升但 trade count 过少的实验不接受。

## 12. Pipeline 编排层

### 12.1 定位

Pipeline 是日常研究主入口，负责把底层子命令串起来。子命令用于 debug，pipeline 用于日常稳定执行。

### 12.2 配置示例

`configs/pipeline_v4a.yaml`：

```yaml
name: v4a_research_pipeline

data_config: configs/data.yaml
splits_config: configs/splits.yaml
cycle_config: configs/cycle.yaml
scores_config: configs/scores.yaml
enrichment_config: configs/enrichment.yaml
experiment_config: configs/experiment_v4a.yaml

stages:
  ingest:
    enabled: true
    skip_if_fresh: true
    freshness_hours: 6

  build_splits:
    enabled: true
    skip_if_exists: true

  detect_cycles:
    enabled: true
    rebuild: false

  score_symbols:
    enabled: true
    point_in_time: true

  enrich:
    enabled: true
    candidate_only: true
    skip_if_fresh: true
    freshness_minutes: 15

  run_experiment:
    enabled: true
    engine: event_driven
    split: train_validation

  report:
    enabled: true
    formats:
      - markdown
      - html

guards:
  forbid_holdout_without_final: true
  forbid_agent_holdout_access: true
  require_clean_git: false
  require_config_hash: true
  require_split_hash: true
  require_data_snapshot_hash: true
```

### 12.3 Pipeline Runner

`pipeline_runner.py` 负责：

- 读取 `pipeline_v4a.yaml`。
- 检查 stage enabled 状态。
- 检查缓存 freshness。
- 按顺序执行阶段。
- 支持 `--from` 从某阶段开始。
- 支持 `--only` 只跑某阶段。
- 支持 `--resume` 从失败阶段继续。
- 写入 `pipeline_runs` 和 `pipeline_stages`。
- 输出 report path。
- 执行 holdout guard。

### 12.4 Report Serve

`super-crypto report serve` 是本地 Web Dashboard 的统一启动入口：

```bash
super-crypto report serve --host 127.0.0.1 --port 8000
```

职责：

- 启动 FastAPI report API。
- 启动或代理 Next.js Dashboard。
- 读取 SQLite / DuckDB / Parquet / reports。
- 只提供只读查询。
- 禁止执行 pipeline。
- 禁止触发 holdout。
- 禁止修改配置。

### 12.5 常用命令别名

可以提供 `justfile`：

```make
research:
    python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation

holdout:
    python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split holdout --final

resume:
    python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --resume

scan:
    python -m super_crypto.realtime.scanner --config configs/scanner.yaml

dashboard:
    super-crypto report serve --host 127.0.0.1 --port 8000
```

日常使用优先：

```bash
just research
just resume
just holdout
```

## 13. AutoResearch 自动实验层

### 13.1 定位

AutoResearch 不是第一阶段核心交易模型，也不是深度学习模型。它的职责是自动化研究流程：

```text
读取历史实验结果
  -> 提出新假设
  -> 生成实验计划
  -> 修改允许范围内的配置或特征
  -> 运行 validation 实验
  -> 解析指标和交易明细
  -> 判断保留或拒绝
  -> 写入实验日志
  -> 继续下一轮
```

当前 PRD 的 Phase 0 到 Phase 10 是 AutoResearch 的前置工程。只有当数据、候选增强、周期识别、V4A 回测、订单簿成本模型、validation、pipeline、report 和实验日志稳定后，才接入 agent loop。

### 13.2 核心模块

- `agent_loop.py`：主循环，负责调度每轮实验。
- `hypothesis_generator.py`：根据历史实验提出新假设。
- `experiment_planner.py`：把假设转成可执行实验计划。
- `config_mutator.py`：只修改允许范围内的 YAML 参数。
- `code_patch_guard.py`：检查代码改动是否越权。
- `result_interpreter.py`：解析指标、交易明细和失败原因。
- `accept_reject_policy.py`：根据规则决定保留或拒绝实验。
- `protected_files.py`：读取保护文件规则。

### 13.3 输入和输出

输入：

- 历史实验日志。
- 最近 N 次失败实验。
- 当前 best validation 结果。
- 可修改参数空间。
- 保护文件列表。

输出：

- 新实验配置。
- 实验假设说明。
- 实验指标。
- 保留/拒绝原因。
- diff 摘要。
- 下一步建议。

### 13.4 保护边界

agent 默认只允许修改：

- `configs/strategy_*.yaml`
- `configs/experiment_*.yaml`
- `configs/cycle.yaml` 中明确开放的参数
- 后续经过允许的 `src/super_crypto/signals/experimental/`

agent 禁止修改：

- `configs/splits.yaml`
- `configs/backtest.yaml` 中的成本下限
- `src/super_crypto/backtest/execution_costs.py`
- `src/super_crypto/validation/leakage_checks.py`
- `src/super_crypto/validation/splits.py`
- `data/raw/`
- `data/processed/holdout/`

### 13.5 接受和拒绝规则

实验只有同时满足以下条件才可保留：

- validation net return 提升。
- max drawdown 不恶化到阈值外。
- trade count 达到最低要求。
- fee/slippage 占利润比例不过高。
- 分币种结果不是只靠单一币种。
- 去掉收益最高 5 笔后仍不过度崩塌。
- no-lookahead 测试通过。

直接拒绝：

- 读取 holdout。
- 降低手续费、滑点、Funding 成本。
- 删除亏损交易。
- 使用未来 K 线。
- 使用 symbol 名称硬编码特征。
- 只优化 Sharpe 或 F1，忽略交易成本和回撤。

### 13.6 AutoResearch 和当前方案的关系

当前方案是可复现实验框架，不是完整 AutoResearch。完整 AutoResearch 是在该框架之上增加自动假设生成、自动实验计划、自动运行、自动解释和保留/拒绝机制。

正确顺序：

1. 先完成数据 -> 周期识别 -> V4A 回测 -> validation -> trade log。
2. 固定 split、成本模型和无未来函数测试。
3. 人工跑至少 20 次实验，形成基线日志。
4. 再接入 AutoResearch agent，只允许跑 validation。
5. 最后由人工决定是否跑 final holdout。

## 14. 实时信号系统

### 14.1 Scanner

功能：

- 每 60 秒拉取最新 K 线。
- 更新目标币裸 K 状态。
- 计算操纵评分。
- 检查 V4A/V4B 条件。
- 生成信号。
- 写入 SQLite。
- 可选推送 webhook；默认只写 SQLite 并展示到 Dashboard。

### 14.2 Dashboard

Dashboard 是本地只读量化研究终端，按 `dashboard设计.md` 实现。它不是 Streamlit，不提供实验执行、配置修改或 holdout 触发入口。

第一版页面：

- Overview：系统健康、pipeline 状态、scanner 状态、核心 KPI、数据告警。
- Experiments：实验列表、config hash、split hash、data snapshot hash、状态、指标排序。
- Backtest Detail：event-driven 主指标、vectorbt diff、权益曲线、回撤曲线、交易明细、分币种、分月份、鲁棒性。
- Signals：实时 V4A/V4B 信号、原因标签、confidence、订单簿滑点、paper trade PnL。
- Trades：回测交易和 paper trade，展示 fee/slippage/funding 后净收益。
- Symbols：操纵评分、score point-in-time cutoff、OI/Funding、数据完整性、最新信号。
- Symbol Detail：K 线、Pump/Dump 标注、V4A entry/exit、support line、trailing stop、订单簿滑点。
- Data Quality：Binance、CoinGlass、订单簿、缓存、missing/stale/failed source。
- Orderbook：深度、spread、imbalance、slippage curve、最大可开仓规模。
- Reports：Markdown/HTML/CSV/diff/robustness/data coverage report。

只读 API：

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

所有 API 返回必须包含：

- `generated_at`
- `source`
- `freshness_sec`
- `data_quality`
- `missing_fields`
- `stale_fields`

实验接口必须包含：

- `config_hash`
- `split_hash`
- `data_snapshot_hash`
- `git_commit_hash`
- `report_path`

信号接口必须包含：

- `signal_time`
- `decision_time`
- `data_cutoff_time`
- `entry_reference`
- `reason`

### 14.3 可选 Webhook

Webhook 不是第一版必需项。默认 `configs/scanner.yaml` 使用 `webhooks: {}`，scanner 只写 SQLite 和 Dashboard 可读数据；如果后续需要 Discord、Telegram 或企业 IM，再显式配置 URL。

推送内容：

```json
{
  "symbol": "MMTUSDT",
  "strategy": "V4A",
  "side": "SHORT",
  "signal_time": "2026-06-28T12:00:00Z",
  "entry": "next_1h_open",
  "stop_loss": 0.015,
  "trailing_stop": 0.02,
  "confidence": 0.74,
  "manipulation_score_bucket": "high",
  "reason": [
    "pump_context_detected",
    "first_sell_pressure",
    "support_break"
  ]
}
```

## 15. 实现过程

### Phase 0：项目骨架

交付：

- `pyproject.toml`
- `configs/`
- `src/super_crypto/`
- 日志系统
- 配置加载
- CLI 入口
- pytest 基础测试

验收：

- `python -m super_crypto.cli --help` 可运行。
- `pytest` 可运行。

### Phase 1：Binance 基础市场数据

交付：

- 合约币种列表下载。
- K 线历史下载。
- 24h ticker 下载。
- funding current/history 下载。
- open interest current 快照和本地历史锚点。
- Parquet 存储。
- 数据质量检查。

验收：

- 能下载指定 symbols 的 1m/5m/15m/1h K 线。
- 能生成全市场 `market_snapshots`。
- 能计算 funding delta、OI 1h/6h/24h change、OI acceleration。
- 能检测缺口、重复、时区错误。

### Phase 2：候选增强和订单簿成本数据

交付：

- 候选选择器。
- CoinGlass 增强缓存。
- cross-exchange OI / futures flow / spot flow / market cap 归一化。
- 候选级 Binance 20-level orderbook 快照。
- orderbook imbalance 和 slippage curve。
- external enrichment freshness / missing / stale 标记。

验收：

- 不把 CoinGlass 作为全市场每轮扫描源。
- 能按候选池拉取并缓存 CoinGlass 数据。
- 能估算 100/500/1000 USDT 名义金额的滑点。
- 能生成候选币可交易深度报告。

### Phase 3：操纵周期识别

交付：

- Pump + Dump 周期检测。
- 周期去重。
- 周期统计报告。
- 参数配置。

验收：

- 能对单个 symbol 输出 cycles。
- 能对全市场输出 cycles。
- 能复现 20%-50%、96h 以内的周期定义。

### Phase 4：操纵评分

交付：

- 按过去 N 天周期频率打分。
- 支持时间衰减。
- 融合 OI、Funding、成交量、候选增强覆盖度。
- 输出 ultra_high / high / medium / low。

验收：

- 能生成每日 score 表。
- 能筛出高操纵池。
- 每个 score 都包含 point-in-time cutoff。
- `test_manipulation_score_point_in_time` 通过。

### Phase 5：策略 V3/V4A/V4B

交付：

- V3 信号模块。
- V4A 近似信号模块。
- V4B 近似信号模块。
- 所有信号 next-bar entry。

验收：

- 每个策略有独立测试。
- 无未来函数测试通过。

### Phase 6：参数扫描和事件驱动回测

交付：

- vectorbt entries/exits 矩阵生成。
- event-driven bar-by-bar backtester。
- V4A 状态机。
- 手续费、滑点、Funding 成本。
- 基于订单簿快照的候选级真实滑点回放。
- trailing stop / stop loss。
- vectorbt vs event-driven diff report。
- trade report。

验收：

- 能用 vectorbt 跑多币多参数快筛。
- 能用 event-driven backtester 跑单币和多币最终复核。
- 输出完整指标和交易明细。
- 最终验收指标来自 event-driven backtester。

### Phase 7：验证和参数搜索

交付：

- train / validation / holdout split。
- fixed symbol split manifest。
- split hash。
- data snapshot hash。
- purged split。
- holdout 物理隔离。
- holdout access guard。
- 参数网格搜索。
- robustness report。

验收：

- holdout 数据不会被参数搜索读取。
- `--split holdout` 没有 `--final` 时必须失败。
- AutoResearch agent 不能读取 holdout path。
- split manifest 固化后不可静默变化。
- 每次实验结果可追踪 config hash。
- 每次实验结果可追踪 split hash 和 data snapshot hash。

### Phase 8：Pipeline 和 Report Server

交付：

- `pipeline_runner.py`
- `pipeline_store.py`
- `configs/pipeline_v4a.yaml`
- `pipeline_runs` / `pipeline_stages` 表。
- `--from` / `--only` / `--resume`。
- Markdown / HTML report。
- `super-crypto report serve` 本地 Web Dashboard。
- `justfile` 常用命令。

验收：

- `python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation` 能跑完整流程。
- `--resume` 能从失败阶段继续。
- `--only score_symbols` 能只跑单阶段。
- `--split holdout` 没有 `--final` 时失败。
- report server 能打开实验列表、交易明细、曲线、分组表现和参数敏感性。

### Phase 9：实时 Scanner

交付：

- 每 60 秒扫描。
- 全市场低成本快照。
- 候选级深扫。
- 信号落库。
- 可选 Webhook 推送。
- paper trade 记录。

验收：

- scanner 可持续运行 24 小时。
- 断网或 API 限流后可恢复。
- 重复信号会去重。

### Phase 10：Dashboard

交付：

- Next.js + React + TypeScript Dashboard。
- Tailwind CSS + shadcn/ui 暗色量化终端设计系统。
- FastAPI report API。
- AppShell、TopStatusBar、SideNav。
- Overview、Experiments、Backtest Detail、Signals、Trades、Symbols、Data Quality、Orderbook、Reports 页面。
- TanStack Table 表格组件。
- Equity / Drawdown / Kline / Slippage / Orderbook 图表。
- 只读配置查看器和 hash 展示。

验收：

- `super-crypto report serve --host 127.0.0.1 --port 8000` 可打开 Dashboard。
- 页面只读，没有执行实验、修改配置、触发 holdout 的入口。
- 能查看实验列表、交易明细、曲线、分组表现、参数敏感性。
- 能区分 event-driven 主指标和 vectorbt 对照指标。
- 能查看实时信号、历史 paper trade、CoinGlass cache、orderbook depth。
- 长 hash 不撑爆布局，表格高密度但可读。

### Phase 11：AutoResearch agent

交付：

- `agent_loop.py`
- `hypothesis_generator.py`
- `experiment_planner.py`
- `config_mutator.py`
- `code_patch_guard.py`
- `result_interpreter.py`
- `accept_reject_policy.py`
- `protected_files.yaml`

验收：

- 能读取最近实验日志并提出新假设。
- 能生成新的实验配置。
- 能自动运行 validation。
- 能按规则保留或拒绝实验。
- 不能读取 holdout。
- 不能修改受保护文件。

### Phase 12：扩展研究

后续加入：

- liquidation heatmap
- Etherscan 链上转账
- LightGBM 过滤器

加入顺序：

1. 先作为分析字段，不进策略。
2. 再作为过滤器。
3. 最后才允许进入模型。

## 16. 风险和对策

### 16.1 文章阈值隐藏

风险：无法精确复现 V4A/V4B。  
对策：配置化参数搜索，明确标注为近似复现。

### 16.2 未来函数

风险：支撑位、peak、跌破确认容易偷看未来。  
对策：标签和信号分离，强制 no-lookahead 测试。

### 16.3 滑点低估

风险：妖币盘口薄，回测收益虚高。  
对策：第一版同时使用保守固定滑点和候选级订单簿深度回放；没有订单簿快照的交易必须标记为低可信。

### 16.4 样本过少

风险：胜率 100% 可能只是样本太小。  
对策：报告必须展示 trade count、置信区间、去极值表现。

### 16.5 过拟合

风险：参数搜索把 validation 调穿。  
对策：保留 final holdout，只允许最后跑一次。

### 16.6 实时和回测不一致

风险：回测用完整 K 线，实时 K 线未收盘。  
对策：只在 K 线收盘后确认信号，实时模块用 closed candle。

### 16.7 外部增强数据不稳定

风险：CoinGlass 额度、缓存、字段变化、接口失败会导致候选增强缺失。  
对策：CoinGlass 只做候选级缓存增强，不作为全市场扫描主源；所有增强字段必须记录 freshness、missing、stale，缺失时降低 confidence 而不是中断 scanner。

### 16.8 数据覆盖率导致误判

风险：某些币缺 OI、Funding、taker、depth，评分可能被误判。  
对策：评分必须包含 data completeness、source reliability、critical missing fields；Alpha/Insight 或单一来源信号不得直接触发高置信推送。

### 16.9 Holdout 污染

风险：反复查看 holdout 后继续改参数，会把 holdout 变成 validation。  
对策：holdout 物理隔离；参数搜索和 agent 禁止读取 holdout；`--split holdout` 必须配 `--final`；每次 holdout 运行写审计日志并限制手动运行次数。

## 17. 第一版验收标准

第一版完成后，应满足：

1. 能下载 Binance 合约 K 线、24h ticker、Funding、OI。
2. 能生成全市场 `market_snapshots`，包含 OI 变化、Funding delta、数据质量字段。
3. 能对候选币拉取 CoinGlass 增强和 Binance 订单簿深度。
4. 能估算候选币真实滑点和最大可开仓规模。
5. 能识别 Pump + Dump 操纵周期。
6. 能生成操纵评分。
7. 能跑 V3/V4A/V4B 回测。
8. 能输出 train / validation / holdout 指标。
9. 能证明信号模块没有未来函数。
10. 能通过 CLI 跑完整 train/validation 实验和 final holdout。
11. 能通过 pipeline 一条命令跑完整 train/validation 流程。
12. 能支持 pipeline `--from` / `--only` / `--resume`。
13. 能输出 Markdown/HTML report、CSV trade log、SQLite 实验日志。
14. 能通过 `super-crypto report serve` 打开本地 Web Dashboard。
15. 能运行 scanner 并推送 V4A 类信号。
16. 能保留完整实验日志，为后续 AutoResearch agent 使用。

## 18. 推荐优先级

最高优先级：

1. Binance 基础市场数据：K 线、24h ticker、Funding、OI。
2. 候选级 CoinGlass 增强和订单簿深度。
3. 操纵周期识别。
4. V4A 近似复现。
5. 无未来函数测试。
6. 真实成本模型。
7. Pipeline 一键执行和报告输出。

第二优先级：

1. V3/V4B 对照。
2. 操纵评分动态化。
3. taker / long-short / OI / Funding 因子归因。
4. 本地 Web Dashboard。
5. 可选 Webhook 通知。

第三优先级：

1. 清算热力图。
2. Etherscan 链上转账和地址标签。
3. LightGBM 过滤器。
4. Agent 自动实验。

## 19. 一句话总结

本项目第一阶段不是做全能交易机器人，而是高质量复刻文章实验：用 Binance 基础市场数据和候选级增强数据识别操纵周期、筛选高操纵币、复现 V4A 暴涨回撤早期做空信号，并用订单簿成本、next-bar 成交和 holdout 验证把回测水分挤掉。
