const STATUS_LABELS: Record<string, string> = {
  accepted: "已接受",
  rejected: "已拒绝",
  failed: "失败",
  blocked: "阻塞",
  partial: "部分可用",
  stale: "过期",
  healthy: "健康",
  running: "运行中",
  completed: "已完成",
  idle: "空闲",
  open: "打开",
  closed: "已关闭",
  local: "本地",
  backtest: "回测",
  paper: "模拟",
  short: "做空",
  low: "低",
  medium: "中",
  high: "高",
  ultra_high: "极高",
  no_pipeline: "无流水线",
  scanner_idle: "扫描器空闲",
  coinglass_unknown: "CoinGlass 未知",
  "git unknown": "Git 未知",
  low_trade_count: "交易数不足",
  train: "训练集",
  validation: "验证集",
  train_validation: "训练 + 验证",
  holdout: "留出集",
  final: "最终验收",
  event_driven: "事件驱动",
  vectorbt: "vectorbt 对照",
  stop_loss: "止损",
  trailing_stop: "移动止损",
  max_hold: "最大持仓",
  take_profit: "止盈",
  next_bar_open: "下一根 K 线开盘",
  available: "可用",
  unavailable: "不可用",
  configured: "已配置",
  no_signal: "无信号",
  rules_fallback: "规则兜底",
  llm: "大模型",
  none: "无"
};

const REASON_LABELS: Record<string, string> = {
  active_pump: "活跃拉盘",
  first_sell_pressure: "首次卖压",
  support_break: "跌破支撑",
  next_bar_entry: "下一根 K 入场",
  trailing_stop: "移动止损",
  stop_loss: "止损",
  max_hold: "最大持仓",
  orderbook_slippage_ok: "盘口滑点可接受",
  orderbook_slippage_high: "盘口滑点偏高",
  manipulation_bucket: "操纵评分分组",
  naked_k: "裸 K",
  funding_context: "资金费上下文",
  oi_context: "持仓量上下文"
};

const TEXT_LABELS: Record<string, string> = {
  "Reference benchmark only; event-driven backtest remains the source of truth.":
    "仅作为参考基准；事件驱动回测仍是主裁判。",
  "No vectorbt benchmark found for this experiment.": "该实验没有 vectorbt 对照结果。",
  "No persisted vectorbt benchmark found for this experiment.": "该实验没有持久化的 vectorbt 对照结果。",
  "No vectorbt benchmark entries were generated.": "没有生成 vectorbt 对照入场。",
  "No critical warning from the latest pipeline run.": "最新 pipeline 没有关键告警。",
  trade_count_below_threshold: "交易数低于门槛",
  no_grid_candidate_accepted: "没有参数候选通过验收",
  base_strategy_config: "基础策略配置",
  parameter_grid: "参数网格",
  parameter_grid_best_effort: "参数网格最佳候选",
  parameter_selection_disabled: "参数选择已关闭",
  score_count_zero: "评分结果为 0",
  request_failed: "请求失败",
  "CoinGlass cache": "CoinGlass 缓存",
  binance_klines: "Binance K 线",
  binance_funding: "Binance 资金费",
  binance_open_interest: "Binance 持仓量",
  binance_orderbook: "Binance 盘口",
  coinglass_cache: "CoinGlass 缓存",
  no_pipeline: "无流水线",
  scanner_idle: "扫描器空闲",
  "No signal": "无信号",
  none: "无",
  partial: "部分可用",
  healthy: "健康",
  stale: "过期",
  failed: "失败"
};

const REPORT_TYPE_LABELS: Record<string, string> = {
  html: "HTML 报告",
  markdown: "Markdown 报告",
  md: "Markdown 报告",
  csv: "CSV 文件",
  trades_csv: "交易 CSV"
};

const FIELD_LABELS: Record<string, string> = {
  experiment: "实验",
  strategy: "策略",
  backtest: "回测",
  symbol: "标的",
  side: "方向",
  signal_time: "信号时间",
  entry: "入场",
  entry_reference: "入场参考",
  stop_loss: "止损",
  trailing_stop: "移动止损",
  confidence: "置信度",
  manipulation_score_bucket: "操纵评分分组",
  reason: "原因",
  engine: "引擎",
  split: "切分",
  fee_bps: "手续费基点",
  slippage_bps: "滑点基点",
  funding_cost: "资金费成本",
  max_hold_bars: "最大持仓 K 线数",
  next_bar_open: "下一根 K 线开盘",
  funding_series: "资金费序列",
  open_interest_series: "持仓量序列",
  orderbook_snapshot: "盘口快照",
  spread_bps: "价差基点",
  imbalance: "买卖盘不平衡",
  slippage_bps_sell: "卖出滑点基点"
};

export function displayStatus(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return STATUS_LABELS[value.toLowerCase()] ?? value;
}

export function displayReason(value: string): string {
  return REASON_LABELS[value] ?? STATUS_LABELS[value.toLowerCase()] ?? value;
}

export function displayText(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return TEXT_LABELS[value] ?? STATUS_LABELS[value.toLowerCase()] ?? value;
}

export function displayReportType(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return REPORT_TYPE_LABELS[value.toLowerCase()] ?? displayText(value);
}

export function displayField(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return FIELD_LABELS[value] ?? displayText(value);
}

export function localizeValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(localizeValue);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, nestedValue]) => [displayField(key), localizeValue(nestedValue)])
    );
  }
  if (typeof value === "string") {
    return displayText(value);
  }
  return value;
}

export function displayDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(parsed);
}
