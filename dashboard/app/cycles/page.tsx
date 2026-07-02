"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { HashBadge } from "@/components/HashBadge";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import { displayDateTime } from "@/lib/display";
import type {
  CycleResearchCandidate,
  CycleResearchCycle,
  CycleResearchRun
} from "@/types/api";

const MODEL_MODE_LABELS: Record<string, string> = {
  llm: "大模型",
  rules_fallback: "规则回退",
  none: "未运行",
  idle: "待机"
};

function pct(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function num(value: number | string | null | undefined, digits = 3) {
  if (value == null || value === "") {
    return "-";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  return parsed.toFixed(digits);
}

function pathTail(path?: string | null) {
  if (!path) {
    return "-";
  }
  return path.split("/").slice(-4).join("/");
}

function modelModeLabel(value?: string | null) {
  if (!value) {
    return "未运行";
  }
  return MODEL_MODE_LABELS[value] ?? value;
}

function ConfigGrid({ value }: { value?: Record<string, unknown> | null }) {
  const entries = Object.entries(value ?? {});
  if (!entries.length) {
    return <p className="text-sm text-muted">暂无参数。</p>;
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {entries.map(([key, nestedValue]) => (
        <div key={key} className="rounded-md border border-border bg-canvas/50 p-3">
          <p className="text-xs text-muted">{key}</p>
          <p className="mt-2 break-words font-mono text-sm text-text">{String(nestedValue)}</p>
        </div>
      ))}
    </div>
  );
}

function CandidateCard({
  candidate,
  bestCandidateId
}: {
  candidate: CycleResearchCandidate;
  bestCandidateId?: string | null;
}) {
  const quality = candidate.quality;
  return (
    <div className="rounded-lg border border-border bg-canvas/40 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <HashBadge value={candidate.candidate_id} />
          {candidate.candidate_id === bestCandidateId ? <Badge tone="positive">最佳</Badge> : null}
        </div>
        <div className="grid gap-2 text-sm text-muted sm:grid-cols-3 lg:min-w-[520px]">
          <span>总分 {num(quality.score)}</span>
          <span>周期 {quality.cycle_count}</span>
          <span>覆盖 {pct(quality.coverage_ratio)}</span>
          <span>强度 {num(quality.strength_score)}</span>
          <span>稳定 {num(quality.stability_score)}</span>
          <span>对照区分 {num(quality.control_group_separation)}</span>
        </div>
      </div>
      <div className="mt-4">
        <ConfigGrid value={candidate.cycle_config} />
      </div>
    </div>
  );
}

function SymbolSummaryTable({ rows }: { rows: NonNullable<CycleResearchRun["cycles_by_symbol_summary"]> }) {
  return (
    <Card className="p-5">
      <h3 className="text-2xl font-semibold">分币种周期</h3>
      <p className="mt-1 text-sm text-muted">
        用来检查强庄币组是否明显多于对照组。如果对照组很多，规则可能太宽。
      </p>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-2 pr-4">代币</th>
              <th className="py-2 pr-4">周期数</th>
              <th className="py-2 pr-4">中位拉盘</th>
              <th className="py-2 pr-4">中位砸盘</th>
              <th className="py-2 pr-4">中位时长</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} className="border-t border-border">
                <td className="py-3 pr-4 font-semibold">{row.symbol}</td>
                <td className="py-3 pr-4 font-mono">{row.cycle_count}</td>
                <td className="py-3 pr-4 font-mono text-positive">{pct(row.median_pump_return)}</td>
                <td className="py-3 pr-4 font-mono text-negative">{pct(row.median_dump_return)}</td>
                <td className="py-3 pr-4 font-mono">{num(row.median_duration_hours, 1)}h</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <EmptyState title="暂无分币种统计" description="该运行没有周期结果。" /> : null}
      </div>
    </Card>
  );
}

function CycleTable({ rows }: { rows: CycleResearchCycle[] }) {
  return (
    <Card className="p-5">
      <h3 className="text-2xl font-semibold">周期明细</h3>
      <p className="mt-1 text-sm text-muted">
        这些是代码按最佳规则后验标注的操盘周期，可用于人工抽查；后续交易信号不能直接偷看这些时间点。
      </p>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[1280px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-2 pr-4">代币</th>
              <th className="py-2 pr-4">拉盘起点</th>
              <th className="py-2 pr-4">最高点</th>
              <th className="py-2 pr-4">砸盘结束</th>
              <th className="py-2 pr-4">拉盘</th>
              <th className="py-2 pr-4">砸盘</th>
              <th className="py-2 pr-4">总时长</th>
              <th className="py-2 pr-4">质量分</th>
              <th className="py-2 pr-4">规则</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.cycle_id} className="border-t border-border">
                <td className="py-3 pr-4 font-semibold">{row.symbol}</td>
                <td className="py-3 pr-4 text-xs">{displayDateTime(row.pump_start)}</td>
                <td className="py-3 pr-4 text-xs">{displayDateTime(row.peak_time)}</td>
                <td className="py-3 pr-4 text-xs">{displayDateTime(row.dump_end)}</td>
                <td className="py-3 pr-4 font-mono text-positive">{pct(row.pump_return)}</td>
                <td className="py-3 pr-4 font-mono text-negative">{pct(row.dump_return)}</td>
                <td className="py-3 pr-4 font-mono">{num(row.duration_hours, 1)}h</td>
                <td className="py-3 pr-4 font-mono">{num(row.quality_score)}</td>
                <td className="py-3 pr-4 text-xs text-muted">{row.detection_rule}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <EmptyState title="暂无周期" description="最佳规则没有标出周期。" /> : null}
      </div>
    </Card>
  );
}

export default function CyclesPage() {
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const { data: runs, error: listError } = useApi<CycleResearchRun[]>(
    "/api/autoresearch/cycle-runs",
    []
  );
  const activeRunId = selectedRunId || runs[0]?.run_id || "";
  const { data, error } = useApi<CycleResearchRun | null>(
    activeRunId ? `/api/autoresearch/cycle-runs/${activeRunId}` : "/api/autoresearch/cycle-latest",
    null
  );

  const candidates = useMemo(
    () => (data?.candidates ?? []).slice().sort((a, b) => b.quality.score - a.quality.score),
    [data?.candidates]
  );
  const cycles = data?.cycles ?? [];

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-[linear-gradient(135deg,#101820,#0b0e11)] p-6 shadow-panel">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge tone="info">周期研究</Badge>
              <StatusBadge value={data?.status ?? "idle"} />
              <Badge tone="accent">{modelModeLabel(data?.model_status.mode)}</Badge>
            </div>
            <h2 className="text-4xl font-semibold">操盘周期发现</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              大模型负责提出和迭代周期定义，代码负责确定性扫描 K 线并生成标签。
              这里展示每轮候选、评分、最佳规则和最终周期表。
            </p>
          </div>
          <div className="grid gap-2 text-sm text-muted sm:min-w-[360px]">
            <label className="text-xs text-muted">选择运行</label>
            <select
              className="rounded-md border border-border bg-surface px-3 py-2 text-text"
              value={activeRunId}
              onChange={(event) => setSelectedRunId(event.target.value)}
            >
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id} · {displayDateTime(run.completed_at ?? run.created_at)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {listError || error ? <ErrorState title="读取周期研究失败" description={listError ?? error ?? ""} /> : null}

      {!data ? (
        <Card className="p-6">
          <EmptyState
            title="暂无操盘周期研究"
            description="先执行 uv run python -m super_crypto.cli cycle-research --config configs/cycle_discovery.yaml。"
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <MetricCard
              label="最佳候选"
              value={data.best_candidate_id?.slice(0, 14) ?? "-"}
              sublabel={`共 ${data.candidate_count} 个候选`}
              badge={data.status}
            />
            <MetricCard
              label="最佳总分"
              value={num(data.best_quality?.score)}
              sublabel={`迭代 ${data.iteration_count ?? "-"} 轮`}
            />
            <MetricCard
              label="周期数量"
              value={String(data.cycle_count ?? data.best_quality?.cycle_count ?? 0)}
              sublabel={`覆盖 ${data.best_quality?.covered_symbols ?? 0}/${data.symbols.length} 个标的`}
            />
            <MetricCard
              label="对照组区分"
              value={num(data.best_quality?.control_group_separation)}
              sublabel={`对照组平均 ${num(data.best_quality?.control_cycles_per_symbol)} 个/币`}
            />
            <MetricCard
              label="稳定性"
              value={num(data.best_quality?.stability_score)}
              sublabel={`周期级别 ${data.timeframe}`}
            />
          </div>

          <Card className="p-5">
            <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
              <section>
                <h3 className="text-2xl font-semibold">最新研究假设</h3>
                <p className="mt-3 text-sm leading-6 text-muted">
                  {data.hypothesis.hypothesis ?? "未生成假设"}
                </p>
                <p className="mt-2 text-sm leading-6 text-warning">
                  风险：{data.hypothesis.risk ?? "未说明"}
                </p>
              </section>
              <section>
                <h3 className="text-2xl font-semibold">产物路径</h3>
                <div className="mt-3 grid gap-2 text-sm text-muted">
                  <p>最佳规则：<span className="font-mono">{pathTail(data.best_rule_path)}</span></p>
                  <p>周期表：<span className="font-mono">{pathTail(data.best_cycles_csv_path)}</span></p>
                  <p>清单：<span className="font-mono">{pathTail(data.manifest_path)}</span></p>
                </div>
              </section>
            </div>
          </Card>

          <Card className="p-5">
            <h3 className="text-2xl font-semibold">最佳周期定义</h3>
            <p className="mt-1 text-sm text-muted">这是最终被选中的确定性扫描规则。</p>
            <div className="mt-5">
              <ConfigGrid value={data.best_rule ?? data.best_cycle_config} />
            </div>
          </Card>

          <Card className="p-5">
            <h3 className="text-2xl font-semibold">币种分组</h3>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {["strong", "volatile", "control"].map((group) => (
                <div key={group} className="rounded-md border border-border bg-canvas/50 p-4">
                  <p className="text-sm font-semibold text-text">
                    {group === "strong" ? "强庄币" : group === "volatile" ? "高波动" : "对照组"}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {(data.symbol_groups?.[group] ?? []).join("、") || "-"}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <SymbolSummaryTable rows={data.cycles_by_symbol_summary ?? []} />

          <Card className="p-5">
            <h3 className="text-2xl font-semibold">迭代记录</h3>
            <div className="mt-5 grid gap-3">
              {(data.iterations ?? []).map((iteration) => (
                <div key={iteration.iteration} className="rounded-lg border border-border bg-canvas/40 p-4">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="accent">第 {iteration.iteration} 轮</Badge>
                      {iteration.best_candidate_id ? <HashBadge value={iteration.best_candidate_id} /> : null}
                    </div>
                    <p className="text-sm text-muted">
                      候选 {iteration.candidate_count} · 最佳分 {num(iteration.best_quality?.score)}
                    </p>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted">
                    {iteration.hypothesis.hypothesis ?? "未记录假设"}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <h3 className="text-2xl font-semibold">候选定义排名</h3>
            <div className="mt-5 grid gap-3">
              {candidates.map((candidate) => (
                <CandidateCard
                  key={candidate.candidate_id}
                  candidate={candidate}
                  bestCandidateId={data.best_candidate_id}
                />
              ))}
            </div>
          </Card>

          <CycleTable rows={cycles} />
        </>
      )}
    </div>
  );
}
