"use client";

import { useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { HashBadge } from "@/components/HashBadge";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  const [refreshKey, setRefreshKey] = useState(0);
  const [editMode, setEditMode] = useState(false);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { data: runs } = useApi<AutoResearchRun[]>(`/api/autoresearch/runs?refresh=${refreshKey}`, []);
  const data = runs[0] ?? null;
  const latestIteration = data?.iterations.at(-1);
  const latestExperiment = latestIteration?.validation_result.experiment;
  const metrics = latestExperiment?.metrics;
  const llmMode = data?.model_status.mode ?? "none";

  async function deleteRuns(runIds: string[]) {
    const uniqueRunIds = Array.from(new Set(runIds));
    if (!uniqueRunIds.length) {
      return;
    }
    const confirmed = window.confirm(`确定删除 ${uniqueRunIds.length} 条研究循环记录吗？实验结果不会被删除。`);
    if (!confirmed) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      const response = await fetch("/api/autoresearch/runs", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_ids: uniqueRunIds })
      });
      if (!response.ok) {
        throw new Error(`delete_failed:${response.status}`);
      }
      setSelectedRunIds([]);
      setRefreshKey((value) => value + 1);
    } catch (caughtError) {
      setDeleteError(caughtError instanceof Error ? caughtError.message : "delete_failed");
    } finally {
      setDeleting(false);
    }
  }

  function toggleSelected(runId: string) {
    setSelectedRunIds((current) =>
      current.includes(runId) ? current.filter((item) => item !== runId) : [...current, runId]
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border bg-[radial-gradient(circle_at_top_left,rgba(0,82,255,0.18),transparent_34%),linear-gradient(135deg,#111821,#0b0e11)] p-6 shadow-panel">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone="info">研究循环</Badge>
              <StatusBadge value={data?.status ?? "idle"} />
              <StatusBadge value={llmMode} />
            </div>
            <h2 className="text-4xl font-semibold">研究循环</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              这里展示自动研究的假设、参数计划、验证集实验和复盘建议。没有配置大模型
              时会显示规则兜底，不会假装调用了大模型。
            </p>
          </div>
          <Button
            className="self-start bg-surface2 text-text hover:bg-border lg:self-end"
            onClick={() => setRefreshKey((value) => value + 1)}
          >
            刷新运行记录
          </Button>
          {data ? (
            <div className="grid gap-2 text-sm text-muted sm:grid-cols-2 lg:min-w-[420px]">
              <span>开始时间：{displayDateTime(data.created_at)}</span>
              <span>完成时间：{displayDateTime(data.completed_at)}</span>
              <span>轮数：{data.iterations.length}</span>
              <span>基础配置：{displayPath(data.config_path)}</span>
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
            <MetricCard
              label="运行ID"
              value={data.run_id.slice(0, 12)}
              sublabel={`开始 ${displayDateTime(data.created_at)}`}
            />
            <MetricCard label="状态" value={displayStatus(data.status)} sublabel={data.latest_acceptance.reason} />
            <MetricCard
              label="模型模式"
              value={data.model_status.model || displayStatus(data.model_status.mode)}
              sublabel={
                data.model_status.base_url ??
                (data.model_status.reason ? displayStatus(data.model_status.reason) : "大模型环境变量已读取")
              }
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

          <Card className="p-5">
            <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
              <div>
                <h3 className="text-2xl font-semibold">最近运行记录</h3>
                <p className="mt-1 text-sm text-muted">用这里确认 dashboard 当前看到的是哪一次 loopresearch。</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm text-muted">共 {runs.length} 次</p>
                {editMode ? (
                  <>
                    <Button
                      className="bg-surface2 text-text hover:bg-border"
                      onClick={() => setSelectedRunIds(runs.map((run) => run.run_id))}
                      disabled={!runs.length || deleting}
                    >
                      全选
                    </Button>
                    <Button
                      className="bg-negative text-white hover:bg-negative/80"
                      onClick={() => void deleteRuns(selectedRunIds)}
                      disabled={!selectedRunIds.length || deleting}
                    >
                      删除选中 {selectedRunIds.length}
                    </Button>
                    <Button
                      className="bg-surface2 text-text hover:bg-border"
                      onClick={() => {
                        setEditMode(false);
                        setSelectedRunIds([]);
                      }}
                      disabled={deleting}
                    >
                      完成
                    </Button>
                  </>
                ) : (
                  <Button
                    className="bg-surface2 text-text hover:bg-border"
                    onClick={() => setEditMode(true)}
                    disabled={!runs.length}
                  >
                    编辑记录
                  </Button>
                )}
              </div>
            </div>
            {deleteError ? (
              <p className="mb-3 rounded-lg border border-negative/40 bg-negative/10 p-3 text-sm text-negative">
                删除失败：{deleteError}
              </p>
            ) : null}
            <div className="grid gap-3">
              {runs.map((run) => {
                const firstExperiment = run.iterations[0]?.validation_result.experiment;
                const selected = selectedRunIds.includes(run.run_id);
                return (
                  <div
                    key={run.run_id}
                    className={`grid gap-3 rounded-lg border border-border bg-canvas/40 p-4 text-sm ${
                      editMode ? "md:grid-cols-[auto_1fr_1fr_1.2fr_auto]" : "md:grid-cols-[1fr_1fr_1.2fr]"
                    }`}
                  >
                    {editMode ? (
                      <label className="flex items-start pt-7">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleSelected(run.run_id)}
                          className="h-4 w-4 accent-[var(--accent)]"
                          aria-label={`选择 ${run.run_id}`}
                        />
                      </label>
                    ) : null}
                    <div>
                      <p className="text-muted">运行</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <HashBadge value={run.run_id} />
                        <StatusBadge value={run.status} />
                      </div>
                      <p className="mt-2 text-muted">开始 {displayDateTime(run.created_at)}</p>
                      <p className="mt-1 text-muted">完成 {displayDateTime(run.completed_at)}</p>
                    </div>
                    <div>
                      <p className="text-muted">实验</p>
                      <p className="mt-1 font-mono text-text">
                        {firstExperiment?.experiment_id ?? "-"}
                      </p>
                      <p className="mt-2 text-muted">
                        {run.iterations.length} 轮 · {displayStatus(run.model_status.mode)}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted">建议</p>
                      <p className="mt-1 leading-6 text-text">{run.recommendation}</p>
                    </div>
                    {editMode ? (
                      <div className="flex items-start justify-end">
                        <Button
                          className="bg-negative text-white hover:bg-negative/80"
                          onClick={() => void deleteRuns([run.run_id])}
                          disabled={deleting}
                        >
                          删除
                        </Button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <div className="border-b border-border bg-surface2/60 p-5">
              <p className="text-sm text-muted">最终建议</p>
              <h3 className="mt-2 text-2xl font-semibold">{data.recommendation}</h3>
            </div>
            <div className="grid gap-4 p-5 text-sm text-muted md:grid-cols-3">
              <div>
                <p className="font-semibold text-text">运行ID</p>
                <div className="mt-2"><HashBadge value={data.run_id} /></div>
              </div>
              <div>
                <p className="font-semibold text-text">运行清单</p>
                <p className="mt-2 break-words font-mono">{displayPath(data.manifest_path)}</p>
              </div>
              <div>
                <p className="font-semibold text-text">建议文件</p>
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
                      <p className="text-sm text-muted">轮次 {iteration.iteration}</p>
                      <h3 className="mt-1 text-xl font-semibold">
                        {iteration.hypothesis.hypothesis ?? "未生成假设"}
                      </h3>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                        <span>轮次开始：{displayDateTime(iteration.started_at)}</span>
                        <span>轮次完成：{displayDateTime(iteration.completed_at)}</span>
                        <span>实验时间：{displayDateTime(experiment.created_at)}</span>
                      </div>
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
                          <p className="mt-2 text-sm text-negative">大模型错误：{iteration.hypothesis.llm_error}</p>
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
                          生成配置：{iteration.generated_config}
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
