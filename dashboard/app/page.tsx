"use client";

import Link from "next/link";

import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { EquityChart } from "@/components/charts/EquityChart";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { MetricCard } from "@/components/MetricCard";
import { SignalReasonTags } from "@/components/SignalReasonTags";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import type { OverviewPayload, SymbolSummary } from "@/types/api";

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

export default function OverviewPage() {
  const overview = useApi("/api/overview", EMPTY_OVERVIEW);
  const symbols = useApi<SymbolSummary[]>("/api/symbols", []);

  if (overview.error && overview.data.latest_pipeline_run == null) {
    return <ErrorState title="Overview API 不可用" description="请先运行 report serve 或检查后端接口。" />;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-4xl font-semibold">Overview</h2>
      <div className="grid gap-4 xl:grid-cols-6">
        <MetricCard label="Today Signals" value={String(overview.data.today_signal_count)} sublabel="current data window" badge="Live" />
        <MetricCard label="Tracked Symbols" value={String(overview.data.active_monitored_symbols)} sublabel="signal-active universe" badge="Pool" />
        <MetricCard
          label="Paper PnL 7D"
          value={`${(overview.data.paper_pnl_7d * 100).toFixed(1)}%`}
          sublabel="paper trades only"
          badge="Paper"
        />
        <MetricCard
          label="Validation Best"
          value={`${(overview.data.validation_best_net_return * 100).toFixed(1)}%`}
          sublabel="latest experiment"
          badge="Event"
        />
        <MetricCard label="Max Drawdown" value={`${(overview.data.max_drawdown * 100).toFixed(1)}%`} sublabel="event-driven" badge="Risk" />
        <MetricCard
          label="Data Health"
          value={`${(overview.data.data_health_score * 100).toFixed(0)}%`}
          sublabel="pipeline confidence"
          badge={overview.data.data_warnings.length ? "Warn" : "Healthy"}
        />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr_.8fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-2xl font-semibold">Candidate Scoreboard</h3>
              <p className="text-sm text-muted">Point-in-time cutoff, score bucket, derivatives, and latest signal.</p>
            </div>
            <Link href="/symbols" prefetch={false} className="text-sm text-accent">
              View all
            </Link>
          </div>
          {symbols.data.length === 0 ? (
            <EmptyState title="No symbol snapshot" description="先跑 pipeline 或 scanner，页面会自动读取最新 parquet / SQLite 数据。" />
          ) : (
            <div className="space-y-3">
              {symbols.data.slice(0, 8).map((row) => (
                <Link
                  key={row.symbol}
                  href={`/symbols?symbol=${encodeURIComponent(row.symbol)}`}
                  prefetch={false}
                  className="grid grid-cols-[1.1fr_.7fr_.7fr_.7fr_1fr] gap-3 rounded-md bg-[#11161d] px-3 py-3 text-sm hover:bg-surface2"
                >
                  <span className="font-medium">{row.symbol}</span>
                  <span className="text-accent">{row.manipulation_score.toFixed(1)}</span>
                  <span className={row.latest_funding < 0 ? "text-negative" : "text-positive"}>
                    {(row.latest_funding * 100).toFixed(2)}%
                  </span>
                  <span className={row.oi_change_24h >= 0 ? "text-positive" : "text-negative"}>
                    {(row.oi_change_24h * 100).toFixed(1)}%
                  </span>
                  <span className="truncate text-muted">{row.latest_signal_label}</span>
                </Link>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">Performance Snapshot</h3>
          <p className="mt-1 text-sm text-muted">Holdout is never triggered here. Event-driven metrics are the only primary metrics.</p>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {overview.data.performance_snapshot.split_comparison.map((row) => (
              <Card key={`${row.split}-${row.status}`} className="bg-[#11161d] p-4">
                <p className="text-sm text-muted">{row.split}</p>
                <p className="mt-3 text-xl font-semibold">{row.status}</p>
                <p className="mt-2 text-positive">{(row.net_return * 100).toFixed(1)}%</p>
                <p className="text-sm text-muted">trade count {row.trade_count}</p>
              </Card>
            ))}
            {overview.data.performance_snapshot.split_comparison.length === 0 ? (
              <EmptyState title="No experiment summary" description="最新实验详情还没生成，先跑 pipeline。" />
            ) : null}
          </div>
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">Latest Alerts</h3>
          <div className="mt-4 space-y-3">
            {overview.data.latest_alerts.length === 0 ? (
              <EmptyState title="No live signal" description="当前样本没有触发 V4A / V4B 信号，这比伪造信号更可信。" />
            ) : (
              overview.data.latest_alerts.map((signal) => (
                <Link
                  key={signal.signal_id}
                  href={`/signals?signal=${encodeURIComponent(signal.signal_id)}`}
                  prefetch={false}
                  className="block rounded-lg border border-border bg-[#11161d] p-4 hover:bg-surface2"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold">{signal.symbol}</p>
                      <p className="mt-1 text-negative">{signal.strategy} SHORT</p>
                    </div>
                    <p className="text-sm text-muted">{(signal.confidence * 100).toFixed(0)}%</p>
                  </div>
                  <div className="mt-3">
                    <SignalReasonTags reasons={signal.reason} />
                  </div>
                </Link>
              ))
            )}
          </div>
        </Card>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">Equity Curve</h3>
          {overview.data.performance_snapshot.equity_curve.length === 0 ? (
            <EmptyState title="No equity curve" description="没有交易时不展示伪造收益曲线。" />
          ) : (
            <EquityChart points={overview.data.performance_snapshot.equity_curve} />
          )}
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">Drawdown Curve</h3>
          {overview.data.performance_snapshot.drawdown_curve.length === 0 ? (
            <EmptyState title="No drawdown curve" description="当前实验没有成交，回撤图保持空态。" />
          ) : (
            <DrawdownChart points={overview.data.performance_snapshot.drawdown_curve} />
          )}
        </Card>
      </div>
      <Card className="p-5">
        <h3 className="text-2xl font-semibold">Data Warnings</h3>
        {overview.data.data_warnings.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No critical warning from the latest pipeline run.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {overview.data.data_warnings.map((warning) => (
              <div key={`${warning.source_name}-${warning.detail}`} className="rounded-lg border border-border bg-[#11161d] px-4 py-3 text-sm">
                <p className="font-medium">{warning.source_name}</p>
                <p className="mt-1 text-muted">
                  {warning.status} · {warning.detail}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
