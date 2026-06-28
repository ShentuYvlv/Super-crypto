"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { useApi } from "@/lib/api";
import type { OverviewPayload } from "@/types/api";

const EMPTY_OVERVIEW: OverviewPayload = {
  latest_pipeline_run: null,
  latest_experiment: null,
  today_signal_count: 0,
  active_monitored_symbols: 0,
  paper_pnl_7d: 0,
  validation_best_net_return: 0,
  max_drawdown: 0,
  data_health_score: 0,
  scanner_status: null,
  performance_snapshot: {
    equity_curve: [],
    drawdown_curve: [],
    split_comparison: []
  },
  data_warnings: [],
  latest_alerts: [],
  recent_trades: []
};

export function TopStatusBar() {
  const { data } = useApi("/api/overview", EMPTY_OVERVIEW);
  const pipeline = data.latest_pipeline_run;
  const scanner = data.scanner_status;
  const coinglassStatus = data.data_warnings.find((warning) => warning.source_name === "CoinGlass cache");

  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
      <div>
        <p className="text-sm text-muted">
          只读研究终端 · 事件驱动指标为主 · 不提供留出集执行入口
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge value={pipeline?.status ?? "无流水线"} />
        <StatusBadge value={scanner?.scanner_status ?? "扫描器空闲"} />
        <StatusBadge value={coinglassStatus?.status ?? "CoinGlass 未知"} />
        <StatusBadge value="本地" />
        <StatusBadge value={pipeline?.git_commit_hash ? `Git ${pipeline.git_commit_hash.slice(0, 7)}` : "Git 未知"} />
      </div>
    </div>
  );
}
