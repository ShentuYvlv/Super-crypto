"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { EquityChart } from "@/components/charts/EquityChart";
import { EmptyState } from "@/components/EmptyState";
import { ExperimentTable } from "@/components/tables/ExperimentTable";
import { TradeTable } from "@/components/tables/TradeTable";
import { EMPTY_TRADE_DETAIL, TradeDetailPanel } from "@/components/trades/TradeDetailPanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HashBadge } from "@/components/HashBadge";
import { useApi } from "@/lib/api";
import { displayDateTime, displayStatus, displayText, localizeValue } from "@/lib/display";
import type { Experiment, ExperimentDetail, TradeDetail } from "@/types/api";

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
  const experimentsRequest = useApi<Experiment[]>("/api/experiments", []);
  const [localExperiments, setLocalExperiments] = useState<Experiment[] | null>(null);
  const [editing, setEditing] = useState(false);
  const [selectedExperimentIds, setSelectedExperimentIds] = useState<Set<string>>(new Set());
  const [selectedTradeIdByExperiment, setSelectedTradeIdByExperiment] = useState<Record<string, string>>(
    {}
  );
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const experiments = localExperiments ?? experimentsRequest.data;
  const selectedId = useMemo(
    () => searchParams.get("experiment") ?? experiments[0]?.experiment_id ?? "",
    [experiments, searchParams]
  );
  const detail = useApi<ExperimentDetail>(
    selectedId ? `/api/experiments/${encodeURIComponent(selectedId)}` : "/api/experiments/__none__",
    EMPTY_DETAIL
  );
  const experimentDetail =
    detail.data.experiment_id === selectedId ? detail.data : EMPTY_DETAIL;
  const selectedTradeId = useMemo(() => {
    const selected = selectedTradeIdByExperiment[selectedId];
    if (selected && experimentDetail.trades.some((trade) => trade.trade_id === selected)) {
      return selected;
    }
    return experimentDetail.trades[0]?.trade_id ?? "";
  }, [experimentDetail.trades, selectedId, selectedTradeIdByExperiment]);
  const tradeDetail = useApi<TradeDetail>(
    selectedTradeId ? `/api/trades/${encodeURIComponent(selectedTradeId)}` : "/api/trades/__none__",
    EMPTY_TRADE_DETAIL
  );
  const selectedTradeDetail =
    tradeDetail.data.trade_id === selectedTradeId ? tradeDetail.data : EMPTY_TRADE_DETAIL;

  function toggleExperiment(experimentId: string) {
    setSelectedExperimentIds((current) => {
      const next = new Set(current);
      if (next.has(experimentId)) {
        next.delete(experimentId);
      } else {
        next.add(experimentId);
      }
      return next;
    });
  }

  function clearSelection() {
    setSelectedExperimentIds(new Set());
  }

  async function deleteSelectedExperiments() {
    const experimentIds = Array.from(selectedExperimentIds);
    if (experimentIds.length === 0) {
      return;
    }
    const confirmed = window.confirm(
      `确认删除 ${experimentIds.length} 个实验？会同步删除关联交易、孤儿信号和报告文件。`
    );
    if (!confirmed) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      const response = await fetch("/api/experiments", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ experiment_ids: experimentIds, delete_artifacts: true })
      });
      if (!response.ok) {
        throw new Error(`delete_failed:${response.status}`);
      }
      const nextExperiments = experiments.filter(
        (experiment) => !selectedExperimentIds.has(experiment.experiment_id)
      );
      setLocalExperiments(nextExperiments);
      clearSelection();
      if (selectedExperimentIds.has(selectedId)) {
        const nextId = nextExperiments[0]?.experiment_id;
        router.replace(nextId ? `/backtest?experiment=${encodeURIComponent(nextId)}` : "/experiments");
      }
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "delete_failed");
    } finally {
      setDeleting(false);
    }
  }

  if (experiments.length === 0) {
    return <EmptyState title="暂无回测详情" description="当前还没有实验结果，先跑流水线再看详情。" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2 className="text-4xl font-semibold">实验详情</h2>
          <p className="mt-2 text-sm text-muted">事件驱动回测是主裁判；缺失的 vectorbt 对照会如实显示，不会伪造。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button
                className="bg-surface2 text-text hover:bg-border"
                onClick={() => setSelectedExperimentIds(new Set(experiments.map((item) => item.experiment_id)))}
              >
                全选
              </Button>
              <Button className="bg-surface2 text-text hover:bg-border" onClick={clearSelection}>
                清空
              </Button>
              <Button
                className="bg-negative text-white hover:bg-negative/80 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={deleteSelectedExperiments}
                disabled={selectedExperimentIds.size === 0 || deleting}
              >
                {deleting ? "删除中..." : `删除所选 ${selectedExperimentIds.size}`}
              </Button>
            </>
          ) : null}
          <Button
            className={editing ? "bg-surface2 text-text hover:bg-border" : undefined}
            onClick={() => {
              setEditing((value) => !value);
              clearSelection();
              setDeleteError(null);
            }}
          >
            {editing ? "完成" : "编辑"}
          </Button>
        </div>
      </div>
      <Card className="p-5">
        {deleteError ? (
          <div className="mb-4 rounded-lg border border-negative/40 bg-negative/10 p-3 text-sm text-negative">
            删除失败：{deleteError}
          </div>
        ) : null}
        <ExperimentTable
          data={experiments}
          activeExperimentId={selectedId}
          onRowClick={(row) => router.push(`/backtest?experiment=${encodeURIComponent(row.experiment_id)}`)}
          editing={editing}
          selectedExperimentIds={selectedExperimentIds}
          onToggleExperiment={toggleExperiment}
        />
      </Card>
      <div className="grid gap-4 lg:grid-cols-6">
        <Card className="p-4">
          <p className="text-sm text-muted">策略</p>
          <p className="mt-3 text-2xl font-semibold">{experimentDetail.strategy}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">状态</p>
          <p className="mt-3 text-2xl font-semibold">{displayStatus(experimentDetail.status)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">运行时间</p>
          <p className="mt-3 text-lg font-semibold">{displayDateTime(experimentDetail.created_at)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">净收益</p>
          <p className="mt-3 text-2xl font-semibold text-positive">{(experimentDetail.metrics.net_return * 100).toFixed(1)}%</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">夏普</p>
          <p className="mt-3 text-2xl font-semibold">{experimentDetail.metrics.sharpe.toFixed(2)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">剔除前 5 笔后</p>
          <p className="mt-3 text-2xl font-semibold">{(experimentDetail.metrics.top5_removed_net_return * 100).toFixed(1)}%</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted">结论</p>
          <p className="mt-3 text-lg font-semibold">{displayText(experimentDetail.failure_reason ?? (experimentDetail.metrics.trade_count < 20 ? "low_trade_count" : experimentDetail.status))}</p>
        </Card>
        <Card className="p-4 lg:col-span-2">
          <p className="text-sm text-muted">参数选择</p>
          <p className="mt-3 text-lg font-semibold">{displayText(experimentDetail.parameter_selection_source ?? "base_strategy_config")}</p>
          <p className="mt-2 text-xs text-muted">{displayText(experimentDetail.parameter_selection_reason ?? "-")}</p>
        </Card>
      </div>
      {experimentDetail.selected_parameters && Object.keys(experimentDetail.selected_parameters).length > 0 ? (
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">选中参数</h3>
          <pre className="overflow-x-auto rounded-lg bg-[#11161d] p-4 text-xs text-muted">
            {JSON.stringify(experimentDetail.selected_parameters, null, 2)}
          </pre>
        </Card>
      ) : null}
      <Card className="p-5">
        <div className="grid gap-4 lg:grid-cols-4">
          <div>
            <p className="text-sm text-muted">实验</p>
            <HashBadge value={experimentDetail.experiment_id || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">配置哈希</p>
            <HashBadge value={experimentDetail.config_hash || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">切分哈希</p>
            <HashBadge value={experimentDetail.split_hash || "-"} />
          </div>
          <div>
            <p className="text-sm text-muted">快照哈希</p>
            <HashBadge value={experimentDetail.data_snapshot_hash || "-"} />
          </div>
        </div>
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">权益</h3>
          {experimentDetail.equity_curve.length === 0 ? (
            <EmptyState title="暂无权益曲线" description="当前实验没有成交，不能伪造收益曲线。" />
          ) : (
            <EquityChart points={experimentDetail.equity_curve} />
          )}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">回撤</h3>
          {experimentDetail.drawdown_curve.length === 0 ? (
            <EmptyState title="暂无回撤曲线" description="当前实验没有成交，回撤也保持空态。" />
          ) : (
            <DrawdownChart points={experimentDetail.drawdown_curve} />
          )}
        </Card>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">按标的</h3>
          {experimentDetail.by_symbol.length === 0 ? (
            <EmptyState title="暂无标的拆分" description="当前实验没有成交通道。" />
          ) : (
            <div className="space-y-3">
              {experimentDetail.by_symbol.map((row) => (
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
          {experimentDetail.by_month.length === 0 ? (
            <EmptyState title="暂无月度拆分" description="当前实验没有月度收益数据。" />
          ) : (
            <div className="space-y-3">
              {experimentDetail.by_month.map((row) => (
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
        <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-2xl font-semibold">交易</h3>
            <p className="mt-1 text-sm text-muted">点击一笔交易，在下方查看 K 线上下文和开平仓标记。</p>
          </div>
          <p className="text-xs text-muted">{experimentDetail.trades.length} 笔交易</p>
        </div>
        {experimentDetail.trades.length === 0 ? (
          <EmptyState title="暂无交易详情" description="这次样本没有触发有效成交，所以实验被拒绝更合理。" />
        ) : (
          <TradeTable
            data={experimentDetail.trades}
            activeTradeId={selectedTradeId}
            onRowClick={(row) =>
              setSelectedTradeIdByExperiment((current) => ({
                ...current,
                [selectedId]: row.trade_id
              }))
            }
          />
        )}
      </Card>
      {experimentDetail.trades.length > 0 ? (
        <TradeDetailPanel detail={selectedTradeDetail} loading={tradeDetail.loading} />
      ) : null}
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">vectorbt 对照差异</h3>
          <p className="text-sm text-muted">{displayText(experimentDetail.vectorbt_diff.comment)}</p>
          {experimentDetail.vectorbt_diff.vectorbt_reference ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">状态</p>
                <p className="mt-1 font-semibold">{displayStatus(String(experimentDetail.vectorbt_diff.vectorbt_reference.status))}</p>
              </div>
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">版本</p>
                <p className="mt-1 font-semibold">{String(experimentDetail.vectorbt_diff.vectorbt_reference.version ?? "未知")}</p>
              </div>
              <div className="rounded-lg bg-[#11161d] p-3">
                <p className="text-xs uppercase tracking-[0.2em] text-muted">净收益差值</p>
                <p className="mt-1 font-semibold">
                  {experimentDetail.vectorbt_diff.net_return_delta == null ? "不适用" : `${(experimentDetail.vectorbt_diff.net_return_delta * 100).toFixed(2)}%`}
                </p>
              </div>
            </div>
          ) : null}
        </Card>
        <Card className="p-5">
          <h3 className="mb-4 text-2xl font-semibold">报告产物</h3>
          <div className="space-y-2 text-sm">
            {experimentDetail.report_urls.html ? <a className="text-accent" href={experimentDetail.report_urls.html}>HTML 报告</a> : <p className="text-muted">HTML 报告不可用</p>}
            {experimentDetail.report_urls.markdown ? <a className="text-accent" href={experimentDetail.report_urls.markdown}>Markdown 报告</a> : <p className="text-muted">Markdown 报告不可用</p>}
            {experimentDetail.report_urls.trades_csv ? <a className="text-accent" href={experimentDetail.report_urls.trades_csv}>交易 CSV</a> : <p className="text-muted">交易 CSV 不可用</p>}
          </div>
        </Card>
      </div>
      <Card className="p-5">
        <h3 className="mb-4 text-2xl font-semibold">配置视图</h3>
        <pre className="overflow-x-auto rounded-lg bg-[#11161d] p-4 text-xs text-muted">
          {JSON.stringify(localizeValue(experimentDetail.config_view), null, 2)}
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
