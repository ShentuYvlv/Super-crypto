export type QualityState = "healthy" | "partial" | "stale" | "failed" | "blocked";

export type CurvePoint = {
  exit_time?: string;
  time?: string;
  equity?: number;
  drawdown?: number;
  value?: number;
};

export type Signal = {
  signal_id: string;
  symbol: string;
  strategy: "V3" | "V4A" | "V4B" | "PHASE1";
  side: "SHORT";
  signal_time: string;
  decision_time: string;
  data_cutoff_time: string;
  entry_reference: string;
  stop_loss: number;
  trailing_stop: number;
  confidence: number;
  manipulation_score_bucket: "ultra_high" | "high" | "medium" | "low";
  reason: string[];
  data_quality: QualityState;
  missing_fields: string[];
  stale_fields: string[];
  orderbook_slippage_bps?: number | null;
  status: string;
};

export type Trade = {
  trade_id: string;
  signal_id: string;
  experiment_id?: string | null;
  symbol: string;
  strategy: "V3" | "V4A" | "V4B" | "PHASE1";
  split: string;
  source: "backtest" | "paper";
  side: "SHORT";
  entry_time: string;
  entry_price: number;
  exit_time: string;
  exit_price: number;
  gross_return: number;
  fee_cost: number;
  slippage_cost: number;
  funding_cost: number;
  net_return: number;
  exit_reason: string;
  holding_minutes: number;
  mae: number;
  mfe: number;
  orderbook_snapshot_status: string;
};

export type ExperimentMetrics = {
  net_return: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  profit_factor: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  trade_count: number;
  median_holding_minutes: number;
  fee_cost: number;
  slippage_cost: number;
  funding_cost: number;
  top5_removed_net_return: number;
  f1?: number;
  precision?: number;
  recall?: number;
  auc?: number;
  train_f1?: number;
  train_precision?: number;
  train_recall?: number;
  train_auc?: number;
  holdout_f1?: number;
  holdout_precision?: number;
  holdout_recall?: number;
  holdout_auc?: number;
  threshold?: number;
  label_count?: number;
  sample_count?: number;
  positive_sample_count?: number;
  negative_sample_count?: number;
  train_sample_count?: number;
  train_positive_count?: number;
  holdout_sample_count?: number;
  holdout_positive_count?: number;
};

export type Phase1WindowDiagnostic = {
  window_id?: string;
  symbol: string;
  split: string;
  lead_time_hours?: number;
  window_start?: string | null;
  window_end?: string | null;
  data_start?: string | null;
  data_end?: string | null;
  window_rows: number;
  detected_event_start?: string | null;
  peak_time?: string | null;
  dump_end?: string | null;
  detection_rule?: string | null;
  positive_sample_time?: string | null;
  has_positive_sample?: boolean;
  status: string;
  reason?: string;
};

export type Phase1Diagnostics = {
  window_diagnostics: Phase1WindowDiagnostic[];
  window_diagnostics_path?: string | null;
  dataset_path?: string | null;
  candidate_path?: string | null;
  label_template_path?: string | null;
  label_count: number;
  sample_count: number;
  positive_sample_count: number;
  negative_sample_count: number;
  train_positive_count: number;
  holdout_positive_count: number;
  phase1_results: Array<Record<string, unknown>>;
};

export type Phase1ExperimentSummary = {
  experiment_id: string;
  status: string;
  created_at?: string;
  label_count: number;
  sample_count: number;
  positive_sample_count: number;
  negative_sample_count: number;
  train_sample_count: number;
  train_positive_count: number;
  holdout_sample_count: number;
  holdout_positive_count: number;
  train_f1: number;
  holdout_f1: number;
  holdout_precision: number;
  holdout_recall: number;
  best_train_experiment?: string | null;
  best_holdout_experiment?: string | null;
  lightgbm_holdout_f1?: number | null;
};

export type Phase1SplitSummary = {
  split: string;
  symbols: string[];
  symbol_count: number;
  label_count: number;
  sample_count: number;
  positive_sample_count: number;
  negative_sample_count: number;
};

export type Phase1FeatureQuality = {
  key: string;
  label: string;
  status: string;
  available_columns: string[];
  nonzero_sample_count: number;
  sample_count: number;
  missing_ratio: number;
  quality_counts: Record<string, number>;
};

export type Phase1ModelResult = {
  experiment: string;
  model: string;
  status: string;
  train_f1?: number;
  train_precision?: number;
  train_recall?: number;
  train_auc?: number;
  holdout_f1?: number;
  holdout_precision?: number;
  holdout_recall?: number;
  holdout_auc?: number;
  threshold?: number;
  train_sample_count?: number;
  holdout_sample_count?: number;
  train_positive_count?: number;
  holdout_positive_count?: number;
  features?: string[];
  missing_features?: string[];
};

export type Phase1ConclusionFlag = {
  key: string;
  severity: "warning" | "danger" | "info" | string;
  label: string;
  detail: string;
  experiments?: string[];
};

export type Phase1ExperimentDetail = {
  experiment: Experiment;
  summary: Phase1ExperimentSummary;
  splits: Phase1SplitSummary[];
  windows: Phase1WindowDiagnostic[];
  labels: Array<Record<string, unknown>>;
  samples: Array<Record<string, unknown>>;
  sample_limit: number;
  sample_count: number;
  candidates: Array<Record<string, unknown>>;
  feature_quality: Phase1FeatureQuality[];
  model_results: Phase1ModelResult[];
  conclusion_flags: Phase1ConclusionFlag[];
  report_urls: {
    html?: string | null;
    markdown?: string | null;
  };
  artifact_paths: {
    dataset?: string | null;
    labels?: string | null;
    windows?: string | null;
    candidates?: string | null;
  };
};

export type Experiment = {
  experiment_id: string;
  name: string;
  strategy: "V3" | "V4A" | "V4B" | "PHASE1";
  engine: string;
  split: string;
  status: string;
  config_hash: string;
  split_hash: string;
  data_snapshot_hash: string;
  git_commit_hash: string;
  markdown_report_path?: string;
  report_path: string;
  trade_log_path: string;
  created_at: string;
  failure_reason?: string | null;
  metrics: ExperimentMetrics;
  base_metrics?: ExperimentMetrics;
  selected_parameters?: Record<string, number | string>;
  parameter_selection_source?: string;
  parameter_selection_reason?: string;
  autoresearch_run_id?: string;
  autoresearch_iteration?: number;
  autoresearch_started_at?: string;
  autoresearch_completed_at?: string;
  autoresearch_parent_config?: string;
  autoresearch_generated_config?: string;
  autoresearch_hypothesis?: string;
  autoresearch_decision?: string;
  autoresearch_recommendation?: string;
  parameter_sensitivity?: Array<{
    params: Record<string, number | string>;
    signal_count: number;
    metrics: ExperimentMetrics;
  }>;
};

export type ExperimentDetail = Experiment & {
  phase1_diagnostics?: Phase1Diagnostics | null;
  signals: Signal[];
  trades: Trade[];
  equity_curve: Array<{ exit_time: string; equity: number }>;
  drawdown_curve: Array<{ exit_time: string; drawdown: number }>;
  by_symbol: Array<{ symbol: string; net_return: number; trade_count: number }>;
  by_month: Array<{ month: string; net_return: number; trade_count: number }>;
  vectorbt_diff: {
    event_driven_primary: ExperimentMetrics;
    vectorbt_reference: Record<string, unknown> | null;
    net_return_delta?: number | null;
    comment: string;
  };
  config_view: {
    experiment: Record<string, unknown>;
    strategy: Record<string, unknown>;
    backtest: Record<string, unknown>;
  };
  report_urls: {
    html?: string | null;
    markdown?: string | null;
    trades_csv?: string | null;
  };
};

export type OrderbookSummary = {
  snapshot_time?: string | null;
  spread_bps?: number | null;
  imbalance?: number | null;
  slippage_bps_sell?: Record<string, number>;
  slippage_bps_buy?: Record<string, number>;
};

export type OrderbookDepthRow = {
  price: number;
  bid: number;
  ask: number;
};

export type SymbolSummary = {
  symbol: string;
  manipulation_score: number;
  score_bucket: string;
  cycle_count: number;
  avg_pump_return: number;
  avg_dump_return: number;
  median_duration_hours: number;
  latest_funding: number;
  oi_change_1h: number;
  oi_change_6h: number;
  oi_change_24h: number;
  quote_volume_24h: number;
  data_completeness: number;
  data_source_summary?: {
    healthy_sources: number;
    total_sources: number;
    coverage: number;
    status: string;
    latest_timestamp?: string | null;
  };
  orderbook_depth_status: string;
  latest_signal?: Signal | null;
  latest_signal_label: string;
  trade_count: number;
  paper_trade_count: number;
  point_in_time_cutoff?: string | null;
  latest_orderbook: OrderbookSummary;
  data_sources?: DataQualityRow[];
};

export type SymbolDetail = SymbolSummary & {
  klines: Array<Record<string, number | string>>;
  cycles: Array<Record<string, number | string>>;
  funding_series: Array<Record<string, number | string>>;
  open_interest_series: Array<Record<string, number | string>>;
  signals: Signal[];
  trades: Trade[];
  paper_trades: Trade[];
  orderbook_depth: OrderbookDepthRow[];
};

export type SignalDetail = Signal & {
  paper_trade?: Trade | null;
  backtest_trades: Trade[];
  kline_context: Array<Record<string, number | string>>;
  funding_series: Array<Record<string, number | string>>;
  open_interest_series: Array<Record<string, number | string>>;
  orderbook_snapshot: OrderbookSummary;
  webhook_payload: Record<string, unknown>;
};

export type TradeDetail = Trade & {
  signal?: Signal | null;
  is_top5_trade: boolean;
  kline_context: Array<Record<string, number | string>>;
  trade_marker?: {
    trade_id: string;
    side: "SHORT";
    entry_time: string;
    exit_time: string;
    entry_price: number;
    exit_price: number;
    quantity_base: number;
    entry_notional_usdt: number;
    exit_notional_usdt: number;
    pnl_usdt: number;
    net_return: number;
    gross_return: number;
    fee_cost: number;
    slippage_cost: number;
    funding_cost: number;
    notional_usdt: number;
  };
};

export type DataQualityRow = {
  source_name: string;
  status: QualityState;
  file_count: number;
  freshness?: string | null;
  latest_timestamp?: string | null;
  path?: string;
  notes?: string[];
};

export type ReportArtifact = {
  report_type: string;
  experiment_id?: string | null;
  generated_at: number;
  split?: string | null;
  strategy?: string | null;
  path: string;
  hash: string;
  url?: string | null;
};

export type PipelineRun = {
  run_id: string;
  name: string;
  split: string;
  status: string;
  config_hash: string;
  split_hash: string;
  data_snapshot_hash: string;
  git_commit_hash: string;
  report_path?: string | null;
  created_at: string;
  updated_at: string;
};

export type AutoResearchIteration = {
  iteration: number;
  started_at?: string;
  completed_at?: string;
  hypothesis: {
    hypothesis?: string;
    rationale?: string;
    risk?: string;
    llm_error?: string;
  };
  plan: {
    hypothesis?: string;
    suggested_changes?: {
      parameter_grid?: Record<string, unknown>;
      notes?: string;
    };
    llm_error?: string;
  };
  generated_config: string;
  validation_result: {
    experiment: Experiment;
  };
  validation_acceptance: {
    accepted: boolean;
    reason: string;
  };
  review: {
    decision?: string;
    recommendation?: string;
    trade_summary?: {
      trade_count: number;
      symbols: string[];
      exit_reasons: Record<string, number>;
      net_return_by_symbol: Record<string, number>;
    };
    evidence?: string[];
    llm_error?: string;
  };
};

export type AutoResearchRun = {
  run_id: string;
  created_at: string;
  completed_at?: string;
  status: string;
  config_path: string;
  autoresearch_config_path: string;
  model_status: {
    mode: string;
    model?: string | null;
    base_url?: string | null;
    reason?: string;
  };
  latest_acceptance: {
    accepted: boolean;
    reason: string;
  };
  cycle_research_result?: CycleResearchRun | null;
  iterations: AutoResearchIteration[];
  recommendation: string;
  recommendation_path?: string;
  manifest_path?: string;
};

export type CycleResearchCandidate = {
  candidate_id: string;
  cycle_config: {
    pump_threshold_min: number;
    pump_threshold_max: number;
    dump_retrace_ratio: number;
    max_cycle_hours: number;
    dedupe_gap_hours: number;
    [key: string]: number | string;
  };
  quality: {
    score: number;
    cycle_count: number;
    covered_symbols: number;
    coverage_ratio: number;
    median_pump_return: number;
    median_dump_return: number;
    median_duration_hours: number;
    matched_seed_event_count: number;
    expanded_event_count: number;
    rejection_reason?: string;
  };
  cycles_by_symbol: Record<string, number>;
};

export type CycleResearchRun = {
  run_id: string;
  created_at: string;
  completed_at?: string;
  status: string;
  pipeline_config_path: string;
  autoresearch_config_path: string;
  model_status: {
    mode: string;
    model?: string | null;
    reason?: string;
  };
  hypothesis: {
    mode?: string;
    hypothesis?: string;
    rationale?: string;
    risk?: string;
    llm_error?: string;
  };
  base_cycle_config: Record<string, number | string>;
  timeframe: string;
  symbols: string[];
  candidate_count: number;
  best_candidate_id?: string | null;
  best_cycle_config?: CycleResearchCandidate["cycle_config"] | null;
  best_quality?: CycleResearchCandidate["quality"] | null;
  applied_path?: string | null;
  candidates: CycleResearchCandidate[];
  manifest_path?: string;
};

export type OverviewPayload = {
  latest_pipeline_run?: PipelineRun | null;
  latest_research_run?: AutoResearchRun | null;
  latest_experiment?: Experiment | null;
  latest_validation_experiment?: Experiment | null;
  latest_holdout_experiment?: Experiment | null;
  frozen_config?: {
    available: boolean;
    path?: string | null;
    source_experiment_id?: string | null;
    created_at?: string | null;
  };
  holdout_status?: {
    run_count: number;
    has_result: boolean;
    latest_experiment_id?: string | null;
    status: string;
  };
  today_signal_count: number;
  active_monitored_symbols: number;
  paper_pnl_7d: number;
  validation_best_net_return: number;
  max_drawdown: number;
  data_health_score: number;
  scanner_status?: {
    scanner_status: string;
    generated_at: string;
    generated_signals: number;
    tracked_symbols: number;
  } | null;
  performance_snapshot: {
    equity_curve: Array<{ exit_time: string; equity: number }>;
    drawdown_curve: Array<{ exit_time: string; drawdown: number }>;
    split_comparison: Array<{
      split: string;
      net_return: number;
      trade_count: number;
      status: string;
    }>;
  };
  data_warnings: Array<{
    source_name: string;
    status: string;
    detail: string;
  }>;
  latest_alerts: Signal[];
  recent_trades: Trade[];
};

export type ApiEnvelope<T> = {
  generated_at: string;
  source: string;
  freshness_sec: number;
  data_quality: string;
  missing_fields: string[];
  stale_fields: string[];
  payload: T;
};
