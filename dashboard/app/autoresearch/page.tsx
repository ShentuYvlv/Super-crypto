"use client";

import { EmptyState } from "@/components/EmptyState";
import { HashBadge } from "@/components/HashBadge";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import { displayDateTime, displayReason, displayStatus } from "@/lib/display";
import type { AutoResearchRun } from "@/types/api";

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function displayPath(path: string | undefined): string {
  if (!path) {
    return "-";
  }
  const parts = path.split("/");
  return parts.slice(-3).join("/");
}

function ParameterGrid({ value }: { value?: Record<string, unknown> }) {
  const entries = Object.entries(value ?? {});
  if (entries.length === 0) {
    return <p className="text-sm text-muted">本轮没有参数网格变更。</p>;
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {entries.map(([key, nestedValue]) => (
        <div key={key} className="rounded-lg border border-border bg-canvas/50 p-3">
          <p className="text-xs uppercase tracking-wide text-muted">{key}</p>
          <p className="mt-2 break-words font-mono text-sm text-text">
            {JSON.stringify(nestedValue)}
          </p>
        </div>
      ))}
    </div>
  );
}

export default function AutoResearchPage() {
  const { data } = useApi<AutoResearchRun | null>("/api/autoresearch/latest", null);
  const latestIteration = data?.iterations.at(-1);
  const latestExperiment = latestIteration?.validation_result.experiment;
  const metrics = latestExperiment?.metrics;
  const llmMode = data?.model_status.mode ?? "none";

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border bg-[radial-gradient(circle_at_top_left,rgba(0,82,255,0.18),transparent_34%),linear-gradient(135deg,#111821,#0b0e11)] p-6 shadow-panel">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone="info">LoopResearch</Badge>
              <StatusBadge value={data?.status ?? "idle"} />
              <StatusBadge value={llmMode} />
            </div>
            <h2 className="text-4xl font-semibold">研究循环</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              这里展示 AutoResearch 的假设、参数计划、验证集实验和复盘建议。没有配置 LLM
              时会显示 rules_fallback，不会假装调用了大模型。
            </p>
          </div>
          {data ? (
            <div className="grid gap-2 text-sm text-muted sm:grid-cols-2 lg:min-w-[420px]">
              <span>运行时间：{displayDateTime(data.created_at)}</span>
              <span>轮数：{data.iterations.length}</span>
              <span>基础配置：{displayPath(data.config_path)}</span>
              <span>研究配置：{displayPath(data.autoresearch_config_path)}</span>
            </div>
          ) : null}
        </div>
      </div>

      {!data ? (
        <Card className="p-6">
          <EmptyState
            title="暂无研究循环"
            description="先执行 just loopresearch，完成后这里会显示假设、思考、建议和验证实验。"
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="状态" value={displayStatus(data.status)} sublabel={data.latest_acceptance.reason} />
            <MetricCard
              label="模型模式"
              value={data.model_status.model ?? displayStatus(data.model_status.mode)}
              sublabel={data.model_status.base_url ?? data.model_status.reason ?? "LLM 环境变量已读取"}
              badge={data.model_status.mode}
            />
            <MetricCard
              label="最新净收益"
              value={formatPercent(metrics?.net_return)}
              sublabel={`交易数 ${metrics?.trade_count ?? 0}`}
              badge={latestExperiment?.status}
            />
            <MetricCard
              label="最大回撤"
              value={formatPercent(metrics?.max_drawdown)}
              sublabel={`夏普 ${formatNumber(metrics?.sharpe)}`}
            />
          </div>

          <Card className="overflow-hidden">
            <div className="border-b border-border bg-surface2/60 p-5">
              <p className="text-sm text-muted">最终建议</p>
              <h3 className="mt-2 text-2xl font-semibold">{data.recommendation}</h3>
            </div>
            <div className="grid gap-4 p-5 text-sm text-muted md:grid-cols-3">
              <div>
                <p className="font-semibold text-text">Run ID</p>
                <div className="mt-2"><HashBadge value={data.run_id} /></div>
              </div>
              <div>
                <p className="font-semibold text-text">Manifest</p>
                <p className="mt-2 break-words font-mono">{displayPath(data.manifest_path)}</p>
              </div>
              <div>
                <p className="font-semibold text-text">Recommendation</p>
                <p className="mt-2 break-words font-mono">{displayPath(data.recommendation_path)}</p>
              </div>
            </div>
          </Card>

          <div className="space-y-4">
            {data.iterations.map((iteration) => {
              const experiment = iteration.validation_result.experiment;
              const iterationMetrics = experiment.metrics;
              return (
                <Card key={iteration.iteration} className="overflow-hidden">
                  <div className="flex flex-col gap-3 border-b border-border bg-surface2/60 p-5 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <p className="text-sm text-muted">Iteration {iteration.iteration}</p>
                      <h3 className="mt-1 text-xl font-semibold">
                        {iteration.hypothesis.hypothesis ?? "未生成假设"}
                      </h3>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge value={iteration.validation_acceptance.accepted ? "accepted" : "rejected"} />
                      <StatusBadge value={experiment.status} />
                      <HashBadge value={experiment.experiment_id} />
                    </div>
                  </div>

                  <div className="grid gap-5 p-5 xl:grid-cols-[1.2fr_1fr]">
                    <div className="space-y-5">
                      <section>
                        <p className="text-sm font-semibold text-text">思考依据</p>
                        <p className="mt-2 text-sm leading-6 text-muted">
                          {iteration.hypothesis.rationale ?? "无 rationale"}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-warning">
                          风险：{iteration.hypothesis.risk ?? "未说明"}
                        </p>
                        {iteration.hypothesis.llm_error ? (
                          <p className="mt-2 text-sm text-negative">LLM 错误：{iteration.hypothesis.llm_error}</p>
                        ) : null}
                      </section>

                      <section>
                        <p className="text-sm font-semibold text-text">参数计划</p>
                        <p className="mt-2 text-sm text-muted">
                          {iteration.plan.suggested_changes?.notes ?? "按 fallback planner 生成参数网格。"}
                        </p>
                        <div className="mt-3">
                          <ParameterGrid value={iteration.plan.suggested_changes?.parameter_grid} />
                        </div>
                        <p className="mt-3 break-words font-mono text-xs text-muted">
                          generated_config: {iteration.generated_config}
                        </p>
                      </section>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg border border-border bg-canvas/50 p-3">
                          <p className="text-xs text-muted">净收益</p>
                          <p className="mt-2 font-mono text-xl text-positive">
                            {formatPercent(iterationMetrics.net_return)}
                          </p>
                        </div>
                        <div className="rounded-lg border border-border bg-canvas/50 p-3">
                          <p className="text-xs text-muted">交易数</p>
                          <p className="mt-2 font-mono text-xl">{iterationMetrics.trade_count}</p>
                        </div>
                        <div className="rounded-lg border border-border bg-canvas/50 p-3">
                          <p className="text-xs text-muted">胜率</p>
                          <p className="mt-2 font-mono text-xl">{formatPercent(iterationMetrics.win_rate)}</p>
                        </div>
                        <div className="rounded-lg border border-border bg-canvas/50 p-3">
                          <p className="text-xs text-muted">回撤</p>
                          <p className="mt-2 font-mono text-xl text-negative">
                            {formatPercent(iterationMetrics.max_drawdown)}
                          </p>
                        </div>
                      </div>

                      <section className="rounded-lg border border-border bg-canvas/50 p-4">
                        <p className="text-sm font-semibold text-text">复盘建议</p>
                        <p className="mt-2 text-sm leading-6 text-muted">
                          {iteration.review.recommendation ?? iteration.review.decision ?? "未生成建议"}
                        </p>
                        <p className="mt-2 text-sm text-muted">
                          拒绝/接受原因：{displayReason(iteration.validation_acceptance.reason)}
                        </p>
                        {iteration.review.evidence?.length ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {iteration.review.evidence.map((item) => (
                              <Badge key={item} tone="neutral">{item}</Badge>
                            ))}
                          </div>
                        ) : null}
                        {iteration.review.trade_summary ? (
                          <div className="mt-4 grid gap-3 text-sm text-muted">
                            <p>
                              交易摘要：{iteration.review.trade_summary.trade_count} 笔，
                              {iteration.review.trade_summary.symbols.length} 个标的
                            </p>
                            {Object.keys(iteration.review.trade_summary.exit_reasons).length ? (
                              <p>
                                退出原因：
                                {Object.entries(iteration.review.trade_summary.exit_reasons)
                                  .map(([reason, count]) => `${displayReason(reason)} ${count}`)
                                  .join(" / ")}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </section>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
