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
import { displayDateTime, displayStatus, displayText, localizeValue } from "@/lib/display";
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
    return <EmptyState title="暂无回测详情" description="当前还没有实验结果，先跑流水线再看详情。" />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-4xl font-semibold">回测详情</h2>
        <p className="mt-2 text-sm text-muted">事件驱动回测是主裁判；缺失的 vectorbt 对照会如实显示，不会伪造。</p>
      </div>
      <Card className="p-5">
        <ExperimentTable
          data={experiments.data}
          activeExperimentId={selectedId}
          onRowClick={(row) => router.push(`/backtest?experiment=${encodeURIComponent(row.experiment_id)}`)}
        />
      </Card>
      <div className="grid gap-4 lg:grid-cols-6">
        <Card className="p-4">
          <p className="text-sm text-muted">策略</p>
          <p className="mt-3 text-2xl font-semibold">{detail.data.strategy}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">状态</p>
          <p className="mt-3 text-2xl font-semibold">{displayStatus(detail.data.status)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">运行时间</p>
          <p className="mt-3 text-lg font-semibold">{displayDateTime(detail.data.created_at)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">净收益</p>
          <p className="mt-3 text-2xl font-semibold text-positive">{(detail.data.metrics.net_return * 100).toFixed(1)}%</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">夏普</p>
          <p className="mt-3 text-2xl font-semibold">{detail.data.metrics.sharpe.toFixed(2)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">剔除前 5 笔后</p>
          <p className="mt-3 text-2xl font-semibold">{(detail.data.metrics.top5_removed_net_return * 100).toFixed(1)}%</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">结论</p>
          <p className="mt-3 text-lg font-semibold">{displayText(detail.data.failure_reason ?? (detail.data.metrics.trade_count < 20 ? "low_trade_count" : detail.data.status))}</p>
        </Card>
        <Card className="p-4 lg:col-span-2">
          <p className="text-sm text-muted">参数选择</p>
          <p className="mt-3 text-lg font-semibold">{displayText(detail.data.parameter_selection_source ?? "base_strategy_config")}</p>
          <p className="mt-2 text-xs text-muted">{displayText(detail.data.parameter_selection_reason ?? "-")}</p>
        </Card>
      </div>
      {detail.data.selected_parameters && Object.keys(detail.data.selected_parameters).length > 0 ? (
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">选中参数</h3>
          <pre className="overflow-x-auto rounded-lg bg-[#11161d] p-4 text-xs text-muted">
            {JSON.stringify(detail.data.selected_parameters, null, 2)}
          </pre>
        </Card>
      ) : null}
      <Card className="p-5">
        <div className="grid gap-4 lg:grid-cols-4">
          <div>
            <p className="text-sm text-muted">实验</p>
            <HashBadge value={detail.data.experiment_id || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">配置哈希</p>
            <HashBadge value={detail.data.config_hash || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">切分哈希</p>
            <HashBadge value={detail.data.split_hash || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">快照哈希</p>
            <HashBadge value={detail.data.data_snapshot_hash || "-"} />
          </div>
        </div>
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">权益</h3>
          {detail.data.equity_curve.length === 0 ? (
            <EmptyState title="暂无权益曲线" description="当前实验没有成交，不能伪造收益曲线。" />
          ) : (
            <EquityChart points={detail.data.equity_curve} />
          )}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">回撤</h3>
          {detail.data.drawdown_curve.length === 0 ? (
            <EmptyState title="暂无回撤曲线" description="当前实验没有成交，回撤也保持空态。" />
          ) : (
            <DrawdownChart points={detail.data.drawdown_curve} />
          )}
        </Card>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">按标的</h3>
          {detail.data.by_symbol.length === 0 ? (
            <EmptyState title="暂无标的拆分" description="当前实验没有成交通道。" />
          ) : (
            <div className="space-y-3">
              {detail.data.by_symbol.map((row) => (
                <div key={row.symbol} className="flex items-center justify-between rounded-lg bg-[#11161d] px-4 py-3 text-sm">
                  <span>{row.symbol}</span>
                  <span>{row.trade_count} 笔交易</span>
                  <span className={row.net_return >= 0 ? "text-positive" : "text-negative"}>
                    {(row.net_return * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">按月份</h3>
          {detail.data.by_month.length === 0 ? (
            <EmptyState title="暂无月度拆分" description="当前实验没有月度收益数据。" />
          ) : (
            <div className="space-y-3">
              {detail.data.by_month.map((row) => (
                <div key={row.month} className="flex items-center justify-between rounded-lg bg-[#11161d] px-4 py-3 text-sm">
                  <span>{row.month}</span>
                  <span>{row.trade_count} 笔交易</span>
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
          <h3 className="mb-4 text-2xl font-semibold">交易</h3>
        {detail.data.trades.length === 0 ? (
          <EmptyState title="暂无交易详情" description="这次样本没有触发有效成交，所以实验被拒绝更合理。" />
        ) : (
          <TradeTable data={detail.data.trades} />
        )}
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">vectorbt 对照差异</h3>
          <p className="text-sm text-muted">{displayText(detail.data.vectorbt_diff.comment)}</p>
          {detail.data.vectorbt_diff.vectorbt_reference ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">状态</p>
                <p className="mt-1 font-semibold">{displayStatus(String(detail.data.vectorbt_diff.vectorbt_reference.status))}</p>
              </div>
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">版本</p>
                <p className="mt-1 font-semibold">{String(detail.data.vectorbt_diff.vectorbt_reference.version ?? "未知")}</p>
              </div>
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">净收益差值</p>
                <p className="mt-1 font-semibold">
                  {detail.data.vectorbt_diff.net_return_delta == null ? "不适用" : `${(detail.data.vectorbt_diff.net_return_delta * 100).toFixed(2)}%`}
                </p>
              </div>
            </div>
          ) : null}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">报告产物</h3>
          <div className="space-y-2 text-sm">
            {detail.data.report_urls.html ? <a className="text-accent" href={detail.data.report_urls.html}>HTML 报告</a> : <p className="text-muted">HTML 报告不可用</p>}
            {detail.data.report_urls.markdown ? <a className="text-accent" href={detail.data.report_urls.markdown}>Markdown 报告</a> : <p className="text-muted">Markdown 报告不可用</p>}
            {detail.data.report_urls.trades_csv ? <a className="text-accent" href={detail.data.report_urls.trades_csv}>交易 CSV</a> : <p className="text-muted">交易 CSV 不可用</p>}
          </div>
        </Card>
      </div>
      <Card className="p-5">
        <h3 className="mb-4 text-2xl font-semibold">配置视图</h3>
        <pre className="overflow-x-auto rounded-lg bg-[#11161d] p-4 text-xs text-muted">
          {JSON.stringify(localizeValue(detail.data.config_view), null, 2)}
        </pre>
      </Card>
    </div>
  );
}

export default function BacktestPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted">正在加载回测...</div>}>
      <BacktestContent />
    </Suspense>
  );
}
