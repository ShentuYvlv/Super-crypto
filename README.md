# Super Crypto

面向《实验复现与量化信号系统 PRD》的 AutoResearch 量化研究系统，核心入口是：

```bash
just research
just holdout
just dashboard
```

其中：

- `research`：AI 自动提出假设、规划实验、跑 validation、复盘并冻结通过验证的策略。
- `holdout`：最终样本外验证，只在 `research` 产出 accepted/frozen 策略后手动执行。
- `dashboard`：只读查看研究过程、实验结果、最终验证和报告。

系统包含：

- Binance / CoinGlass 数据采集与缓存
- Pump + Dump 周期识别与操纵评分
- V3 / V4A / V4B 信号与事件驱动回测
- AutoResearch loop、validation / holdout guard、report
- FastAPI 只读 API
- Next.js Dashboard
- forward test scanner、可选 webhook、paper trade

默认行情数据说明：

- Binance USDT-M 公共行情接口不需要 API key。
- CoinGlass 当前按逆向 public 接口/缓存增强设计，不要求 `COINGLASS_API_KEY`。
- Discord / Telegram webhook 不是必需项，只在 forward test 配置后启用。
- LLM 用于 AutoResearch 研究循环，环境变量使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。未配置时可用规则兜底调试。

## 快速开始

```bash
uv sync --extra dev
just research
just holdout
just dashboard
```

`research` 可以反复运行；`holdout` 是最终样本外验证，不要反复运行；`dashboard` 只用于查看结果。

## 开发调试

```bash
uv run python -m super_crypto.cli --help
just dev-test
just dev-pipeline
just dev-experiment
```

## 前端

```bash
cd dashboard
npm install
npm run build
```

`report serve` 会优先挂载 `dashboard/out` 作为只读前端静态站点。
