# Super Crypto

面向《实验复现与量化信号系统 PRD》的研究底座，包含：

- Binance / CoinGlass 数据采集与缓存
- Pump + Dump 周期识别与操纵评分
- V3 / V4A / V4B 信号与事件驱动回测
- validation / holdout guard、pipeline、report
- FastAPI 只读 API
- Next.js Dashboard
- realtime scanner、可选 webhook、paper trade
- AutoResearch 边界模块

默认行情数据说明：

- Binance USDT-M 公共行情接口不需要 API key。
- CoinGlass 当前按逆向 public 接口/缓存增强设计，不要求 `COINGLASS_API_KEY`。
- Discord / Telegram webhook 不是必需项，只在 `configs/scanner.yaml` 手动配置后启用。
- LLM 只用于后续 AutoResearch 研究助理，环境变量使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

## 快速开始

```bash
uv sync --extra dev
uv run python -m super_crypto.cli --help
uv run pytest
```

## 常用命令

```bash
uv run python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation
uv run python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split holdout --final
uv run python -m super_crypto.cli scanner --config configs/scanner.yaml --once
uv run python -m super_crypto.cli report serve --host 127.0.0.1 --port 8000
```

## 前端

```bash
cd dashboard
npm install
npm run build
```

`report serve` 会优先挂载 `dashboard/out` 作为只读前端静态站点。
