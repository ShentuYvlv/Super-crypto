# Super Crypto Todo

## Phase Checklist

- [x] Phase 0 项目骨架、配置、CLI、日志、pytest 基线
- [x] Phase 1 Binance 基础市场数据、Parquet 落地、质量检查
- [x] Phase 2 候选增强、CoinGlass 缓存、订单簿成本特征
- [x] Phase 3 Pump + Dump 周期识别、去重、统计
- [x] Phase 4 庄币评分、point-in-time cutoff、bucket 输出
- [x] Phase 5 V3 / V4A / V4B 信号与 next-bar entry 约束
- [x] Phase 6 事件驱动回测、成本模型、交易报表、参数敏感性落库
- [x] Phase 7 split manifest / split hash / holdout guard / data snapshot hash
- [x] Phase 8 pipeline / report server / Markdown + HTML + CSV artifacts
- [x] Phase 9 realtime scanner / dedupe / paper trade / heartbeat / webhook 容错
- [x] Phase 10 FastAPI + Next.js Dashboard（真实数据、只读、详情区、空态/错态）
- [x] Phase 11 AutoResearch 自动生成实验配置并执行 validation 验证
- [x] Phase 12 外部增强研究字段、可选 LightGBM 过滤器、策略隔离边界

## This Review Round

- [x] 修正 CLI 为 `--config` / `--split` 风格，和 PRD 对齐
- [x] 修正无效 Binance futures symbol 配置
- [x] 修正 open interest 归一化 schema 错误
- [x] 修正 SQLite payload 序列化 datetime 崩溃
- [x] 修正空 cycle parquet 写入失败
- [x] 修正 score_symbols 在 OI 字段缺失时的兼容
- [x] 修正 pipeline / experiment 元数据：git hash、snapshot hash、accept/reject 状态
- [x] 修正 scanner 重复信号去重与非法 webhook 自动跳过
- [x] 修正 FastAPI report API：overview / experiments detail / symbols detail / reports artifacts
- [x] 修正 Dashboard 直接读 mock 的页面，全部切回真实 API
- [x] 修正 Dashboard 图表、详情视图、报表链接、空态与错态
- [x] 修正 AutoResearch：按 hypothesis 生成实验配置、运行 validation、遵守 protected config guard
- [x] 修正 pipeline `--only score_symbols` 覆盖历史 `report_path` 的问题
- [x] 补齐 Phase 12：liquidation / onchain 分析字段与 LightGBM 可选过滤模块
- [x] 补齐真实 `vectorbt` optional benchmark：实验 payload、API diff、Dashboard 展示均读取真实状态

## Verification

- [x] `pytest`
- [x] `python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation --from run_experiment`
- [x] `python -m super_crypto.cli scanner --config configs/scanner.yaml --once`
- [x] `python -m super_crypto.cli autoresearch --config configs/experiment_v4a.yaml`
- [x] `python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation --only score_symbols`
- [x] `python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split holdout` 未带 `--final` 时正确拒绝
- [x] `python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation --from run_experiment` 已写出 `vectorbt_benchmark.status=available`
- [x] `python -m super_crypto.cli report serve --help`
- [x] `npm install`
- [x] `npm run build`
- [x] 本地启动 `report serve` 后验证 `/`、`/api/overview`、`/api/experiments/{id}`、`/artifacts/.../report.html`

## Objective Note

- [x] Dashboard 明确把 event-driven 作为主指标展示
- [x] Dashboard 明确没有任何执行实验、修改配置、触发 holdout 的入口
- [x] 最新实验因 `trade_count_below_threshold` 被正确标记为 `rejected`
- [x] 最新 pipeline run 已写入真实 `git_commit_hash` 和 `data_snapshot_hash`
- [x] 最新 `pytest` 结果：11 passed
- [x] Phase 6 严格说明：当前已实现事件驱动主回测、参数敏感性、真实 `vectorbt` optional benchmark；主判定仍以 event-driven 为准
- [x] Dashboard 设计严格说明：本地已完成 `dashboard设计.md` 与 dashboard 实现；外部 Figma frame URL / node id 无法在本地验证
