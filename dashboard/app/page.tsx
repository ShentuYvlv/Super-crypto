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
import { displayDateTime, displayStatus, displayText } from "@/lib/display";
import type { OverviewPayload, SymbolSummary } from "@/types/api";

const EMPTY_OVERVIEW: OverviewPayload = {
  latest_pipeline_run: null,
  latest_research_run: null,
  latest_experiment: null,
  latest_validation_experiment: null,
  latest_holdout_experiment: null,
  frozen_config: {
    available: false,
    path: null,
    source_experiment_id: null,
    created_at: null
  },
  holdout_status: {
    run_count: 0,
    has_result: false,
    latest_experiment_id: null,
    status: "not_run"
  },
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
  const researchRun = overview.data.latest_research_run;
  const validationExperiment = overview.data.latest_validation_experiment;
  const holdoutExperiment = overview.data.latest_holdout_experiment;
  const frozenConfig = overview.data.frozen_config ?? EMPTY_OVERVIEW.frozen_config;
  const holdoutStatus = overview.data.holdout_status ?? EMPTY_OVERVIEW.holdout_status;

  if (overview.error && overview.data.latest_pipeline_run == null) {
    return <ErrorState title="总览接口不可用" description="请先启动报告服务或检查后端接口。" />;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-4xl font-semibold">总览</h2>
      <div className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5 xl:col-span-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-2xl font-semibold">研究循环</h3>
              <p className="mt-2 text-sm text-muted">
                AutoResearch 是主流程；流水线和单次实验只是内部执行模块。
              </p>
            </div>
            <span className="rounded-md border border-border px-2 py-1 text-xs text-muted">
              {displayStatus(researchRun?.status ?? "idle")}
            </span>
          </div>
          <div className="mt-5 grid gap-3 text-sm text-muted md:grid-cols-2">
            <p>最新运行：{researchRun?.run_id ?? "-"}</p>
            <p>完成时间：{displayDateTime(researchRun?.completed_at ?? researchRun?.created_at)}</p>
            <p>轮数：{researchRun?.iterations.length ?? 0}</p>
            <p>模型：{displayStatus(researchRun?.model_status.mode ?? "none")}</p>
          </div>
          <p className="mt-4 text-sm leading-6 text-muted">
            {researchRun?.recommendation ?? "暂无研究循环建议。先运行 just research。"}
          </p>
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">验证集结果</h3>
          {validationExperiment ? (
            <div className="mt-5 space-y-2 text-sm text-muted">
              <p>状态：{displayStatus(validationExperiment.status)}</p>
              <p>净收益：{(validationExperiment.metrics.net_return * 100).toFixed(2)}%</p>
              <p>交易数：{validationExperiment.metrics.trade_count}</p>
              <p>实验：{validationExperiment.experiment_id}</p>
            </div>
          ) : (
            <EmptyState title="暂无验证集结果" description="先运行 just research 生成 validation 实验。" />
          )}
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">最终留出集</h3>
          <div className="mt-5 space-y-2 text-sm text-muted">
            <p>冻结策略：{frozenConfig?.available ? "已生成" : "未生成"}</p>
            <p>运行次数：{holdoutStatus?.run_count ?? 0}</p>
            <p>状态：{displayStatus(holdoutStatus?.status ?? "not_run")}</p>
            {holdoutExperiment ? (
              <>
                <p>净收益：{(holdoutExperiment.metrics.net_return * 100).toFixed(2)}%</p>
                <p>交易数：{holdoutExperiment.metrics.trade_count}</p>
              </>
            ) : (
              <p>准备最终验收时运行 just holdout。</p>
            )}
          </div>
        </Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-6">
        <MetricCard label="今日信号" value={String(overview.data.today_signal_count)} sublabel="当前数据窗口" badge="实时" />
        <MetricCard label="跟踪标的" value={String(overview.data.active_monitored_symbols)} sublabel="信号活跃池" badge="标的池" />
        <MetricCard
          label="模拟 7 日盈亏"
          value={`${(overview.data.paper_pnl_7d * 100).toFixed(1)}%`}
          sublabel="仅模拟交易"
          badge="模拟"
        />
        <MetricCard
          label="验证集最佳"
          value={`${(overview.data.validation_best_net_return * 100).toFixed(1)}%`}
          sublabel="最新实验"
          badge="事件驱动"
        />
        <MetricCard label="最大回撤" value={`${(overview.data.max_drawdown * 100).toFixed(1)}%`} sublabel="事件驱动" badge="风险" />
        <MetricCard
          label="数据健康度"
          value={`${(overview.data.data_health_score * 100).toFixed(0)}%`}
          sublabel="数据与执行可信度"
          badge={overview.data.data_warnings.length ? "告警" : "健康"}
        />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr_.8fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-2xl font-semibold">候选标的评分</h3>
              <p className="text-sm text-muted">按时点截断展示评分分组、衍生品数据和最新信号。</p>
            </div>
            <Link href="/symbols" prefetch={false} className="text-sm text-accent">
              查看全部
            </Link>
          </div>
          {symbols.data.length === 0 ? (
            <EmptyState title="暂无标的快照" description="先运行 just research，页面会自动读取最新 Parquet / SQLite 数据。" />
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
                  <span className="truncate text-muted">{displayText(row.latest_signal_label)}</span>
                </Link>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">表现快照</h3>
          <p className="mt-1 text-sm text-muted">这里不会触发留出集；主指标只采用事件驱动回测。</p>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {overview.data.performance_snapshot.split_comparison.map((row) => (
              <Card key={`${row.split}-${row.status}`} className="bg-[#11161d] p-4">
                <p className="text-sm text-muted">{displayText(row.split)}</p>
                <p className="mt-3 text-xl font-semibold">{displayStatus(row.status)}</p>
                <p className="mt-2 text-positive">{(row.net_return * 100).toFixed(1)}%</p>
                <p className="text-sm text-muted">交易数 {row.trade_count}</p>
              </Card>
            ))}
            {overview.data.performance_snapshot.split_comparison.length === 0 ? (
              <EmptyState title="暂无实验摘要" description="最新实验详情还没生成，先运行 just research。" />
            ) : null}
          </div>
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">最新告警</h3>
          <div className="mt-4 space-y-3">
            {overview.data.latest_alerts.length === 0 ? (
              <EmptyState title="暂无实时信号" description="当前样本没有触发 V4A / V4B 信号，这比伪造信号更可信。" />
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
                      <p className="mt-1 text-negative">{signal.strategy} 做空</p>
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
          <h3 className="text-2xl font-semibold">权益曲线</h3>
          {overview.data.performance_snapshot.equity_curve.length === 0 ? (
            <EmptyState title="暂无权益曲线" description="没有交易时不展示伪造收益曲线。" />
          ) : (
            <EquityChart points={overview.data.performance_snapshot.equity_curve} />
          )}
        </Card>
        <Card className="p-5">
          <h3 className="text-2xl font-semibold">回撤曲线</h3>
          {overview.data.performance_snapshot.drawdown_curve.length === 0 ? (
            <EmptyState title="暂无回撤曲线" description="当前实验没有成交，回撤图保持空态。" />
          ) : (
            <DrawdownChart points={overview.data.performance_snapshot.drawdown_curve} />
          )}
        </Card>
      </div>
      <Card className="p-5">
        <h3 className="text-2xl font-semibold">数据告警</h3>
        {overview.data.data_warnings.length === 0 ? (
          <p className="mt-3 text-sm text-muted">最新研究流程没有关键告警。</p>
        ) : (
          <div className="mt-4 space-y-3">
            {overview.data.data_warnings.map((warning) => (
              <div key={`${warning.source_name}-${warning.detail}`} className="rounded-lg border border-border bg-[#11161d] px-4 py-3 text-sm">
                <p className="font-medium">{displayText(warning.source_name)}</p>
                <p className="mt-1 text-muted">
                  {displayStatus(warning.status)} · {displayText(warning.detail)}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
