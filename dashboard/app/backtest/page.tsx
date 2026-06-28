"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { EquityChart } from "@/components/charts/EquityChart";
import { EmptyState } from "@/components/EmptyState";
import { ExperimentTable } from "@/components/tables/ExperimentTable";
import { TradeTable } from "@/components/tables/TradeTable";
import { Card } from "@/components/ui/card";
import { HashBadge } from "@/components/HashBadge";
import { useApi } from "@/lib/api";
import type { Experiment, ExperimentDetail } from "@/types/api";

const EMPTY_DETAIL: ExperimentDetail = {
  experiment_id: "",
  name: "",
  strategy: "V4A",
  engine: "",
  split: "",
  status: "failed",
  config_hash: "",
  split_hash: "",
  data_snapshot_hash: "",
  git_commit_hash: "",
  report_path: "",
  trade_log_path: "",
  created_at: "",
  metrics: {
    net_return: 0,
    sharpe: 0,
    sortino: 0,
    max_drawdown: 0,
    profit_factor: 0,
    win_rate: 0,
    avg_win: 0,
    avg_loss: 0,
    trade_count: 0,
    median_holding_minutes: 0,
    fee_cost: 0,
    slippage_cost: 0,
    funding_cost: 0,
    top5_removed_net_return: 0
  },
  signals: [],
  trades: [],
  equity_curve: [],
  drawdown_curve: [],
  by_symbol: [],
  by_month: [],
  vectorbt_diff: {
    event_driven_primary: {
      net_return: 0,
      sharpe: 0,
      sortino: 0,
      max_drawdown: 0,
      profit_factor: 0,
      win_rate: 0,
      avg_win: 0,
      avg_loss: 0,
      trade_count: 0,
      median_holding_minutes: 0,
      fee_cost: 0,
      slippage_cost: 0,
      funding_cost: 0,
      top5_removed_net_return: 0
    },
    vectorbt_reference: null,
    comment: ""
  },
  config_view: {
    experiment: {},
    strategy: {},
    backtest: {}
  },
  report_urls: {}
};

function BacktestContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experiments = useApi<Experiment[]>("/api/experiments", []);
  const selectedId = useMemo(
    () => searchParams.get("experiment") ?? experiments.data[0]?.experiment_id ?? "",
    [experiments.data, searchParams]
  );
  const detail = useApi<ExperimentDetail>(
    selectedId ? `/api/experiments/${encodeURIComponent(selectedId)}` : "/api/experiments/__none__",
    EMPTY_DETAIL
  );

  if (experiments.data.length === 0) {
    return <EmptyState title="No backtest detail" description="当前还没有实验结果，先跑 pipeline 再看 detail。" />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">Backtest Detail</h2>
        <p className="mt-2 text-sm text-muted">Event-driven is primary. Any missing vectorbt benchmark is shown honestly instead of被伪造。</p>
      </div>
      <Card className="p-5">
        <ExperimentTable
          data={experiments.data}
          onRowClick={(row) => router.push(`/backtest?experiment=${encodeURIComponent(row.experiment_id)}`)}
        />
      </Card>
      <div className="grid gap-4 lg:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted">Strategy</p>
          <p className="mt-3 text-2xl font-semibold">{detail.data.strategy}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">Net Return</p>
          <p className="mt-3 text-2xl font-semibold text-positive">{(detail.data.metrics.net_return * 100).toFixed(1)}%</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">Sharpe</p>
          <p className="mt-3 text-2xl font-semibold">{detail.data.metrics.sharpe.toFixed(2)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">Top 5 Removed</p>
          <p className="mt-3 text-2xl font-semibold">{(detail.data.metrics.top5_removed_net_return * 100).toFixed(1)}%</p>
        </Card>
      </div>
      <Card className="p-5">
        <div className="grid gap-4 lg:grid-cols-4">
          <div>
            <p className="text-sm text-muted">Experiment</p>
            <HashBadge value={detail.data.experiment_id || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">Config Hash</p>
            <HashBadge value={detail.data.config_hash || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">Split Hash</p>
            <HashBadge value={detail.data.split_hash || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">Snapshot Hash</p>
            <HashBadge value={detail.data.data_snapshot_hash || "-"} />
          </div>
        </div>
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">Equity</h3>
          {detail.data.equity_curve.length === 0 ? (
            <EmptyState title="No equity curve" description="当前实验没有成交，不能伪造收益曲线。" />
          ) : (
            <EquityChart points={detail.data.equity_curve} />
          )}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">Drawdown</h3>
          {detail.data.drawdown_curve.length === 0 ? (
            <EmptyState title="No drawdown curve" description="当前实验没有成交，回撤也保持空态。" />
          ) : (
            <DrawdownChart points={detail.data.drawdown_curve} />
          )}
        </Card>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">By Symbol</h3>
          {detail.data.by_symbol.length === 0 ? (
            <EmptyState title="No symbol breakdown" description="当前实验没有成交通道。" />
          ) : (
            <div className="space-y-3">
              {detail.data.by_symbol.map((row) => (
                <div key={row.symbol} className="flex items-center justify-between rounded-lg bg-[#11161d] px-4 py-3 text-sm">
                  <span>{row.symbol}</span>
                  <span>{row.trade_count} trades</span>
                  <span className={row.net_return >= 0 ? "text-positive" : "text-negative"}>
                    {(row.net_return * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">By Month</h3>
          {detail.data.by_month.length === 0 ? (
            <EmptyState title="No month breakdown" description="当前实验没有月度收益数据。" />
          ) : (
            <div className="space-y-3">
              {detail.data.by_month.map((row) => (
                <div key={row.month} className="flex items-center justify-between rounded-lg bg-[#11161d] px-4 py-3 text-sm">
                  <span>{row.month}</span>
                  <span>{row.trade_count} trades</span>
                  <span className={row.net_return >= 0 ? "text-positive" : "text-negative"}>
                    {(row.net_return * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
      <Card className="p-5">
        <h3 className="mb-4 text-2xl font-semibold">Trades</h3>
        {detail.data.trades.length === 0 ? (
          <EmptyState title="No trade detail" description="这次样本没有触发有效成交，所以实验会被 reject 更合理。" />
        ) : (
          <TradeTable data={detail.data.trades} />
        )}
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">Vectorbt Diff</h3>
          <p className="text-sm text-muted">{detail.data.vectorbt_diff.comment}</p>
          {detail.data.vectorbt_diff.vectorbt_reference ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">Status</p>
                <p className="mt-1 font-semibold">{String(detail.data.vectorbt_diff.vectorbt_reference.status)}</p>
              </div>
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">Version</p>
                <p className="mt-1 font-semibold">{String(detail.data.vectorbt_diff.vectorbt_reference.version ?? "unknown")}</p>
              </div>
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">Net Delta</p>
                <p className="mt-1 font-semibold">
                  {detail.data.vectorbt_diff.net_return_delta == null ? "N/A" : `${(detail.data.vectorbt_diff.net_return_delta * 100).toFixed(2)}%`}
                </p>
              </div>
            </div>
          ) : null}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">Report Artifacts</h3>
          <div className="space-y-2 text-sm">
            {detail.data.report_urls.html ? <a className="text-accent" href={detail.data.report_urls.html}>HTML Report</a> : <p className="text-muted">HTML report unavailable</p>}
            {detail.data.report_urls.markdown ? <a className="text-accent" href={detail.data.report_urls.markdown}>Markdown Report</a> : <p className="text-muted">Markdown report unavailable</p>}
            {detail.data.report_urls.trades_csv ? <a className="text-accent" href={detail.data.report_urls.trades_csv}>Trades CSV</a> : <p className="text-muted">Trades CSV unavailable</p>}
          </div>
        </Card>
      </div>
      <Card className="p-5">
        <h3 className="mb-4 text-2xl font-semibold">Config View</h3>
        <pre className="overflow-x-auto rounded-lg bg-[#11161d] p-4 text-xs text-muted">
          {JSON.stringify(detail.data.config_view, null, 2)}
        </pre>
      </Card>
    </div>
  );
}

export default function BacktestPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">Loading backtest...</div>}>
      <BacktestContent />
    </Suspense>
  );
}
