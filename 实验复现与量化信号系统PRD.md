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

3. 建立信号系统：
   - 实时扫描目标币。
   - 触发 V4A 类信号。
   - 输出 entry、stop、trailing stop、confidence、reason。
   - 推送到 Dashboard 和 Webhook。

### 2.2 非目标

第一阶段不做：

- 自动实盘下单。
- 高频撮合级回测。
- 本地训练 LLM。
- 深度学习模型。
- 直接复刻文章隐藏的具体阈值。
- 宣称策略可稳定盈利。

文章隐藏了 V4A/V4B 的关键阈值，所以本项目只能通过参数搜索复原近似版本，不能把猜测写成确定事实。

## 3. 用户场景

### 3.1 研究者场景

用户希望选择一批 Binance 合约币，运行完整实验：

```bash
python -m super_crypto.experiments.run_experiment --config configs/experiment_v4a.yaml
```

系统输出：

- 操纵周期列表。
- 庄币评分表。
- 策略交易明细。
- 回测指标。
- holdout 结果。
- 参数敏感性分析。

### 3.2 实时扫描场景

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

### 3.3 扩展研究场景

用户可以新增一个特征源，比如 Funding：

1. 写入数据采集模块。
2. 写入特征构建模块。
3. 在实验配置中打开该特征。
4. 重新运行 validation。
5. 只有 validation 稳定后，才允许最后跑一次 holdout。

## 4. 总体架构

系统分为七层：

1. 数据层：采集和存储 Binance K 线，后续扩展 CoinGlass、Etherscan。
2. 标的层：生成币种池，筛选 Binance 合约币、新合约币、老币。
3. 标签层：识别 Pump + Dump 操纵周期。
4. 策略层：实现 V3、V4A、V4B 和后续策略。
5. 回测层：用 vectorbt 做研究回测，自定义成本和风控。
6. 验证层：时间切分、币种切分、purged split、无未来函数检查。
7. 信号层：实时 scanner、Dashboard、Webhook。

数据流：

```text
Binance API
  -> raw parquet
  -> normalized OHLCV
  -> cycle labels
  -> manipulation score
  -> strategy signals
  -> vectorbt backtest
  -> reports / dashboard / webhook
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

- Binance Futures API：第一阶段主数据源。
- CCXT：可选，用于统一交易所接口，但 Binance 专有字段优先直接调 Binance API。
- aiohttp / httpx：异步请求和限速控制。

第一阶段只强制采集：

- 1m K 线
- 5m K 线
- 15m K 线
- 1h K 线
- exchange info
- futures symbol 上线状态

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

- vectorbt：第一阶段研究回测主引擎。
- 自定义 execution/cost 模块：补齐手续费、滑点、Funding、next-bar entry。

选择 vectorbt 的原因：

- 适合多币种、多参数、信号矩阵化回测。
- 官方定位就是高性能向量化策略研究。
- 适合快速做参数扫描和样本外对比。

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

### 5.7 Dashboard 和推送

- Streamlit：第一阶段本地研究 Dashboard。
- Discord / Telegram Webhook：信号推送。
- FastAPI：后续如果需要服务化，再加。

第一阶段不做复杂前端，重点是研究结果可信。

## 6. 目录结构

```text
Super-crypto/
  README.md
  pyproject.toml
  .env.example

  configs/
    data.yaml
    symbols.yaml
    cycle.yaml
    splits.yaml
    backtest.yaml
    strategy_v3.yaml
    strategy_v4a.yaml
    strategy_v4b.yaml
    experiment_v3.yaml
    experiment_v4a.yaml
    experiment_v4b.yaml
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
      coinglass/
      etherscan/
    processed/
      ohlcv/
      cycles/
      scores/
      signals/
      trades/
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
        ingest_klines.py
        normalize_ohlcv.py
        data_quality.py

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
        experiment_store.py
        report_builder.py

      realtime/
        scanner.py
        signal_store.py
        webhook.py
        scheduler.py

      dashboard/
        app.py
        pages/
          overview.py
          symbols.py
          signals.py
          experiments.py

  tests/
    test_cycle_detection.py
    test_no_lookahead.py
    test_cost_model.py
    test_splits.py
    test_signal_v3.py
    test_signal_v4a.py
    test_signal_v4b.py

  reports/
    experiments/
    backtests/
    signals/

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

### 7.3 庄币评分 manipulation_scores

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

### 7.4 信号 signals

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

### 7.5 交易 trades

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

## 8. 操纵周期识别

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

1. 标的必须属于高操纵评分池。
2. 当前处于近期明显 pump 后区域。
3. 用历史 K 线计算 peak candidate，不能用未来高点。
4. 出现第一次卖压强于买压：
   - 当前 1h K 线为阴线。
   - 实体占振幅比例超过阈值。
   - close 低于上一根或若干根关键价位。
5. 用 peak 前已经存在的 swing low / rolling low 定义支撑位。
6. 1h 收盘价跌破支撑位一定比例后，下一根开盘做空。
7. 使用 trailing stop + stop loss。
8. 中位目标持仓约 1h，最长持仓不超过配置值。

默认参数需要搜索：

```yaml
pump_context_lookback_hours: [12, 24, 48]
min_pump_context_return: [0.15, 0.20, 0.25]
sell_pressure_body_ratio: [0.45, 0.55, 0.65]
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

### 10.1 成交规则

所有策略必须满足：

- 信号在 K 线收盘后生成。
- 入场只能发生在下一根 K 线。
- 不允许用当前 K 线 close 当作已成交价格。
- 不允许使用未来 peak、未来 support、未来最低点。

### 10.2 成本模型

第一版：

```yaml
fee_rate: 0.0005
base_slippage: 0.001
small_cap_slippage: 0.003
extreme_slippage: 0.01
funding_cost_enabled: true
```

第二版：

- 按成交额和 24h quote volume 动态估算滑点。
- 加入 Binance funding rate 历史。
- 后续加入订单簿深度。

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

### 11.2 币种切分

至少保留一组 symbol holdout：

- train symbols：用于参数搜索。
- validation symbols：用于策略选择。
- holdout symbols：最终只跑一次。

### 11.3 无未来函数检查

必须实现测试：

- signal timestamp 之后的数据不能参与 signal。
- support 只能由历史 K 线计算。
- peak candidate 只能是当前已知 rolling high。
- 所有 entry 都是 next-bar。
- 所有 feature timestamp <= decision timestamp。
- 禁止在 `signals/` 中使用负 shift。

### 11.4 参数搜索约束

- 参数只能在 train + validation 上搜索。
- holdout 不能反复查看。
- 每次实验必须记录 config hash。
- 每次实验必须保存交易明细。
- validation 提升但 trade count 过少的实验不接受。

## 12. 实时信号系统

### 12.1 Scanner

功能：

- 每 60 秒拉取最新 K 线。
- 更新目标币裸 K 状态。
- 计算操纵评分。
- 检查 V4A/V4B 条件。
- 生成信号。
- 写入 SQLite。
- 推送 webhook。

### 12.2 Dashboard

第一版页面：

- Overview：今日信号、策略表现、运行状态。
- Symbols：操纵评分排行。
- Signals：实时信号列表。
- Experiments：历史实验结果。
- Trades：paper trade 结果。

### 12.3 Webhook

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
  "reason": [
    "high_manipulation_score",
    "pump_context_detected",
    "first_sell_pressure",
    "support_break"
  ]
}
```

## 13. 实现过程

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

### Phase 1：Binance K 线数据

交付：

- 合约币种列表下载。
- K 线历史下载。
- Parquet 存储。
- 数据质量检查。

验收：

- 能下载指定 symbols 的 1m/5m/15m/1h K 线。
- 能检测缺口、重复、时区错误。

### Phase 2：操纵周期识别

交付：

- Pump + Dump 周期检测。
- 周期去重。
- 周期统计报告。
- 参数配置。

验收：

- 能对单个 symbol 输出 cycles。
- 能对全市场输出 cycles。
- 能复现 20%-50%、96h 以内的周期定义。

### Phase 3：操纵评分

交付：

- 按过去 N 天周期频率打分。
- 支持时间衰减。
- 输出 ultra_high / high / medium / low。

验收：

- 能生成每日 score 表。
- 能筛出高操纵池。

### Phase 4：策略 V3/V4A/V4B

交付：

- V3 信号模块。
- V4A 近似信号模块。
- V4B 近似信号模块。
- 所有信号 next-bar entry。

验收：

- 每个策略有独立测试。
- 无未来函数测试通过。

### Phase 5：vectorbt 回测

交付：

- entries/exits 矩阵生成。
- 手续费、滑点、Funding 成本。
- trailing stop / stop loss。
- trade report。

验收：

- 能跑单币回测。
- 能跑多币回测。
- 输出完整指标和交易明细。

### Phase 6：验证和参数搜索

交付：

- train / validation / holdout split。
- purged split。
- 参数网格搜索。
- robustness report。

验收：

- holdout 数据不会被参数搜索读取。
- 每次实验结果可追踪 config hash。

### Phase 7：实时 Scanner

交付：

- 每 60 秒扫描。
- 信号落库。
- Webhook 推送。
- paper trade 记录。

验收：

- scanner 可持续运行 24 小时。
- 断网或 API 限流后可恢复。
- 重复信号会去重。

### Phase 8：Dashboard

交付：

- Streamlit Dashboard。
- 展示信号、评分、实验、paper trade。

验收：

- 本地可打开 Dashboard。
- 能查看实时信号和历史实验。

### Phase 9：扩展研究

后续加入：

- Funding Rate
- OI
- liquidation
- taker buy/sell ratio
- orderbook depth
- liquidation heatmap
- Etherscan 链上转账
- LightGBM 过滤器
- AutoResearch agent

加入顺序：

1. 先作为分析字段，不进策略。
2. 再作为过滤器。
3. 最后才允许进入模型。

## 14. 风险和对策

### 14.1 文章阈值隐藏

风险：无法精确复现 V4A/V4B。  
对策：配置化参数搜索，明确标注为近似复现。

### 14.2 未来函数

风险：支撑位、peak、跌破确认容易偷看未来。  
对策：标签和信号分离，强制 no-lookahead 测试。

### 14.3 滑点低估

风险：妖币盘口薄，回测收益虚高。  
对策：第一版用保守滑点，第二版加入订单簿深度。

### 14.4 样本过少

风险：胜率 100% 可能只是样本太小。  
对策：报告必须展示 trade count、置信区间、去极值表现。

### 14.5 过拟合

风险：参数搜索把 validation 调穿。  
对策：保留 final holdout，只允许最后跑一次。

### 14.6 实时和回测不一致

风险：回测用完整 K 线，实时 K 线未收盘。  
对策：只在 K 线收盘后确认信号，实时模块用 closed candle。

## 15. 第一版验收标准

第一版完成后，应满足：

1. 能下载 Binance 合约 K 线。
2. 能识别 Pump + Dump 操纵周期。
3. 能生成操纵评分。
4. 能跑 V3/V4A/V4B 回测。
5. 能输出 train / validation / holdout 指标。
6. 能证明信号模块没有未来函数。
7. 能运行 scanner 并推送 V4A 类信号。
8. 能打开 Dashboard 查看信号。

## 16. 推荐优先级

最高优先级：

1. Binance K 线数据。
2. 操纵周期识别。
3. V4A 近似复现。
4. 无未来函数测试。
5. 成本模型。

第二优先级：

1. V3/V4B 对照。
2. 操纵评分动态化。
3. Dashboard。
4. Webhook。

第三优先级：

1. OI / Funding。
2. 订单簿深度。
3. 清算热力图。
4. LightGBM 过滤器。
5. Agent 自动实验。

## 17. 一句话总结

本项目第一阶段不是做全能交易机器人，而是高质量复刻文章实验：用 Binance 合约 K 线识别操纵周期，筛选高操纵币，复现 V4A 暴涨回撤早期做空信号，并用严格的成本、next-bar 成交和 holdout 验证把回测水分挤掉。
